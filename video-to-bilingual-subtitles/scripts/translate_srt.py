#!/usr/bin/env python3
"""Translate an SRT into a bilingual (source + Chinese) SRT via a local LM Studio server.

Design notes that matter for quality:

* The endpoint is LM Studio's native REST API (POST /api/v1/chat), NOT the
  OpenAI-compatible one. It takes {"model", "input", "reasoning"} and answers with
  an `output` list of parts; `type == "reasoning"` parts must be dropped.
* Reasoning is disabled (`"reasoning": "off"`) — thinking traces only add latency
  and occasionally bleed into the answer.
* Subtitle lines are sentence fragments. Each line is translated together with its
  neighbours supplied as CONTEXT ONLY, otherwise the model inserts "……" wherever
  the fragment breaks mid-phrase.
* Every answer is validated (must contain Chinese, must not be an echo of the
  prompt); invalid answers are retried with exponential backoff.

Usage:
    python translate_srt.py INPUT.srt -o OUT.srt \
        --url http://127.0.0.1:8899/api/v1/chat \
        --model google/gemma-4-12b-qat \
        [--glossary glossary.txt] [--no-context] [--delay 5] \
        [--max-retries 5] [--resume] [--test-indices 1,2,3]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

DEFAULT_GLOSSARY = [
    ("intelligence", "智能"),          # never 情报
    ("frontier intelligence", "前沿智能"),
    ("frontier model", "前沿模型"),
    ("compute", "算力"),
    ("compute capacity", "算力容量"),
    ("agent", "智能体"),
    ("bundle", "套件"),
    ("safety", "安全"),
    ("alignment", "对齐"),
    ("inference", "推理"),
    ("training", "训练"),
    ("enterprise", "企业级"),
]

# Chinese renderings of the instruction itself. If an answer contains these,
# the model echoed the prompt instead of translating.
ECHO_PATTERNS = [
    r"您是一位专业的",
    r"你是一位专业的",
    r"我是一位专业的",
    r"请仅提供中文翻译",
    r"请只提供中文译文",
    r"请将以下英文",
    r"不要添加任何额外的解释",
    r"不要包含原始英文",
]

PROMPT_HEADER = (
    "You are a professional {src} to Chinese (zh-Hans) translator. "
    "The source has been split into subtitle lines, so a single sentence may span "
    "several lines and the line you translate can be an incomplete fragment. "
    "Neighbouring lines are provided for CONTEXT ONLY — do not translate them, but use "
    "them to resolve what the current fragment means.\n"
    "Rules:\n"
    "1. Output only the Chinese translation of the current line. No explanations, no "
    "commentary, no repeating the source.\n"
    "2. Keep proper nouns (company, product and model names, acronyms) in their original form.\n"
    "3. Never output an ellipsis (……) as a placeholder for missing words. If the current "
    "line ends mid-sentence, use the context to work out the missing part and write a "
    "complete, natural Chinese clause that fits the flow.\n"
)

PROMPT_TAIL = (
    "Context - the line BEFORE (do not translate):\n{prev}\n"
    "Context - the line AFTER (do not translate):\n{next}\n"
    "Please translate ONLY the following line into Chinese:\n\n\n{text}"
)


# ---------------------------------------------------------------- helpers

def has_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def is_echo(text):
    return any(re.search(p, text) for p in ECHO_PATTERNS)


def parse_srt(path):
    """Return [(index, timestamp, text), ...] from an SRT file."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    entries = []
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        entries.append((lines[0].strip(), lines[1].strip(),
                        "\n".join(lines[2:]).strip()))
    return entries


def load_glossary(path):
    """Parse a glossary file of `english = 中文` or `english -> 中文` lines."""
    if not path:
        return DEFAULT_GLOSSARY
    pairs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for sep in ("->", "=>", "="):
                if sep in line:
                    src, dst = line.split(sep, 1)
                    pairs.append((src.strip(), dst.strip()))
                    break
    return pairs


def build_prompt(text, prev_text, next_text, glossary, source_lang, use_context):
    body = PROMPT_HEADER.format(src=source_lang)
    if glossary:
        body += "4. Use this glossary consistently:\n"
        body += "".join("   {} = {}\n".format(a, b) for a, b in glossary)
    if not use_context:
        prev_text = next_text = "(context disabled)"
    return body + PROMPT_TAIL.format(prev=prev_text or "(none)",
                                     next=next_text or "(none)",
                                     text=text)


def call_server(url, model, prompt, reasoning, timeout):
    """POST to LM Studio's native chat endpoint, return the message text only."""
    payload = {"model": model, "input": prompt, "reasoning": reasoning}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    parts = result.get("output", [])
    messages = [p.get("content", "") for p in parts if p.get("type") == "message"]
    if messages:
        return "\n".join(messages)
    return "\n".join(p.get("content", "") for p in parts)


def extract_translation(content):
    """Pick the translated segment out of the model's answer.

    The model sometimes echoes the prompt first and puts the translation after a
    blank line, so scan segments from last to first and skip echoes.
    """
    for seg in reversed(re.split(r"\n\n+", content.strip())):
        seg = seg.strip()
        if not seg or not has_chinese(seg) or is_echo(seg):
            continue
        kept = [l.strip() for l in seg.split("\n")
                if has_chinese(l) and not is_echo(l)]
        if kept:
            return "\n".join(kept)

    kept = [l.strip() for l in content.strip().split("\n")
            if has_chinese(l) and not is_echo(l)]
    return "\n".join(kept)


# ---------------------------------------------------------------- main

def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="source-language SRT")
    ap.add_argument("-o", "--output", required=True, help="bilingual SRT to write")
    ap.add_argument("--url", default="http://127.0.0.1:8899/api/v1/chat",
                    help="LM Studio chat endpoint")
    ap.add_argument("--model", default="google/gemma-4-12b-qat")
    ap.add_argument("--reasoning", default="off",
                    help="off | low | medium | high | xhigh | on")
    ap.add_argument("--source-lang", default="English")
    ap.add_argument("--glossary", default=None,
                    help="glossary file; omit to use the built-in AI-domain list")
    ap.add_argument("--no-glossary", action="store_true")
    ap.add_argument("--no-context", action="store_true",
                    help="translate each line in isolation")
    ap.add_argument("--delay", type=float, default=5.0,
                    help="seconds to wait between successful calls")
    ap.add_argument("--max-retries", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--resume", action="store_true",
                    help="reuse valid translations already in the output file")
    ap.add_argument("--test-indices", default=None,
                    help="comma-separated indices to translate, e.g. 1,5,42")
    return ap.parse_args()


def load_existing(path):
    """Read valid translations from an existing bilingual SRT: {index: chinese}."""
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path, encoding="utf-8") as f:
        content = f.read()
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 4:
            continue
        zh = "\n".join(lines[3:]).strip()
        if zh and has_chinese(zh) and not is_echo(zh):
            result[lines[0].strip()] = zh
    return result


def main():
    args = parse_args()

    all_entries = parse_srt(args.input)
    pos_of = {e[0]: i for i, e in enumerate(all_entries)}
    entries = all_entries

    if args.test_indices:
        wanted = {x.strip() for x in args.test_indices.split(",") if x.strip()}
        entries = [e for e in entries if e[0] in wanted]
        print("Test mode: {} selected indices".format(len(entries)), flush=True)

    glossary = [] if args.no_glossary else load_glossary(args.glossary)
    cached = load_existing(args.output) if args.resume else {}

    print("Entries: {} | model: {} | reasoning: {} | glossary: {} terms | resume: {}".format(
        len(entries), args.model, args.reasoning, len(glossary), bool(cached)), flush=True)
    if cached:
        print("Reusing {} already-translated entries".format(len(cached)), flush=True)

    ok = failed = reused = 0
    started = time.time()

    with open(args.output, "w", encoding="utf-8") as f_out:
        for n, (idx, timestamp, text) in enumerate(entries, 1):
            if idx in cached:
                zh, status = cached[idx], "skip"
                reused += 1
            else:
                p = pos_of[idx]
                prev_text = all_entries[p - 1][2] if p > 0 else ""
                next_text = all_entries[p + 1][2] if p + 1 < len(all_entries) else ""
                prompt = build_prompt(text, prev_text, next_text, glossary,
                                      args.source_lang, not args.no_context)
                zh, status = text, "fail"
                for attempt in range(args.max_retries):
                    try:
                        raw = call_server(args.url, args.model, prompt,
                                          args.reasoning, args.timeout)
                        candidate = extract_translation(raw)
                        if candidate and has_chinese(candidate) and not is_echo(candidate):
                            zh, status = candidate, "ok"
                            break
                        print("    [retry {}/{}] no Chinese in answer: {!r}".format(
                            attempt + 1, args.max_retries, raw[:80]), flush=True)
                        time.sleep(2 + attempt * 2)
                    except Exception as exc:
                        backoff = 4 * (2 ** attempt)
                        print("    [retry {}/{}] {} | backoff {}s".format(
                            attempt + 1, args.max_retries, exc, backoff), flush=True)
                        time.sleep(backoff)
                if status == "ok":
                    ok += 1
                else:
                    failed += 1

            f_out.write("{}\n{}\n{}\n{}\n\n".format(idx, timestamp, text, zh))
            f_out.flush()

            elapsed = time.time() - started
            rate = n / elapsed if elapsed else 0
            eta = (len(entries) - n) / rate if rate else 0
            print("[{}/{}] {} [{}] {} -> {} | ETA {:.0f}s".format(
                n, len(entries), idx, status.upper(), text[:40], zh[:24], eta), flush=True)

            if status != "skip" and n < len(entries):
                time.sleep(args.delay)

    print("\nDone in {:.1f}s — translated {}, failed {}, reused {}".format(
        time.time() - started, ok, failed, reused), flush=True)
    print("Output: {}".format(args.output), flush=True)
    if failed:
        print("Re-run with --resume to retry only the failed lines.", flush=True)


if __name__ == "__main__":
    main()

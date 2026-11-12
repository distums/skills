---
name: video-to-bilingual-subtitles
description: Transcribe a video or audio file to an SRT with faster-whisper, then translate it into a bilingual (source + Chinese) SRT and a Chinese-only SRT using a local LM Studio model. Use when the task is to subtitle a recording, produce ASR text from media, or generate Chinese/English dual-language subtitles, especially for long files (30+ minutes) or domain content that needs a glossary.
agent_created: true
---

# Video → Bilingual Subtitles

Turn a media file into three time-aligned SRTs: source-language ASR, bilingual
(source + Chinese), and Chinese-only.

The pipeline is deliberately split into four stages because each one fails in a
different way on long recordings, and each stage can be re-run without redoing the
previous ones.

## When to use

- A video or audio file needs subtitles, ASR text, or a transcript.
- Chinese subtitles are needed for English (or other source-language) content.
- The file is long enough that single-pass transcription would hallucinate.
- Terminology consistency matters (AI, finance, medical, legal vocabulary).

## Prerequisites

| Requirement | Check |
|-------------|-------|
| `ffmpeg` / `ffprobe` on PATH | `ffmpeg -version` |
| `faster-whisper` + CUDA | `python -c "import faster_whisper"` |
| LM Studio server reachable | `curl $URL/api/v1/models` |

`transcribe_chunks.py` needs the interpreter that has `faster-whisper` installed — that
is often a project venv rather than the system Python. `translate_srt.py`,
`make_zh_only.py` and `verify_srt.py` only use the standard library and run anywhere.

The first request to an idle LM Studio server can take over a minute while the model
reloads; a timeout on the opening call is normal and the built-in retry handles it.

Scripts live in `scripts/`. All are standalone and take CLI arguments; run them from
the skill directory or reference them by absolute path.

## Stage 1 — Extract the audio

Keep the audio as its own file so ASR can be re-run without touching the video.

```bash
ffmpeg -i INPUT.mp4 -vn -acodec copy INPUT.aac
```

`-acodec copy` is lossless and takes under a second. If the container's audio codec
cannot be remuxed into `.aac`, re-encode instead:
`-vn -ac 1 -ar 16000 -c:a pcm_s16le INPUT.wav`.

`transcribe_chunks.py` also extracts audio internally, so this stage is optional —
do it anyway when the audio is likely to be reused or the video is very large.

## Stage 2 — Transcribe

```bash
python scripts/transcribe_chunks.py INPUT.mp4 -o OUTPUT.srt \
    --chunk-seconds 300 --model large-v3 --device cuda --compute-type float16 --language en
```

What the script does, and why each part matters:

- **Chunks the audio (default 5 min).** One long pass lets the model loop on silence.
- **Sets `condition_on_previous_text=False`.** Without it a single bad guess is fed
  back into the next window and repeated for hundreds of segments. This is the
  single most important flag.
- **Enables VAD with `no_speech_threshold=0.6`** so silent stretches produce nothing.
- **Offsets timestamps per chunk** using accumulated real chunk durations, so the
  merged SRT is continuous.

Expect roughly 20–40× realtime on a modern GPU: a 42-minute file takes about 2 minutes.

Pass `--language en` (or the actual source language) — auto-detection is less reliable
on short chunks than on the whole file.

## Stage 3 — Translate

```bash
python scripts/translate_srt.py OUTPUT.srt -o OUTPUT_zh.srt \
    --url http://127.0.0.1:8899/api/v1/chat \
    --model google/gemma-4-12b-qat \
    --reasoning off \
    --glossary references/glossary-example.txt \
    --delay 5
```

Non-obvious requirements baked into the script:

- **The endpoint is LM Studio's native API**, `POST /api/v1/chat`, with the body
  `{"model", "input", "reasoning"}`. It is *not* the OpenAI-compatible
  `/v1/chat/completions` shape, and `messages` is rejected with HTTP 400.
- **The response is an `output` array of parts.** Filter to `type == "message"`;
  drop `type == "reasoning"`.
- **Disable reasoning with `"reasoning": "off"`.** Valid values are
  `off | low | medium | high | xhigh | on`. Leaving it on burns ~1200 reasoning
  tokens per line for no quality gain.
- **Send the neighbouring lines as context.** Subtitle entries are sentence
  fragments; translating them in isolation makes the model insert `……` wherever the
  phrase breaks. With context it can resolve the missing words.
- **Validate every answer.** It must contain a CJK character and must not echo the
  prompt. Invalid answers retry with exponential backoff (4s → 64s).
- **Throttle between calls** (`--delay`, default 5s). A single-slot local server
  returns intermittent 403s when pushed.

For a first run on a new model or glossary, probe a handful of lines before
committing to the full file:

```bash
python scripts/translate_srt.py OUTPUT.srt -o probe.srt \
    --test-indices 1,42,69,138 --no-glossary
```

If the run is interrupted, re-run with `--resume`: valid translations already in the
output file are reused, only missing or failed lines are sent again.

### Building a glossary

Copy `references/glossary-example.txt` and edit it. Keep only terms that recur — a
long glossary dilutes attention. Two categories are worth including:

1. **Domain terms with a wrong default sense.** `intelligence` defaults to 情报
   (espionage) rather than 智能 (AI); `bundle` defaults to 卷宗 rather than 套件.
2. **ASR corrections.** Whisper writes `Clod` for `Claude` and `Cloud Code` for
   `Claude Code`; declaring them in the prompt normalises the Chinese side.

## Stage 4 — Derive the Chinese-only file

```bash
python scripts/make_zh_only.py OUTPUT_zh.srt -o OUTPUT_zh_only.srt
```

Drops the source line, keeps index, timestamp and Chinese text. Timestamps stay
identical to the bilingual file, so the two are interchangeable.

## Quality gate

```bash
python scripts/verify_srt.py OUTPUT_zh_only.srt --reference OUTPUT.srt
python scripts/verify_srt.py OUTPUT_zh.srt --bilingual --reference OUTPUT.srt
```

Reports structural errors, missing Chinese, residual `……`, leaked Latin prose, and
timestamp drift against the source SRT. Aim for zero on every counter.

Any surviving `……` means the context window did not supply the missing words. Read
that entry's neighbours and hand-fix the line — with 550 entries there are usually
only a handful, and a targeted manual patch is faster and better than re-running the
whole stage.

## Common failures

See `references/troubleshooting.md` for the full list with causes and fixes. The three
that cost the most time:

| Symptom | Cause | Fix |
|---------|-------|-----|
| Same sentence repeated hundreds of times | `condition_on_previous_text` left on | Disable it, add VAD, chunk the audio |
| Model answers in the source language | Translation-specialised checkpoint resolving the language pair wrongly | Switch to a general instruction-following model |
| `……` mid-sentence | Line translated without context | Pass neighbouring lines as context |

## Output layout

```
INPUT.mp4              original media
INPUT.aac              extracted audio (optional but reusable)
INPUT.srt              source-language ASR
INPUT_zh.srt           bilingual: source line, then Chinese line
INPUT_zh_only.srt      Chinese only
```

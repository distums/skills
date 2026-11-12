# Troubleshooting & Design Notes

Failure modes encountered while building this pipeline, and the fix for each.

## 1. Whisper repeats the same sentence hundreds of times

**Symptom.** The SRT contains the same line, verbatim, from some timestamp onward —
often a line from the opening seconds. A 42-minute video yields 500+ identical entries.

**Cause.** A long silence, music bed, or applause stretch. With
`condition_on_previous_text=True` (the default) the model conditions each window on
its own previous output, so one bad guess is fed back and reinforced.

**Fix.** Transcribe in chunks *and* disable cross-segment conditioning:

```python
model.transcribe(
    chunk,
    vad_filter=True,
    vad_parameters={"threshold": 0.5, "min_silence_duration_ms": 500, "speech_pad_ms": 200},
    condition_on_previous_text=False,
    no_speech_threshold=0.6,
    compression_ratio_threshold=2.4,
)
```

Chunking alone is not enough — the loop also happens inside a single chunk.

## 2. `av.open() got an unexpected keyword argument 'metadata_errors'`

faster-whisper and PyAV version skew. Newer PyAV dropped `metadata_errors`; some
faster-whisper releases still pass it unconditionally. Pin one of the two, or patch
the call site to pass the argument only when `int(av.__version__.split(".")[0]) < 19`.

## 3. MCP transcription tool times out on long files

A 40+ minute file exceeds the tool's request timeout, and the partial work is lost.
Call `faster_whisper` directly from a script instead; that also makes chunk-level
retries possible.

## 4. LM Studio returns 403 intermittently

Transient — the server refuses a request when its parallel slots are busy. The same
input succeeds moments later. Do not treat it as a permanent failure: retry with
exponential backoff (4s → 8s → 16s → 32s → 64s).

## 5. Model answers in the source language instead of Chinese

Some translation-specialised checkpoints (e.g. `translategemma-12b-it` served through
LM Studio) resolve the language pair incorrectly — the template collapses to
`en → en-GB` and the model paraphrases English into English. Retries never help because
the failure is deterministic.

**Fix.** Use a general instruction-following model (e.g. `google/gemma-4-12b-qat`) and
validate every answer: it must contain at least one CJK character and must not be a
paraphrase of the prompt. Retry on failure.

## 6. `……` appears in the middle of a translation

**Symptom.** `我们是专注于为……建设的领先 AI 实验室`

**Cause.** Whisper splits sentences across subtitle entries. The current line ends
mid-phrase (`...focused on building for the`), the continuation lives in the next entry
(`enterprise from day one`). Translating lines in isolation leaves a hole the model
marks with an ellipsis. Telling the model "never use an ellipsis" does not work — it
still needs a placeholder for the missing words.

**Fix.** Pass the neighbouring lines as context and instruct the model to translate
only the current line. The ellipsis disappears because the missing word is now known.

Trade-off: the model may absorb a few words from the next line, producing slight
overlap between adjacent entries. This reads far better than a placeholder.

## 7. Prompt echo contaminates the answer

The model sometimes restates the instruction (in Chinese) before translating. Naive
"take the last line" extraction then captures the echoed instruction.

**Fix.** Split the answer on blank lines, scan segments from last to first, and reject
any segment matching an echo pattern (`您是一位专业的`, `请仅提供中文翻译`, …).

## 8. Terminology drift

`intelligence` → 情报 (intelligence agency) instead of 智能 (artificial intelligence);
`bundle` → 卷宗 instead of 套件. Short subtitle fragments give the model no domain
signal.

**Fix.** Ship a glossary in the prompt. Keep it to the terms that actually recur;
a long glossary dilutes attention and slows generation.

## 9. ASR mangles product names

Whisper transcribes `Claude` as `Clod` and `Claude Code` as `Cloud Code`. State the
correction explicitly in the prompt (`'Clod' and 'Cloud Code' mean Claude and
Claude Code`) — the translator then normalises the Chinese side. The source-language
line keeps the ASR spelling; fix that separately with a find/replace if the bilingual
file must be pristine.

## 10. Cost / throughput reference

Measured on an RTX 3080 Ti, 42-minute 720p video, 550 subtitle entries:

| Stage | Time |
|-------|------|
| Audio extraction (`-c copy`) | < 1 s |
| ASR, `large-v3` + CUDA float16, 5-min chunks | ~2 min |
| Translation, local 12B model, 5 s throttle | ~56 min |

Translation dominates. The 5 s throttle exists to keep a single-slot local server
responsive; on a beefier host it can be lowered, but expect more transient 403s.

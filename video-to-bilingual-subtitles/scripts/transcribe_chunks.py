#!/usr/bin/env python3
"""Transcribe a media file to SRT with faster-whisper, using fixed-length chunks.

Long single-pass transcription makes Whisper loop on silence / music stretches,
emitting the same sentence hundreds of times. Splitting the audio into chunks and
disabling cross-segment conditioning removes that failure mode entirely.

Usage:
    python transcribe_chunks.py INPUT_MEDIA -o OUTPUT.srt \
        [--chunk-seconds 300] [--model large-v3] [--device cuda] \
        [--compute-type float16] [--language en] [--beam-size 5] [--keep-chunks]

Requires: ffmpeg / ffprobe on PATH, faster-whisper installed.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time


def run(cmd):
    """Run a subprocess, exiting with its stderr on failure."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("command failed: {}\n{}".format(" ".join(cmd), proc.stderr[-2000:]))
    return proc.stdout


def media_duration(path):
    out = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ])
    return float(out.strip())


def extract_audio(src, dst):
    """Decode any media container to mono 16 kHz PCM, the format Whisper wants."""
    run([
        "ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", dst,
    ])


def split_audio(wav, out_dir, chunk_seconds):
    """Cut the WAV into fixed-length chunks. PCM can be split with -c copy."""
    pattern = os.path.join(out_dir, "chunk_%04d.wav")
    run([
        "ffmpeg", "-y", "-i", wav, "-f", "segment",
        "-segment_time", str(chunk_seconds), "-c", "copy", pattern,
    ])
    chunks = sorted(glob.glob(os.path.join(out_dir, "chunk_*.wav")))
    if not chunks:
        sys.exit("audio splitting produced no chunks")
    return chunks


def format_timestamp(seconds):
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(hours, minutes, secs, ms)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="video or audio file")
    ap.add_argument("-o", "--output", required=True, help="output SRT path")
    ap.add_argument("--chunk-seconds", type=int, default=300,
                    help="chunk length in seconds (default 300 = 5 min)")
    ap.add_argument("--model", default="large-v3", help="Whisper model name")
    ap.add_argument("--device", default="cuda", help="cuda / cpu / auto")
    ap.add_argument("--compute-type", default="float16",
                    help="float16 / int8 / auto")
    ap.add_argument("--language", default=None,
                    help="source language code, e.g. en. Omit to auto-detect.")
    ap.add_argument("--beam-size", type=int, default=5)
    ap.add_argument("--keep-chunks", action="store_true",
                    help="keep the intermediate WAV chunks for inspection")
    return ap.parse_args()


def main():
    args = parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper is not installed for this interpreter.\n"
                 "Install it (pip install faster-whisper) or run this script with the "
                 "Python that already has it, e.g. a project venv.")

    if not os.path.isfile(args.input):
        sys.exit("input not found: {}".format(args.input))

    duration = media_duration(args.input)
    print("Input duration: {:.1f}s ({:.1f} min)".format(duration, duration / 60), flush=True)

    work_dir = tempfile.mkdtemp(prefix="whisper_chunks_")
    try:
        wav = os.path.join(work_dir, "audio.wav")
        print("Extracting audio -> mono 16 kHz PCM ...", flush=True)
        extract_audio(args.input, wav)

        print("Splitting into {}-second chunks ...".format(args.chunk_seconds), flush=True)
        chunks = split_audio(wav, work_dir, args.chunk_seconds)
        print("{} chunks".format(len(chunks)), flush=True)

        print("Loading model {} on {} ({}) ...".format(
            args.model, args.device, args.compute_type), flush=True)
        t0 = time.time()
        model = WhisperModel(args.model, device=args.device,
                             compute_type=args.compute_type)
        print("Model loaded in {:.1f}s".format(time.time() - t0), flush=True)

        seg_index = 0
        offset = 0.0
        started = time.time()

        with open(args.output, "w", encoding="utf-8") as f_out:
            for i, chunk in enumerate(chunks, 1):
                chunk_duration = media_duration(chunk)
                print("[{}/{}] {} (offset {:.1f}s) ...".format(
                    i, len(chunks), os.path.basename(chunk), offset), flush=True)
                t1 = time.time()

                segments, info = model.transcribe(
                    chunk,
                    language=args.language,
                    beam_size=args.beam_size,
                    temperature=0,
                    vad_filter=True,
                    vad_parameters={
                        "threshold": 0.5,
                        "min_silence_duration_ms": 500,
                        "speech_pad_ms": 200,
                    },
                    # Critical: without this the model can chain a wrong guess
                    # across segments and repeat it.
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                    compression_ratio_threshold=2.4,
                )

                count = 0
                for seg in segments:
                    # VAD's speech_pad_ms can push the last segment of a chunk past
                    # the chunk boundary, which would overlap the first segment of
                    # the next chunk. Clamp to the boundary.
                    rel_start = min(seg.start, chunk_duration)
                    rel_end = min(seg.end, chunk_duration)
                    if rel_end - rel_start < 0.05:
                        continue

                    seg_index += 1
                    count += 1
                    f_out.write("{}\n{} --> {}\n{}\n\n".format(
                        seg_index,
                        format_timestamp(rel_start + offset),
                        format_timestamp(rel_end + offset),
                        seg.text.strip(),
                    ))
                f_out.flush()

                if i == 1:
                    print("    detected language: {} (p={:.2f})".format(
                        info.language, info.language_probability), flush=True)
                print("    {} segments in {:.1f}s".format(count, time.time() - t1), flush=True)

                offset += chunk_duration

        print("\nDone: {} segments in {:.1f}s".format(seg_index, time.time() - started), flush=True)
        print("Output: {}".format(args.output), flush=True)
    finally:
        if args.keep_chunks:
            kept = os.path.abspath("chunks")
            if os.path.isdir(kept):
                shutil.rmtree(kept)
            shutil.copytree(work_dir, kept)
            print("Chunks kept at: {}".format(kept), flush=True)
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

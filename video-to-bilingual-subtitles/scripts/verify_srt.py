#!/usr/bin/env python3
"""Validate an SRT (single-language or bilingual) and report residual defects.

Checks structure (sequential indices, well-formed timestamps), verifies the Chinese
line exists, and flags the two artefacts that survive translation most often:
leftover "……" placeholders and leaked source-language prose.

Usage:
    python verify_srt.py TARGET.srt [--reference SOURCE.srt] [--bilingual]
"""
import argparse
import os
import re
import sys

TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")
ELLIPSIS = re.compile(r"……|\.\.\.$")
LATIN_RUN = re.compile(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}\s+[A-Za-z]{4,}")


def blocks_of(path):
    with open(path, encoding="utf-8") as f:
        return [b.strip() for b in re.split(r"\n\s*\n", f.read().strip()) if b.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="SRT to validate")
    ap.add_argument("--reference", default=None,
                    help="source SRT to compare timestamps against")
    ap.add_argument("--bilingual", action="store_true",
                    help="target holds source + Chinese lines per block")
    args = ap.parse_args()

    if not os.path.isfile(args.target):
        sys.exit("target not found: {}".format(args.target))

    blocks = blocks_of(args.target)
    min_lines = 4 if args.bilingual else 3
    zh_start = 3 if args.bilingual else 2

    structural, no_chinese, ellipsis, latin = [], [], [], []

    for n, block in enumerate(blocks, 1):
        lines = block.split("\n")
        if len(lines) < min_lines:
            structural.append((n, "only {} lines".format(len(lines))))
            continue
        if lines[0].strip() != str(n):
            structural.append((n, "index is {!r}".format(lines[0])))
        if not TIMESTAMP.match(lines[1].strip()):
            structural.append((n, "bad timestamp {!r}".format(lines[1])))
        zh = "\n".join(lines[zh_start:]).strip()
        if not re.search(r"[\u4e00-\u9fff]", zh):
            no_chinese.append((n, zh))
        if ELLIPSIS.search(zh):
            ellipsis.append((n, zh))
        if LATIN_RUN.search(zh):
            latin.append((n, zh))

    mismatch = []
    if args.reference:
        ref = blocks_of(args.reference)
        if len(ref) != len(blocks):
            print("WARNING: entry count differs — target {}, reference {}".format(
                len(blocks), len(ref)))
        for n, (a, b) in enumerate(zip(blocks, ref), 1):
            if a.split("\n")[1].strip() != b.split("\n")[1].strip():
                mismatch.append(n)

    print("File            : {}".format(args.target))
    print("Size            : {:.1f} KB".format(os.path.getsize(args.target) / 1024))
    print("Entries         : {}".format(len(blocks)))
    print("Structural errs : {}".format(len(structural)))
    print("Missing Chinese : {}".format(len(no_chinese)))
    print("Ellipsis left   : {}".format(len(ellipsis)))
    print("Latin run left  : {}".format(len(latin)))
    if args.reference:
        print("Timestamp drift : {}".format(len(mismatch)))

    for label, items in (("structural", structural),
                         ("no Chinese", no_chinese),
                         ("ellipsis", ellipsis),
                         ("latin run", latin)):
        if items:
            print("\n-- {} --".format(label))
            for n, detail in items[:15]:
                print("  [{}] {}".format(n, str(detail)[:90]))
            if len(items) > 15:
                print("  ... {} more".format(len(items) - 15))


if __name__ == "__main__":
    main()

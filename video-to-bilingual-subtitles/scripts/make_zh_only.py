#!/usr/bin/env python3
"""Derive a Chinese-only SRT from a bilingual SRT.

The bilingual file is expected to hold, per block: index / timestamp / source line /
one or more Chinese lines. Everything after the source line is kept.

Usage:
    python make_zh_only.py BILINGUAL.srt -o CHINESE_ONLY.srt
"""
import argparse
import os
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="bilingual SRT")
    ap.add_argument("-o", "--output", required=True, help="Chinese-only SRT to write")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit("input not found: {}".format(args.input))

    with open(args.input, encoding="utf-8") as f:
        content = f.read()

    out = []
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 4:
            continue
        idx, timestamp = lines[0].strip(), lines[1].strip()
        chinese = "\n".join(lines[3:]).strip()
        if chinese:
            out.append("{}\n{}\n{}".format(idx, timestamp, chinese))

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n\n".join(out) + "\n\n")

    print("Wrote {} entries -> {}".format(len(out), args.output))
    print("Size: {:.1f} KB".format(os.path.getsize(args.output) / 1024))


if __name__ == "__main__":
    main()

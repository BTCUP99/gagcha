#!/usr/bin/env python3
"""Print one version's section of CHANGELOG.md, for use as GitHub release notes."""
from pathlib import Path
import re
import sys

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"


def notes(version, text=None):
    text = CHANGELOG.read_text(encoding="utf-8") if text is None else text
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |^\[[^\]]+\]: |\Z)", text, re.S | re.M)
    if not match or not match.group(1).strip():
        raise ValueError(f"CHANGELOG.md 里没有 {version} 的内容")
    return match.group(1).strip()


def main():
    if len(sys.argv) != 2:
        sys.exit("用法：release_notes.py 版本号，例如 0.4.1")
    try:
        print(notes(sys.argv[1]))
    except ValueError as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()

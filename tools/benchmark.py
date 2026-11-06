#!/usr/bin/env python3
"""Report catalog search coverage and top-result accuracy against the phrase benchmark."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "gagcha" / "scripts"))
import action


def top(query, rows):
    q = action.normal(query)
    ranked = sorted(((action.score(q, row), row) for row in rows), key=lambda item: -item[0]) if q else []
    return ranked[0][1] if ranked and ranked[0][0] > 0 else None


def measure(path=ROOT / "tests" / "benchmark" / "phrases.json"):
    rows, trends = action.load("actions.json"), action.load("trends.json")
    action.apply_trends(rows, trends)
    data = json.loads(path.read_text(encoding="utf-8"))
    collections = {}
    for name, phrases in data["collections"].items():
        collections[name] = {"total": len(phrases), "missed": [p for p in phrases if top(p, rows) is None]}
    wrong = {}
    for phrase, expected in data["must_route"].items():
        found = top(phrase, rows)
        if not found or found["id"] != expected:
            wrong[phrase] = found["id"] if found else None
    return collections, wrong


def main():
    collections, wrong = measure()
    for name, result in collections.items():
        hits = result["total"] - len(result["missed"])
        print(f"{name}: {hits}/{result['total']}（{hits * 100 / result['total']:.1f}%）")
        if result["missed"]:
            print("  未命中：" + " ".join(result["missed"]))
    print("首位错误：" + (json.dumps(wrong, ensure_ascii=False) if wrong else "无"))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())

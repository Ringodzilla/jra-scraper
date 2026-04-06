from __future__ import annotations

import argparse
import re
from pathlib import Path

BANNED_PATTERNS = [
    r"\bresult\b",
    r"\bpayout\b",
    r"\bfinish_position\b",
    r"\brank_after\b",
    r"\bfuture_[a-zA-Z0-9_]*\b",
]

DEFAULT_TARGETS = [
    "analysis/ev.py",
    "strategy/betting.py",
    "src/features.py",
    "src/model.py",
    "src/betting.py",
]


def find_leakage(paths: list[Path]) -> list[str]:
    regexes = [re.compile(p, flags=re.IGNORECASE) for p in BANNED_PATTERNS]
    findings: list[str] = []

    for path in paths:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "leak-check: ignore" in line:
                continue
            for rgx in regexes:
                if rgx.search(line):
                    findings.append(f"{path}:{i}:{line.strip()}")
                    break
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check strategy code for obvious data leakage keywords.")
    parser.add_argument("paths", nargs="*", default=DEFAULT_TARGETS)
    args = parser.parse_args()

    paths = [Path(p) for p in args.paths]
    findings = find_leakage(paths)

    if findings:
        print("Leakage risk keywords found:")
        for f in findings:
            print(f"- {f}")
        raise SystemExit(1)

    print("Leakage check passed.")


if __name__ == "__main__":
    main()

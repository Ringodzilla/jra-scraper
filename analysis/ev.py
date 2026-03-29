from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

@dataclass
class EVWeights:
position: float = 0.45
last_3f: float = 0.25
popularity_gap: float = 0.30

def load_rows(path: Path) -> list[dict[str, str]]:
with path.open("r", encoding="utf-8", newline="") as f:
rows = list(csv.DictReader(f))
return [_sanitize_row(r) for r in rows]

def compute_ev(
rows: list[dict[str, str]],
weights: EVWeights | None = None,
) -> list[dict[str, str | None]]:
weights = weights or EVWeights()
scored: list[dict[str, str | None]] = []

```
for row in rows:
    row = _sanitize_row(row)

    pos = _to_float(row.get("position"))
    last3f = _to_float(row.get("last_3f"))
    pop = _to_float(row.get("popularity"))
    odds = _to_float(row.get("odds"))

    pos_score = 1.0 / pos if pos else None
    last3f_score = 1.0 / last3f if last3f else None
    gap_score = ((pop - 1.0) / pop) if pop else None

    model_prob = _weighted_mean(
        [
            (pos_score, weights.position),
            (last3f_score, weights.last_3f),
            (gap_score, weights.popularity_gap),
        ]
    )

    fair_odds = (1.0 / model_prob) if model_prob else None
    ev = (odds * model_prob) if odds and model_prob else None

    new_row = dict(row)
    new_row["model_prob"] = _fmt(model_prob)
    new_row["fair_odds"] = _fmt(fair_odds)
    new_row["ev"] = _fmt(ev)
    scored.append(new_row)

scored.sort(key=lambda r: _to_float(str(r.get("ev"))) or 0.0, reverse=True)
return scored
```

def save_ev(rows: list[dict[str, str | None]], out_path: Path) -> None:
out_path.parent.mkdir(parents=True, exist_ok=True)
if not rows:
out_path.write_text("", encoding="utf-8")
return

```
keys = list(rows[0].keys())
with out_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
```

def _sanitize_row(row: dict[str, str]) -> dict[str, str]:
out: dict[str, str] = {}
for k, v in row.items():
if v in (None, "", "None"):
out[k] = "0"
continue

```
    f = _to_float(str(v))
    if f is not None and not math.isfinite(f):
        out[k] = "0"
    else:
        out[k] = str(v)

return out
```

def _weighted_mean(pairs: list[tuple[float | None, float]]) -> float | None:
total_w = 0.0
total_v = 0.0
for value, weight in pairs:
if value is None:
continue
total_v += value * weight
total_w += weight

```
if total_w == 0:
    return None

return total_v / total_w
```

def _to_float(value: str | None) -> float | None:
if value in (None, "", "None"):
return None
try:
return float(value)
except ValueError:
return None

def _fmt(value: float | None) -> str | None:
if value is None:
return None
return f"{value:.4f}".rstrip("0").rstrip(".")

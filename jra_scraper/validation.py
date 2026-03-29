from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime

OUTPUT_COLUMNS = [
    "row_id",
    "race_id",
    "horse_id",
    "horse_name",
    "run_index",
    "date",
    "race_name",
    "course",
    "distance",
    "position",
    "time",
    "weight",
    "jockey",
    "pace",
    "last_3f",
    "track_condition",
    "weather",
    "passing_order",
    "odds",
    "popularity",
]


def validate_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        normalized = _normalize_row(row)
        normalized["row_id"] = build_row_id(normalized)
        if normalized["row_id"] in seen:
            continue
        seen.add(normalized["row_id"])
        deduped.append(normalized)

    by_horse: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in deduped:
        by_horse[(row["race_id"], row["horse_id"] or row["horse_name"])].append(row)

    out: list[dict[str, str]] = []
    for group_rows in by_horse.values():
        sorted_rows = sorted(group_rows, key=lambda r: _safe_int(r["run_index"]))
        out.extend(sorted_rows[:5])

    return out


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    data = {col: str(row.get(col, "")).strip() for col in OUTPUT_COLUMNS if col != "row_id"}

    data["horse_id"] = _normalize_horse_id(data["horse_id"], data["horse_name"])
    data["date"] = _normalize_date(data["date"])
    data["distance"] = _normalize_int(data["distance"])
    data["position"] = _normalize_int(data["position"])
    data["weight"] = _normalize_float(data["weight"])
    data["time"] = _normalize_time(data["time"])
    data["pace"] = _normalize_time(data["pace"])
    data["last_3f"] = _normalize_float(data["last_3f"])
    data["passing_order"] = _normalize_passing_order(data["passing_order"])
    data["odds"] = _normalize_float(data["odds"])
    data["popularity"] = _normalize_int(data["popularity"])

    return data


def build_row_id(row: dict[str, str]) -> str:
    stable_keys = ["race_id", "horse_id", "run_index", "date", "race_name", "position", "odds"]
    payload = "|".join(str(row.get(k, "")).strip() for k in stable_keys)
    return f"row_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:20]}"


def _normalize_horse_id(raw_id: str, horse_name: str) -> str:
    if raw_id:
        return raw_id
    cleaned = re.sub(r"\s+", "_", horse_name.strip().lower())
    cleaned = re.sub(r"[^a-z0-9_\-ぁ-んァ-ヶ一-龠]", "", cleaned)
    return cleaned or "unknown_horse"


def _normalize_date(value: str) -> str:
    if not value:
        return ""
    value = value.replace(".", "/").replace("-", "/")
    for fmt in ("%Y/%m/%d", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _normalize_int(value: str) -> str:
    m = re.search(r"-?\d+", value or "")
    return m.group(0) if m else ""


def _normalize_float(value: str) -> str:
    m = re.search(r"-?\d+(?:\.\d+)?", value or "")
    if not m:
        return ""
    return f"{float(m.group(0)):.1f}".rstrip("0").rstrip(".")


def _normalize_time(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if ":" in value:
        try:
            minute, sec = value.split(":", 1)
            total = int(minute) * 60 + float(sec)
            return f"{total:.1f}".rstrip("0").rstrip(".")
        except ValueError:
            return value
    return _normalize_float(value)


def _normalize_passing_order(value: str) -> str:
    if not value:
        return ""
    parts = [p for p in re.split(r"[-→]", value) if p.strip()]
    if not parts:
        return ""
    return _normalize_int(parts[-1])


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 999
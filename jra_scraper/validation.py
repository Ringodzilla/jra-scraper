from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import re
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_pandas():
    if importlib.util.find_spec("pandas") is None:
        return None
    return importlib.import_module("pandas")

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
    "margin",
    "weight",
    "jockey",
    "pace",
    "last_3f",
    "passing_order",
    "corner_4",
    "track_condition",
    "weather",
    "odds",
    "popularity",
    "last3f_rank",
    "last3f_diff",
    "last3f_score",
    "last3f_top_flag",
    "expected_position",
    "style",
    "pace_maker_flag",
    "race_pace",
    "field_size",
    "trouble_flag",
    "odds_rank",
    "performance_rank",
    "gap_index",
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

    return _with_features(out)


def _normalize_row(row: dict[str, str]) -> dict[str, str]:
    data = {col: str(row.get(col, "")).strip() for col in OUTPUT_COLUMNS if col != "row_id"}

    data["horse_id"] = _normalize_horse_id(data["horse_id"], data["horse_name"])
    data["date"] = _normalize_date(data["date"])
    data["distance"] = _normalize_int(data["distance"])
    data["position"] = _normalize_int(data["position"])
    data["margin"] = _normalize_float(data["margin"])
    data["weight"] = _normalize_float(data["weight"])
    data["time"] = _normalize_time(data["time"])
    data["pace"] = parse_pace(data["pace"])
    data["last_3f"] = parse_last3f(data["last_3f"])
    data["passing_order"] = parse_passing_order(data["passing_order"])
    data["corner_4"] = data["passing_order"]
    data["odds"] = _normalize_float(data["odds"])
    data["popularity"] = _normalize_int(data["popularity"])
    data["last3f_rank"] = _normalize_int(data.get("last3f_rank", ""))
    data["last3f_diff"] = _normalize_float(data.get("last3f_diff", ""))
    data["last3f_score"] = _normalize_float(data.get("last3f_score", ""))
    data["last3f_top_flag"] = _normalize_int(data.get("last3f_top_flag", ""))
    data["expected_position"] = _normalize_float(data.get("expected_position", ""))
    data["style"] = str(data.get("style", "")).strip()
    data["pace_maker_flag"] = _normalize_int(data.get("pace_maker_flag", ""))
    data["race_pace"] = str(data.get("race_pace", "")).strip()
    data["field_size"] = _normalize_int(data.get("field_size", ""))
    data["trouble_flag"] = _normalize_int(data.get("trouble_flag", ""))
    data["odds_rank"] = _normalize_int(data.get("odds_rank", ""))
    data["performance_rank"] = _normalize_int(data.get("performance_rank", ""))
    data["gap_index"] = _normalize_int(data.get("gap_index", ""))

    return data


def parse_last3f(value: str) -> str:
    return _normalize_float(value)


def parse_passing_order(value: str) -> str:
    return _normalize_passing_order(value)


def parse_pace(value: str) -> str:
    value = (value or "").strip()
    normalized = _normalize_time(value)
    return normalized if normalized else value


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


def _with_features(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return rows
    pd = _get_pandas()
    if pd is None:
        logger.warning("pandas is not available; using non-pandas feature pipeline")
        return _with_features_no_pandas(rows)
    df = pd.DataFrame(rows)
    df = compute_last3f_features(df)
    df = compute_position_features(df)
    df = compute_race_features(df)
    df = compute_ev_features(df)
    return df.to_dict(orient="records")


def compute_last3f_features(df):
    pd = _get_pandas()
    if pd is None:
        return df
    df = df.copy()
    df["last_3f_num"] = _to_numeric_series(df["last_3f"])
    df["pace_num"] = _to_numeric_series(df["pace"])
    df["passing_order_num"] = _to_numeric_series(df["passing_order"])

    df["last3f_rank"] = (
        df.groupby("race_id")["last_3f_num"]
        .rank(method="min", ascending=True, na_option="keep")
    )
    race_mean_last3f = df.groupby("race_id")["last_3f_num"].transform("mean")
    df["last3f_diff"] = race_mean_last3f - df["last_3f_num"]

    race_pace_mean = df.groupby("race_id")["pace_num"].transform("mean")
    pace_fast = race_pace_mean <= 34.5
    pace_slow = race_pace_mean >= 36.5

    pace_label = pd.Series("mid", index=df.index)
    pace_label = pace_label.where(~pace_fast, "fast")
    pace_label = pace_label.where(~pace_slow, "slow")
    df["race_pace"] = pace_label

    score = df["last3f_diff"].copy()
    score = score.where(~pace_fast, score * 1.5)
    score = score.where(~pace_slow, score * 0.7)
    score = score.where(df["passing_order_num"].isna() | (df["passing_order_num"] > 5), score + 1.5)
    score = score.where(df["passing_order_num"].isna() | (df["passing_order_num"] < 10), score - 1.0)
    df["last3f_score"] = score
    df["last3f_top_flag"] = (df["last3f_rank"] == 1).astype("Int64")

    missing_mask = df["last_3f_num"].isna()
    df.loc[missing_mask, ["last3f_rank", "last3f_diff", "last3f_score", "last3f_top_flag"]] = None

    df["last3f_rank"] = df["last3f_rank"].map(_fmt_int)
    df["last3f_diff"] = df["last3f_diff"].map(_fmt_float)
    df["last3f_score"] = df["last3f_score"].map(_fmt_float)
    df["last3f_top_flag"] = df["last3f_top_flag"].map(_fmt_int)

    return df.drop(columns=["last_3f_num", "pace_num", "passing_order_num"])


def compute_position_features(df):
    pd = _get_pandas()
    if pd is None:
        return df
    df = df.copy()
    df["passing_order_num"] = pd.to_numeric(df["passing_order"], errors="coerce")
    df["expected_position_num"] = df.groupby(["race_id", "horse_id"])["passing_order_num"].transform("mean")

    df["expected_position"] = df["expected_position_num"].map(_fmt_float)
    style = pd.Series("追込", index=df.index)
    style = style.where(df["expected_position_num"] > 10, "差し")
    style = style.where(df["expected_position_num"] > 6, "先行")
    style = style.where(df["expected_position_num"] > 3, "逃げ")
    style = style.where(df["expected_position_num"].isna(), "")
    df["style"] = style

    return df.drop(columns=["passing_order_num", "expected_position_num"])


def compute_race_features(df):
    pd = _get_pandas()
    if pd is None:
        return df
    df = df.copy()
    nige_horses = (
        df[df["style"] == "逃げ"]
        .groupby("race_id")["horse_id"]
        .nunique()
    )
    race_style = df["race_id"].map(nige_horses).fillna(0)
    df["pace_maker_flag"] = (race_style >= 2).astype("Int64").map(_fmt_int)

    race_pace = pd.Series("slow", index=df.index)
    race_pace = race_pace.where(race_style <= 0, "mid")
    race_pace = race_pace.where(race_style < 2, "fast")
    if "race_pace" in df.columns:
        df["race_pace"] = df["race_pace"].where(df["race_pace"].astype(str).str.len() > 0, race_pace)
    else:
        df["race_pace"] = race_pace
    return df


def compute_ev_features(df):
    pd = _get_pandas()
    if pd is None:
        return df
    df = df.copy()
    df["odds_num"] = pd.to_numeric(df["odds"], errors="coerce")
    df["position_num"] = pd.to_numeric(df["position"], errors="coerce")
    df["passing_order_num"] = pd.to_numeric(df["passing_order"], errors="coerce")
    df["last3f_rank_num"] = pd.to_numeric(df["last3f_rank"], errors="coerce")

    df["odds_rank"] = df.groupby("race_id")["odds_num"].rank(method="min", ascending=True, na_option="keep")
    df["performance_rank"] = df.groupby("race_id")["position_num"].rank(method="min", ascending=True, na_option="keep")
    df["gap_index"] = df["performance_rank"] - df["odds_rank"]

    trouble_cond_1 = (df["last3f_rank_num"] <= 3) & (df["position_num"] > 5)
    trouble_cond_2 = (df["passing_order_num"] >= 10) & (df["last3f_rank_num"] == 1)
    df["trouble_flag"] = (trouble_cond_1 | trouble_cond_2).astype("Int64")

    df["odds_rank"] = df["odds_rank"].map(_fmt_int)
    df["performance_rank"] = df["performance_rank"].map(_fmt_int)
    df["gap_index"] = df["gap_index"].map(_fmt_int)
    df["trouble_flag"] = df["trouble_flag"].map(_fmt_int)

    return df.drop(columns=["odds_num", "position_num", "passing_order_num", "last3f_rank_num"])


def _to_numeric_series(series):
    pd = _get_pandas()
    if pd is None:
        return series
    return pd.to_numeric(series, errors="coerce")


def _with_features_no_pandas(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = _with_last3f_features_fallback(rows)
    rows = _with_position_features_fallback(rows)
    rows = _with_race_features_fallback(rows)
    rows = _with_ev_features_fallback(rows)
    return rows


def _with_last3f_features_fallback(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["race_id"]].append(row)

    for race_rows in grouped.values():
        vals = [_to_float(r.get("last_3f", "")) for r in race_rows]
        valid_vals = [v for v in vals if v is not None]
        avg = (sum(valid_vals) / len(valid_vals)) if valid_vals else None
        sorted_unique = sorted(set(valid_vals))
        rank_map = {v: i + 1 for i, v in enumerate(sorted_unique)}

        pace_vals = [_to_float(r.get("pace", "")) for r in race_rows]
        valid_pace = [v for v in pace_vals if v is not None]
        pace_avg = (sum(valid_pace) / len(valid_pace)) if valid_pace else None
        race_pace = "mid"
        pace_mult = 1.0
        if pace_avg is not None and pace_avg <= 34.5:
            race_pace = "fast"
            pace_mult = 1.5
        elif pace_avg is not None and pace_avg >= 36.5:
            race_pace = "slow"
            pace_mult = 0.7

        for row in race_rows:
            row["race_pace"] = race_pace
            last3f = _to_float(row.get("last_3f", ""))
            if last3f is None or avg is None:
                row["last3f_rank"] = ""
                row["last3f_diff"] = ""
                row["last3f_score"] = ""
                row["last3f_top_flag"] = ""
                continue
            diff = avg - last3f
            score = diff * pace_mult
            passing = _safe_int_or_none(row.get("passing_order", ""))
            if passing is not None and passing <= 5:
                score += 1.5
            elif passing is not None and passing >= 10:
                score -= 1.0
            rank = rank_map[last3f]
            row["last3f_rank"] = str(rank)
            row["last3f_diff"] = _fmt_float(diff)
            row["last3f_score"] = _fmt_float(score)
            row["last3f_top_flag"] = "1" if rank == 1 else "0"
    return rows


def _with_position_features_fallback(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_horse: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_horse[(row["race_id"], row["horse_id"])].append(row)

    for key_rows in by_horse.values():
        vals = [_safe_int_or_none(r.get("passing_order")) for r in key_rows]
        valid = [v for v in vals if v is not None]
        if not valid:
            for row in key_rows:
                row["expected_position"] = ""
                row["style"] = ""
            continue
        avg = sum(valid) / len(valid)
        if avg <= 3:
            style = "逃げ"
        elif avg <= 6:
            style = "先行"
        elif avg <= 10:
            style = "差し"
        else:
            style = "追込"
        for row in key_rows:
            row["expected_position"] = _fmt_float(avg)
            row["style"] = style
    return rows


def _with_race_features_fallback(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["race_id"]].append(row)
    for race_rows in grouped.values():
        nige_horses = {r.get("horse_id") for r in race_rows if r.get("style") == "逃げ" and r.get("horse_id")}
        nige_cnt = len(nige_horses)
        pace_maker = "1" if nige_cnt >= 2 else "0"
        race_pace = "fast" if nige_cnt >= 2 else ("mid" if nige_cnt == 1 else "slow")
        for row in race_rows:
            row["pace_maker_flag"] = pace_maker
            if not row.get("race_pace"):
                row["race_pace"] = race_pace
    return rows


def _with_ev_features_fallback(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["race_id"]].append(row)

    for race_rows in grouped.values():
        odds_sorted = sorted(
            [(_to_float(r.get("odds")), idx) for idx, r in enumerate(race_rows) if _to_float(r.get("odds")) is not None],
            key=lambda x: x[0],
        )
        pos_sorted = sorted(
            [(_to_float(r.get("position")), idx) for idx, r in enumerate(race_rows) if _to_float(r.get("position")) is not None],
            key=lambda x: x[0],
        )
        odds_rank = {idx: rank + 1 for rank, (_, idx) in enumerate(odds_sorted)}
        perf_rank = {idx: rank + 1 for rank, (_, idx) in enumerate(pos_sorted)}

        for idx, row in enumerate(race_rows):
            orank = odds_rank.get(idx)
            prank = perf_rank.get(idx)
            row["odds_rank"] = str(orank) if orank is not None else ""
            row["performance_rank"] = str(prank) if prank is not None else ""
            if orank is not None and prank is not None:
                row["gap_index"] = str(prank - orank)
            else:
                row["gap_index"] = ""

            last_rank = _safe_int_or_none(row.get("last3f_rank"))
            pos = _safe_int_or_none(row.get("position"))
            passing = _safe_int_or_none(row.get("passing_order"))
            trouble = 0
            if last_rank is not None and pos is not None and last_rank <= 3 and pos > 5:
                trouble = 1
            if last_rank == 1 and passing is not None and passing >= 10:
                trouble = 1
            row["trouble_flag"] = str(trouble)
    return rows


def _fmt_int(value: object) -> str:
    if value is None:
        return ""
    try:
        if value != value:  # nan
            return ""
        return str(int(float(value)))
    except (TypeError, ValueError):
        return ""


def _fmt_float(value: object) -> str:
    if value is None:
        return ""
    try:
        f = float(value)
        if f != f:  # nan
            return ""
        return f"{f:.3f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""


def _to_float(value: str | None) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _safe_int_or_none(value: str | None) -> int | None:
    if value in (None, "", "None"):
        return None
    try:
        return int(float(str(value)))
    except ValueError:
        return None


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 999


def build_race_info_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return []
    race_info: dict[str, dict[str, str]] = {}
    for row in rows:
        race_id = row.get("race_id", "")
        if not race_id:
            continue
        if race_id not in race_info:
            race_info[race_id] = {
                "race_id": race_id,
                "date": row.get("date", ""),
                "race_name": row.get("race_name", ""),
                "course": row.get("course", ""),
                "distance": row.get("distance", ""),
                "field_size": row.get("field_size", ""),
                "race_pace": row.get("race_pace", ""),
                "pace_maker_flag": row.get("pace_maker_flag", ""),
                "track_condition": row.get("track_condition", ""),
                "weather": row.get("weather", ""),
            }
            continue
        current = race_info[race_id]
        for key in ("field_size", "race_pace", "pace_maker_flag", "track_condition", "weather"):
            if not current.get(key) and row.get(key):
                current[key] = row[key]

    return [race_info[k] for k in sorted(race_info.keys())]

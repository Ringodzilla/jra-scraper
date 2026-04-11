from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class ModelWeights:
    ability: float = 0.42
    course: float = 0.14
    pace: float = 0.16
    weight: float = 0.08
    jockey: float = 0.08
    market: float = 0.12
    temperature: float = 1.15
    market_shrink: float = 0.25


def estimate_win_probs(rows: list[dict], weights: ModelWeights | None = None) -> list[dict]:
    weights = weights or ModelWeights()
    by_race: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_race[str(row["race_id"])].append(row)

    out: list[dict] = []
    for race_id, group in by_race.items():
        scored_group = [_score_row(row, weights) for row in group]
        raw_probs = _softmax([float(row["model_score"]) * weights.temperature for row in scored_group])
        market_probs = _market_probs(scored_group)

        blended_probs = []
        for idx, row in enumerate(scored_group):
            blended = raw_probs[idx]
            if market_probs:
                blended = ((1.0 - weights.market_shrink) * raw_probs[idx]) + (weights.market_shrink * market_probs[idx])
            blended_probs.append(blended)

        total_prob = sum(blended_probs) or 1.0
        blended_probs = [value / total_prob for value in blended_probs]

        for row, prob in zip(scored_group, blended_probs):
            odds = _to_float(row.get("current_odds") or row.get("win_odds"), 0.0)
            fair_odds = (1.0 / prob) if prob > 0 else 0.0
            predicted_structural = _predict_structural_odds(row, current_odds=odds, fair_odds=fair_odds)
            predicted_live = _predict_live_odds(row, current_odds=odds, fallback_odds=predicted_structural)
            predicted_odds, prediction_source = _select_predicted_odds(
                row,
                structural_odds=predicted_structural,
                live_odds=predicted_live,
            )

            ev_current = prob * odds if odds > 0 else 0.0
            ev_predicted_structural = prob * predicted_structural if predicted_structural > 0 else 0.0
            ev_predicted_live = prob * predicted_live if predicted_live > 0 else 0.0
            ev_predicted = prob * predicted_odds if predicted_odds > 0 else 0.0
            odds_gap = predicted_odds - odds if odds > 0 else 0.0
            odds_gap_ratio = (odds_gap / odds) if odds > 0 else 0.0
            ev_gap = ev_predicted - ev_current if ev_current > 0 else 0.0
            ev_gap_ratio = (ev_gap / ev_current) if ev_current > 0 else 0.0

            out.append(
                {
                    **row,
                    "current_odds": _fmt(odds),
                    "win_odds": _fmt(odds),
                    "predicted_odds_structural": _fmt(predicted_structural),
                    "predicted_odds_live": _fmt(predicted_live),
                    "predicted_odds": _fmt(predicted_odds),
                    "predicted_odds_source": prediction_source,
                    "win_prob": _fmt(prob),
                    "fair_odds": _fmt(fair_odds),
                    "ev": _fmt(ev_current),
                    "ev_win": _fmt(ev_current),
                    "ev_current": _fmt(ev_current),
                    "ev_predicted_structural": _fmt(ev_predicted_structural),
                    "ev_predicted_live": _fmt(ev_predicted_live),
                    "ev_predicted": _fmt(ev_predicted),
                    "odds_gap": _fmt(odds_gap),
                    "odds_gap_ratio": _fmt(odds_gap_ratio),
                    "ev_delta": _fmt(ev_gap),
                    "ev_delta_ratio": _fmt(ev_gap_ratio),
                }
            )

    out.sort(
        key=lambda row: (
            str(row.get("race_id", "")),
            -_to_float(row.get("ev"), 0.0),
            -_to_float(row.get("win_prob"), 0.0),
        )
    )
    return out


def _score_row(row: dict, weights: ModelWeights) -> dict:
    out = dict(row)
    ability_score = _to_float(out.get("ability_score"), 0.0)
    course_score = _to_float(out.get("course_score"), 0.0)
    pace_score = _to_float(out.get("pace_score"), 0.0)
    weight_score = _to_float(out.get("weight_score"), 0.0)
    jockey_score = _to_float(out.get("jockey_score"), 0.0)
    market_score = _to_float(out.get("market_support"), 0.0)

    out["model_score"] = _fmt(
        (weights.ability * ability_score)
        + (weights.course * course_score)
        + (weights.pace * pace_score)
        + (weights.weight * weight_score)
        + (weights.jockey * jockey_score)
        + (weights.market * market_score)
    )
    return out


def _market_probs(rows: list[dict]) -> list[float]:
    implied = []
    for row in rows:
        odds = _to_float(row.get("current_odds") or row.get("win_odds"), 0.0)
        implied.append((1.0 / odds) if odds > 0 else 0.0)
    total = sum(implied)
    if total <= 0:
        return []
    return [value / total for value in implied]


def _predict_structural_odds(row: dict, *, current_odds: float, fair_odds: float) -> float:
    if current_odds <= 0:
        return 0.0

    avg_popularity = _to_float(row.get("avg_popularity"), 0.0)
    current_popularity = _to_float(
        row.get("popularity_latest") or row.get("current_popularity"),
        avg_popularity or 0.0,
    )
    popularity_gap = _to_float(row.get("popularity_gap"), 0.0)
    if popularity_gap == 0.0 and avg_popularity > 0 and current_popularity > 0:
        popularity_gap = current_popularity - avg_popularity
    popularity_factor = _clamp(1.0 + (0.030 * popularity_gap), 0.84, 1.16)

    days_since_last_run = _to_float(row.get("days_since_last_run"), 35.0)
    time_signal = (days_since_last_run - 35.0) / 120.0
    time_factor = _clamp(1.0 + (0.5 * time_signal), 0.94, 1.10)

    avg_odds = _to_float(row.get("avg_odds"), current_odds)
    volatility = _to_float(row.get("odds_volatility"), 0.0)
    history_count = _to_float(row.get("history_count"), 0.0)
    anchor_weight = _clamp(0.16 + (0.04 * min(history_count, 5.0)) + (0.10 * volatility), 0.14, 0.40)

    adjusted = current_odds * popularity_factor * time_factor
    if fair_odds > 0:
        adjusted = ((1.0 - anchor_weight) * adjusted) + (anchor_weight * fair_odds)
    if avg_odds > 0:
        adjusted = (0.82 * adjusted) + (0.18 * avg_odds)

    lower = max(1.05, min(current_odds, fair_odds if fair_odds > 0 else current_odds) * 0.65)
    upper_anchor = max(current_odds, fair_odds if fair_odds > 0 else current_odds)
    upper = max(lower + 0.01, upper_anchor * 1.45)
    return _clamp(adjusted, lower, upper)


def _predict_live_odds(row: dict, *, current_odds: float, fallback_odds: float) -> float:
    latest_odds = _to_float(row.get("odds_latest"), current_odds or fallback_odds)
    if latest_odds <= 0:
        return fallback_odds

    sample_count = _to_float(row.get("odds_snapshot_count"), 0.0)
    span_minutes = _to_float(row.get("odds_span_minutes"), 0.0)
    range_ratio = _to_float(row.get("odds_range_ratio"), 0.0)
    slope_recent = _to_float(row.get("odds_slope_recent"), 0.0)
    slope_full = _to_float(row.get("odds_slope_full"), 0.0)
    popularity_change = _to_float(row.get("popularity_change"), 0.0)
    odds_min = _to_float(row.get("odds_min"), latest_odds)
    odds_max = _to_float(row.get("odds_max"), latest_odds)

    confidence = _live_confidence(sample_count, span_minutes)
    trend_projection = _clamp((0.65 * slope_recent) + (0.35 * slope_full), -0.25, 0.25)
    popularity_factor = _clamp(1.0 + (0.025 * popularity_change), 0.88, 1.18)
    range_factor = _clamp(1.0 + (0.18 * range_ratio), 0.92, 1.15)

    projected = latest_odds * (1.0 + (trend_projection * confidence)) * popularity_factor * range_factor
    projected = ((1.0 - (0.20 * confidence)) * projected) + ((0.20 * confidence) * fallback_odds)

    lower = max(1.05, min(latest_odds, odds_min) * 0.88)
    upper = max(lower + 0.01, max(latest_odds, odds_max, fallback_odds) * 1.12)
    return _clamp(projected, lower, upper)


def _select_predicted_odds(
    row: dict,
    *,
    structural_odds: float,
    live_odds: float,
) -> tuple[float, str]:
    sample_count = _to_float(row.get("odds_snapshot_count"), 0.0)
    span_minutes = _to_float(row.get("odds_span_minutes"), 0.0)
    latest_odds = _to_float(row.get("odds_latest"), 0.0)
    if latest_odds > 0 and sample_count >= 3 and span_minutes >= 5.0:
        return live_odds, "live"
    return structural_odds, "structural"


def _live_confidence(sample_count: float, span_minutes: float) -> float:
    sample_term = _clamp((sample_count - 2.0) / 4.0, 0.0, 1.0)
    span_term = _clamp(span_minutes / 45.0, 0.0, 1.0)
    return _clamp((0.55 * sample_term) + (0.45 * span_term), 0.0, 1.0)


def _softmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    maximum = max(scores)
    exps = [math.exp(score - maximum) for score in scores]
    total = sum(exps)
    return [value / total for value in exps] if total > 0 else [0.0 for _ in scores]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _to_float(value: object, default: float = 0.0) -> float:
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

from __future__ import annotations

from collections import defaultdict
import math


def generate_tickets(
    ev_rows: list[dict[str, object]],
    mode: str = "balanced",
    *,
    bankroll_per_race: int = 1000,
    min_ev: float = 1.03,
    min_wide_ev: float = 1.01,
    max_tickets_per_race: int = 2,
    max_wide_tickets_per_race: int = 2,
    kelly_fraction: float = 0.33,
    prefer_wide: bool = False,
) -> dict[str, object]:
    by_race: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in ev_rows:
        by_race[str(row.get("race_id", ""))].append(row)

    races: list[dict[str, object]] = []
    flat_tickets: list[dict[str, object]] = []
    core: list[dict[str, object]] = []
    partner: list[dict[str, object]] = []
    longshots: list[dict[str, object]] = []

    per_race_limit = 3 if mode == "aggressive" else max_tickets_per_race

    for race_id in sorted(by_race.keys()):
        ranked = sorted(
            by_race[race_id],
            key=lambda row: (_to_float(row.get("ev")), _to_float(row.get("win_prob"))),
            reverse=True,
        )
        enriched = _enrich_rows_for_multi_bet(ranked)
        win_candidates = [
            row
            for row in enriched
            if _to_float(row.get("ev")) >= min_ev and _to_float(row.get("current_odds")) > 0
        ]
        wide_candidates = _build_wide_candidates(
            enriched,
            bankroll_per_race=bankroll_per_race,
            min_wide_ev=min_wide_ev,
            kelly_fraction=kelly_fraction,
        )

        race_tickets: list[dict[str, object]] = []
        win_tickets = [
            ticket
            for row in win_candidates[:per_race_limit]
            if (ticket := _build_win_ticket(row, bankroll_per_race=bankroll_per_race, kelly_fraction=kelly_fraction)) is not None
        ]
        wide_limit = min(max_wide_tickets_per_race, per_race_limit)
        win_limit = max(0, per_race_limit - wide_limit)

        if prefer_wide:
            race_tickets.extend(wide_candidates[:wide_limit])
            if _has_win_standout(enriched):
                race_tickets.extend(win_tickets[: max(1, win_limit)])
            elif not race_tickets:
                race_tickets.extend(win_tickets[:1])
        else:
            race_tickets.extend(win_tickets[:per_race_limit])
            if len(race_tickets) < per_race_limit:
                race_tickets.extend(wide_candidates[: per_race_limit - len(race_tickets)])

        race_tickets = race_tickets[:per_race_limit]
        race_tickets = _rebalance_race_stakes(race_tickets, bankroll_per_race=bankroll_per_race)
        flat_tickets.extend(race_tickets)

        place_ranked = sorted(
            enriched,
            key=lambda row: (_to_float(row.get("place_prob")), _to_float(row.get("win_prob"))),
            reverse=True,
        )
        race_core = [_horse_summary(row) for row in place_ranked[:2] if _to_float(row.get("place_prob")) >= 0.22]
        race_partner = [_horse_summary(row) for row in place_ranked[2:4] if _to_float(row.get("place_prob")) >= 0.16]
        race_long = [
            _horse_summary(row)
            for row in enriched
            if _to_float(row.get("current_odds")) >= 10.0 and _to_float(row.get("ev")) >= max(min_ev, 1.08)
        ][:2]

        core.extend(race_core)
        partner.extend(race_partner)
        longshots.extend(race_long)
        races.append(
            {
                "race_id": race_id,
                "core": race_core,
                "partner": race_partner,
                "long": race_long,
                "tickets": race_tickets,
            }
        )

    return {
        "core": core,
        "partner": partner,
        "long": longshots,
        "tickets": flat_tickets,
        "races": races,
        "primary_bet_type": flat_tickets[0].get("bet_type", "wide") if flat_tickets else "wide",
        "tansho": [ticket.get("horse_name", "") for ticket in flat_tickets if ticket.get("bet_type") == "win"][:2],
        "wide": [ticket.get("horse_name", "") for ticket in flat_tickets if ticket.get("bet_type") == "wide"][:3]
        or _pair_strings([item.get("horse_name", "") for item in core[:3]]),
        "sanrenpuku": [" - ".join([item.get("horse_name", "") for item in core[:3]])] if len(core) >= 3 else [],
    }


def _build_win_ticket(
    row: dict[str, object],
    *,
    bankroll_per_race: int,
    kelly_fraction: float,
) -> dict[str, object] | None:
    prob = _to_float(row.get("win_prob"))
    odds = _to_float(row.get("current_odds"))
    ev = _to_float(row.get("ev"))
    if prob <= 0 or odds <= 1.0 or ev <= 1.0:
        return None

    full_kelly = ((odds * prob) - 1.0) / max(odds - 1.0, 1e-6)
    recommended_fraction = max(0.0, min(0.30, full_kelly * kelly_fraction))
    stake = int((bankroll_per_race * recommended_fraction) / 100) * 100
    if stake < 100:
        stake = 100 if ev >= 1.08 else 0
    if stake <= 0:
        return None

    return {
        "race_id": str(row.get("race_id", "")),
        "bet_type": "win",
        "horse_id": str(row.get("horse_id", "")),
        "horse_name": str(row.get("horse_name", "")),
        "horse_number": int(_to_float(row.get("horse_number"), 0.0)),
        "stake": stake,
        "win_prob": _fmt(prob),
        "win_odds": _fmt(odds),
        "ev": _fmt(ev),
        "ev_current": str(row.get("ev_current", row.get("ev", ""))),
        "ev_predicted": str(row.get("ev_predicted", "")),
        "fair_odds": str(row.get("fair_odds", "")),
        "model_score": str(row.get("model_score", "")),
        "predicted_odds": str(row.get("predicted_odds", "")),
        "predicted_odds_source": str(row.get("predicted_odds_source", "")),
    }


def _build_wide_candidates(
    rows: list[dict[str, object]],
    *,
    bankroll_per_race: int,
    min_wide_ev: float,
    kelly_fraction: float,
) -> list[dict[str, object]]:
    if len(rows) < 2:
        return []

    field_size = len(rows)
    pool = sorted(
        rows,
        key=lambda row: (
            _to_float(row.get("place_prob")),
            _to_float(row.get("ev_predicted") or row.get("ev")),
            _to_float(row.get("win_prob")),
        ),
        reverse=True,
    )[:5]

    pairs: list[dict[str, object]] = []
    for left_idx in range(len(pool)):
        for right_idx in range(left_idx + 1, len(pool)):
            ticket = _build_wide_ticket(
                pool[left_idx],
                pool[right_idx],
                field_size=field_size,
                bankroll_per_race=bankroll_per_race,
                kelly_fraction=kelly_fraction,
                min_wide_ev=min_wide_ev,
            )
            if ticket is not None:
                pairs.append(ticket)

    pairs.sort(
        key=lambda ticket: (
            _to_float(ticket.get("ev_current") or ticket.get("ev")),
            _to_float(ticket.get("hit_prob")),
            _to_float(ticket.get("confidence")),
        ),
        reverse=True,
    )
    return pairs


def _build_wide_ticket(
    left: dict[str, object],
    right: dict[str, object],
    *,
    field_size: int,
    bankroll_per_race: int,
    kelly_fraction: float,
    min_wide_ev: float,
) -> dict[str, object] | None:
    pair_prob = _estimate_pair_hit_prob(left, right, field_size=field_size)
    market_pair_prob = _estimate_market_pair_prob(left, right, field_size=field_size)
    current_odds_est = _estimate_market_pair_odds(market_pair_prob)
    predicted_odds_est = _estimate_predicted_pair_odds(left, right, current_odds_est=current_odds_est)
    ev_current = pair_prob * current_odds_est if current_odds_est > 0 else 0.0
    ev_predicted = pair_prob * predicted_odds_est if predicted_odds_est > 0 else 0.0

    if pair_prob < 0.10 or current_odds_est <= 1.0 or ev_current < min_wide_ev:
        return None

    stake = _kelly_stake(
        probability=pair_prob,
        odds=current_odds_est,
        bankroll_per_race=bankroll_per_race,
        kelly_fraction=min(0.40, kelly_fraction + 0.05),
        min_ev=min_wide_ev,
        max_fraction=0.36,
    )
    if stake <= 0:
        return None

    horse_ids = [str(left.get("horse_id", "")), str(right.get("horse_id", ""))]
    horse_names = [str(left.get("horse_name", "")), str(right.get("horse_name", ""))]
    horse_numbers = [str(left.get("horse_number", "")), str(right.get("horse_number", ""))]
    confidence = (pair_prob / max(market_pair_prob, 1e-6)) if market_pair_prob > 0 else 0.0

    return {
        "race_id": str(left.get("race_id", "")),
        "bet_type": "wide",
        "horse_id": "|".join(horse_ids),
        "horse_name": " - ".join(horse_names),
        "horse_number": "-".join(horse_numbers),
        "horse_ids": horse_ids,
        "horse_names": horse_names,
        "horse_numbers": horse_numbers,
        "stake": stake,
        "hit_prob": _fmt(pair_prob),
        "win_prob": _fmt(pair_prob),
        "wide_prob": _fmt(pair_prob),
        "wide_prob_market": _fmt(market_pair_prob),
        "win_odds": _fmt(current_odds_est),
        "wide_odds_est": _fmt(current_odds_est),
        "predicted_odds": _fmt(predicted_odds_est),
        "predicted_wide_odds": _fmt(predicted_odds_est),
        "ev": _fmt(ev_current),
        "ev_current": _fmt(ev_current),
        "ev_predicted": _fmt(ev_predicted),
        "predicted_odds_source": "pair_estimated",
        "confidence": _fmt(confidence),
        "legs": [
            {
                "horse_id": horse_ids[0],
                "horse_name": horse_names[0],
                "horse_number": horse_numbers[0],
                "place_prob": str(left.get("place_prob", "")),
                "win_prob": str(left.get("win_prob", "")),
            },
            {
                "horse_id": horse_ids[1],
                "horse_name": horse_names[1],
                "horse_number": horse_numbers[1],
                "place_prob": str(right.get("place_prob", "")),
                "win_prob": str(right.get("win_prob", "")),
            },
        ],
    }


def _horse_summary(row: dict[str, object]) -> dict[str, object]:
    return {
        "race_id": str(row.get("race_id", "")),
        "horse_id": str(row.get("horse_id", "")),
        "horse_name": str(row.get("horse_name", "")),
        "horse_number": str(row.get("horse_number", "")),
        "win_prob": str(row.get("win_prob", "")),
        "place_prob": str(row.get("place_prob", "")),
        "ev": str(row.get("ev", "")),
        "ev_predicted": str(row.get("ev_predicted", "")),
        "current_odds": str(row.get("current_odds", "")),
        "predicted_odds": str(row.get("predicted_odds", "")),
        "predicted_odds_source": str(row.get("predicted_odds_source", "")),
    }


def _pair_strings(names: list[str]) -> list[str]:
    cleaned = [name for name in names if name]
    out: list[str] = []
    for i in range(len(cleaned)):
        for j in range(i + 1, len(cleaned)):
            out.append(f"{cleaned[i]} - {cleaned[j]}")
    return out


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _enrich_rows_for_multi_bet(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []

    field_size = len(rows)
    target_hits = 2.0 if field_size <= 7 else 3.0
    raw_place: list[float] = []
    market_place: list[float] = []
    floors: list[float] = []

    for row in rows:
        win_prob = _to_float(row.get("win_prob"))
        market_prob = _to_float(row.get("market_prob"))
        consistency = _to_float(row.get("consistency"), 0.5)
        history = min(_to_float(row.get("history_count"), 0.0) / 5.0, 1.0)
        band = str(row.get("probability_band") or _probability_band_from_row(row))
        band_boost = {
            "favorite": 1.60,
            "contender": 1.82,
            "outsider": 2.04,
            "longshot": 2.18,
        }.get(band, 1.80)
        market_boost = {
            "favorite": 1.72,
            "contender": 1.92,
            "outsider": 2.10,
            "longshot": 2.28,
        }.get(band, 1.90)

        raw_place.append(
            max(
                win_prob,
                (win_prob * band_boost)
                + (0.18 * consistency)
                + (0.08 * history)
                + (0.08 * market_prob * target_hits),
            )
        )
        market_place.append(
            max(
                market_prob,
                (market_prob * market_boost)
                + (0.10 * consistency)
                + (0.05 * history),
            )
        )
        floors.append(win_prob)

    caps = [0.82 if field_size > 7 else 0.72 for _ in rows]
    place_probs = _normalize_to_target(raw_place, target=target_hits, floors=floors, caps=caps)
    market_place_probs = _normalize_to_target(
        market_place,
        target=target_hits,
        floors=[_to_float(row.get("market_prob")) for row in rows],
        caps=caps,
    )

    enriched: list[dict[str, object]] = []
    for row, place_prob, market_place_prob in zip(rows, place_probs, market_place_probs):
        out = dict(row)
        out["place_prob"] = _fmt(max(_to_float(row.get("win_prob")), place_prob))
        out["market_place_prob"] = _fmt(market_place_prob)
        out["place_fair_odds"] = _fmt((1.0 / place_prob) if place_prob > 0 else 0.0)
        out["place_edge"] = _fmt(place_prob - market_place_prob)
        enriched.append(out)
    return enriched


def _normalize_to_target(
    values: list[float],
    *,
    target: float,
    floors: list[float],
    caps: list[float],
) -> list[float]:
    if not values:
        return []

    normalized = _scale_to_target(values, target)
    out = [
        _clamp(value, minimum=max(0.0, floor), maximum=max(max(0.0, floor), cap))
        for value, floor, cap in zip(normalized, floors, caps)
    ]

    for _ in range(8):
        total = sum(out)
        delta = target - total
        if abs(delta) <= 1e-6:
            break

        if delta > 0:
            adjustable = [idx for idx, (value, cap) in enumerate(zip(out, caps)) if value < cap - 1e-9]
            if not adjustable:
                break
            weights = [max(values[idx], 1e-6) for idx in adjustable]
            weight_total = sum(weights) or float(len(adjustable))
            for idx, weight in zip(adjustable, weights):
                add = delta * (weight / weight_total)
                out[idx] = min(caps[idx], out[idx] + add)
        else:
            adjustable = [idx for idx, (value, floor) in enumerate(zip(out, floors)) if value > floor + 1e-9]
            if not adjustable:
                break
            weights = [max(out[idx] - floors[idx], 1e-6) for idx in adjustable]
            weight_total = sum(weights) or float(len(adjustable))
            remove = abs(delta)
            for idx, weight in zip(adjustable, weights):
                cut = remove * (weight / weight_total)
                out[idx] = max(floors[idx], out[idx] - cut)

    return out


def _scale_to_target(values: list[float], target: float) -> list[float]:
    total = sum(max(0.0, value) for value in values)
    if total <= 0:
        equal = target / max(len(values), 1)
        return [equal for _ in values]
    return [(max(0.0, value) / total) * target for value in values]


def _estimate_pair_hit_prob(
    left: dict[str, object],
    right: dict[str, object],
    *,
    field_size: int,
) -> float:
    slots = 2.0 if field_size <= 7 else 3.0
    left_place = _to_float(left.get("place_prob"))
    right_place = _to_float(right.get("place_prob"))
    avg_consistency = (_to_float(left.get("consistency"), 0.5) + _to_float(right.get("consistency"), 0.5)) / 2.0
    front_gap = abs(_to_float(left.get("front_rate"), 0.5) - _to_float(right.get("front_rate"), 0.5))
    complement = 1.0 - min(front_gap, 1.0)
    inflation = 1.14 + (0.55 * (slots / max(field_size, 1))) + (0.12 * avg_consistency) + (0.08 * complement)
    joint = left_place * right_place * inflation
    return _clamp(joint, minimum=0.0, maximum=min(left_place, right_place) * 0.97)


def _estimate_market_pair_prob(
    left: dict[str, object],
    right: dict[str, object],
    *,
    field_size: int,
) -> float:
    slots = 2.0 if field_size <= 7 else 3.0
    left_place = _to_float(left.get("market_place_prob"))
    right_place = _to_float(right.get("market_place_prob"))
    inflation = 1.10 + (0.45 * (slots / max(field_size, 1)))
    joint = left_place * right_place * inflation
    return _clamp(joint, minimum=0.0, maximum=min(left_place, right_place) * 0.98)


def _estimate_market_pair_odds(market_pair_prob: float) -> float:
    if market_pair_prob <= 0:
        return 0.0
    return _clamp(0.82 / market_pair_prob, minimum=1.1, maximum=75.0)


def _estimate_predicted_pair_odds(
    left: dict[str, object],
    right: dict[str, object],
    *,
    current_odds_est: float,
) -> float:
    ratios: list[float] = []
    for row in (left, right):
        current = _to_float(row.get("current_odds"))
        predicted = _to_float(row.get("predicted_odds"))
        if current > 0 and predicted > 0:
            ratios.append(predicted / current)

    trend_ratio = math.prod(ratios) ** (1.0 / len(ratios)) if ratios else 1.0
    trend_ratio = _clamp(trend_ratio, minimum=0.88, maximum=1.16)
    return _clamp(current_odds_est * trend_ratio, minimum=1.1, maximum=max(1.1, current_odds_est * 1.18))


def _has_win_standout(rows: list[dict[str, object]]) -> bool:
    if not rows:
        return False
    leader = max(rows, key=lambda row: _to_float(row.get("win_prob")))
    return _to_float(leader.get("win_prob")) >= 0.20 and _to_float(leader.get("ev")) >= 1.08


def _rebalance_race_stakes(
    tickets: list[dict[str, object]],
    *,
    bankroll_per_race: int,
) -> list[dict[str, object]]:
    if not tickets:
        return []

    total = sum(int(_to_float(ticket.get("stake"), 0.0)) for ticket in tickets)
    if total <= bankroll_per_race:
        return tickets

    scaled: list[dict[str, object]] = []
    scale = bankroll_per_race / max(total, 1)
    for ticket in tickets:
        out = dict(ticket)
        stake = int(_to_float(ticket.get("stake"), 0.0))
        adjusted = int((stake * scale) / 100) * 100
        if adjusted <= 0:
            continue
        out["stake"] = adjusted
        scaled.append(out)

    if not scaled:
        best = dict(max(tickets, key=lambda ticket: _to_float(ticket.get("ev_current") or ticket.get("ev"))))
        best["stake"] = min(100, bankroll_per_race)
        return [best] if int(_to_float(best.get("stake"), 0.0)) > 0 else []
    return scaled


def _kelly_stake(
    *,
    probability: float,
    odds: float,
    bankroll_per_race: int,
    kelly_fraction: float,
    min_ev: float,
    max_fraction: float,
) -> int:
    if probability <= 0 or odds <= 1.0:
        return 0
    ev = probability * odds
    if ev <= 1.0:
        return 0

    full_kelly = ((odds * probability) - 1.0) / max(odds - 1.0, 1e-6)
    recommended_fraction = max(0.0, min(max_fraction, full_kelly * kelly_fraction))
    stake = int((bankroll_per_race * recommended_fraction) / 100) * 100
    if stake < 100:
        stake = 100 if ev >= min_ev else 0
    return stake


def _probability_band_from_row(row: dict[str, object]) -> str:
    odds = _to_float(row.get("current_odds"))
    popularity = _to_float(row.get("current_popularity") or row.get("popularity_latest"))
    if (popularity > 0 and popularity <= 3) or (odds > 0 and odds <= 6.0):
        return "favorite"
    if (popularity > 0 and popularity <= 8) or (odds > 0 and odds <= 15.0):
        return "contender"
    if (popularity > 0 and popularity <= 12) or (odds > 0 and odds <= 30.0):
        return "outsider"
    return "longshot"


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _to_float(value: object, default: float = 0.0) -> float:
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

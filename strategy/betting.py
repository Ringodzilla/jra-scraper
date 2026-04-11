from __future__ import annotations

from collections import defaultdict


def generate_tickets(
    ev_rows: list[dict[str, object]],
    mode: str = "balanced",
    *,
    bankroll_per_race: int = 1000,
    min_ev: float = 1.03,
    max_tickets_per_race: int = 2,
    kelly_fraction: float = 0.33,
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
        candidates = [row for row in ranked if _to_float(row.get("ev")) >= min_ev and _to_float(row.get("current_odds")) > 0]

        race_tickets: list[dict[str, object]] = []
        for row in candidates[:per_race_limit]:
            ticket = _build_win_ticket(row, bankroll_per_race=bankroll_per_race, kelly_fraction=kelly_fraction)
            if ticket is None:
                continue
            race_tickets.append(ticket)
            flat_tickets.append(ticket)

        race_core = [_horse_summary(row) for row in ranked[:2] if _to_float(row.get("win_prob")) >= 0.12]
        race_partner = [_horse_summary(row) for row in ranked[2:4] if _to_float(row.get("ev")) >= min_ev]
        race_long = [
            _horse_summary(row)
            for row in ranked
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
        "tansho": [ticket.get("horse_name", "") for ticket in flat_tickets[:2]],
        "wide": _pair_strings([item.get("horse_name", "") for item in core[:3]]),
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


def _horse_summary(row: dict[str, object]) -> dict[str, object]:
    return {
        "race_id": str(row.get("race_id", "")),
        "horse_id": str(row.get("horse_id", "")),
        "horse_name": str(row.get("horse_name", "")),
        "horse_number": str(row.get("horse_number", "")),
        "win_prob": str(row.get("win_prob", "")),
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


def _to_float(value: object, default: float = 0.0) -> float:
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

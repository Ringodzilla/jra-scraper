from __future__ import annotations


def generate_tickets(ev_rows: list[dict[str, str]], mode: str = "safe") -> dict[str, list[str]]:
    picks = [r for r in ev_rows if _to_float(r.get("ev")) and _to_float(r.get("ev")) > 1.0]
    picks = sorted(picks, key=lambda r: _to_float(r.get("ev")) or 0.0, reverse=True)

    if mode == "aggressive":
        top = picks[:5]
    else:
        top = picks[:3]

    horse_names = [p.get("horse_name") or "unknown" for p in top]
    return {
        "tansho": horse_names[:2],
        "wide": _pair_strings(horse_names[:3]),
        "sanrenpuku": [" - ".join(horse_names[:3])] if len(horse_names) >= 3 else [],
    }


def _pair_strings(names: list[str]) -> list[str]:
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            out.append(f"{names[i]} - {names[j]}")
    return out


def _to_float(value: str | None) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None

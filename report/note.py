from __future__ import annotations

from pathlib import Path


def generate_note_markdown(race_name: str, ev_rows: list[dict[str, str]], tickets: dict[str, list[str]]) -> str:
    ranking_lines = []
    for idx, row in enumerate(ev_rows[:10], start=1):
        ranking_lines.append(
            f"{idx}. {row.get('horse_name')} / EV={row.get('ev')} / odds={row.get('odds')} / pop={row.get('popularity')}"
        )

    return "\n".join(
        [
            f"# {race_name}",
            "",
            "## サマリー",
            f"対象頭数: {len(ev_rows)}",
            "",
            "## EVランキング",
            *ranking_lines,
            "",
            "## 買い目",
            f"- 単勝: {', '.join(tickets.get('tansho', []))}",
            f"- ワイド: {', '.join(tickets.get('wide', []))}",
            f"- 3連複: {', '.join(tickets.get('sanrenpuku', []))}",
            "",
            "## コメント",
            "EV>1 を優先し、人気との乖離を加味して選定。",
        ]
    )


def write_note(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

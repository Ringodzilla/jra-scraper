from __future__ import annotations

from pathlib import Path


def generate_note_markdown(
    race_name: str,
    ev_rows: list[dict[str, object]],
    tickets: dict[str, object],
    *,
    review: dict[str, object] | None = None,
    quality_report: dict[str, object] | None = None,
) -> str:
    review = review or {}
    quality_report = quality_report or {}
    ranking_lines = []
    for idx, row in enumerate(ev_rows[:10], start=1):
        ranking_lines.append(
            (
                f"{idx}. {row.get('horse_name')} "
                f"(馬番={row.get('horse_number')}, 勝率={row.get('win_prob')}, "
                f"EV_current={row.get('ev_current', row.get('ev'))}, EV_predicted={row.get('ev_predicted', '')}, "
                f"odds={row.get('current_odds')}, predicted={row.get('predicted_odds', '')}, "
                f"source={row.get('predicted_odds_source', '')}, fair={row.get('fair_odds')})"
            )
        )

    ticket_lines = []
    for ticket in tickets.get("tickets", []):
        ticket_lines.append(
            f"- 単勝 {ticket.get('horse_name')}({ticket.get('horse_number')}) "
            f"{ticket.get('stake')}円 / EV={ticket.get('ev')} / EV_predicted={ticket.get('ev_predicted', '')} / "
            f"prob={ticket.get('win_prob')} / source={ticket.get('predicted_odds_source', '')}"
        )
    if not ticket_lines:
        ticket_lines.append("- 条件を満たす購入候補なし")

    issue_summary = quality_report.get("issues_by_severity") or {}
    return "\n".join(
        [
            f"# {race_name}",
            "",
            "## 実行サマリー",
            f"- review_status: {review.get('status', 'UNKNOWN')}",
            f"- review_reason: {review.get('reason', '')}",
            f"- parser_issues: {quality_report.get('issue_count', 0)}",
            f"- issues_by_severity: {issue_summary}",
            "",
            "## EVランキング",
            *ranking_lines,
            "",
            "## 買い目",
            *ticket_lines,
            "",
            "## 役割メモ",
            f"- core: {len(tickets.get('core', []))}頭",
            f"- partner: {len(tickets.get('partner', []))}頭",
            f"- long: {len(tickets.get('long', []))}頭",
        ]
    )


def write_note(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

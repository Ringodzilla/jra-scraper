from __future__ import annotations

from pathlib import Path


def build_note_article(
    race_name: str,
    ev_rows: list[dict[str, object]],
    tickets: dict[str, object],
    *,
    review: dict[str, object] | None = None,
    quality_report: dict[str, object] | None = None,
    race_config: dict[str, object] | None = None,
) -> dict[str, object]:
    review = review or {}
    quality_report = quality_report or {}
    race_config = race_config or {}

    title = str(race_config.get("note_title") or f"{race_name} AI予想")
    review_status = str(review.get("status", "UNKNOWN"))
    review_reason = str(review.get("reason", "")).strip()
    sorted_by_ev = _sort_rows(ev_rows, key="ev_current")
    sorted_by_prob = _sort_rows(ev_rows, key="win_prob")
    ticket_rows = list(tickets.get("tickets") or [])
    publish_ready = review_status == "OK"
    status = "ready" if publish_ready else "hold"

    markdown_lines = [
        f"# {title}",
        "",
        _headline(race_name, review_status, ticket_rows),
        "",
        "## レース概要",
        *_race_meta_lines(race_name, race_config),
        "",
        "## 結論",
        *_conclusion_lines(review_status, review_reason, ticket_rows, sorted_by_ev),
        "",
        "## 印",
        *_mark_lines(ticket_rows, sorted_by_prob, sorted_by_ev),
        "",
        "## 買い目",
        *_ticket_lines(review_status, review_reason, ticket_rows),
        "",
        "## AI評価上位",
        *_ranking_lines(sorted_by_ev),
        "",
        "## データチェック",
        *_data_quality_lines(review, quality_report, ticket_rows),
        "",
        "## メモ",
        *_risk_lines(review_status, sorted_by_prob, sorted_by_ev),
        "",
        "※ 最終判断は直前オッズと馬場状態を確認して行ってください。",
    ]
    markdown = "\n".join(markdown_lines)

    return {
        "status": status,
        "publish_ready": publish_ready,
        "title": title,
        "headline": _headline(race_name, review_status, ticket_rows),
        "ticket_count": len(ticket_rows),
        "review_status": review_status,
        "markdown": markdown,
    }


def generate_note_markdown(
    race_name: str,
    ev_rows: list[dict[str, object]],
    tickets: dict[str, object],
    *,
    review: dict[str, object] | None = None,
    quality_report: dict[str, object] | None = None,
    race_config: dict[str, object] | None = None,
) -> str:
    article = build_note_article(
        race_name,
        ev_rows,
        tickets,
        review=review,
        quality_report=quality_report,
        race_config=race_config,
    )
    return str(article["markdown"])


def write_note(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _headline(race_name: str, review_status: str, ticket_rows: list[dict[str, object]]) -> str:
    if review_status == "OK" and ticket_rows:
        main_names = "、".join(str(ticket.get("horse_name", "")) for ticket in ticket_rows[:2] if ticket.get("horse_name"))
        return f"{race_name}を再計算しました。reviewerはOKで、現時点の妙味候補は{main_names}です。"
    if review_status == "OK":
        return f"{race_name}を再計算しました。reviewerはOKでしたが、期待値条件を満たす買い目は絞り込みになりました。"
    return f"{race_name}を再計算しました。今回はreviewerがNGを返しているため、見送り前提で整理します。"


def _race_meta_lines(race_name: str, race_config: dict[str, object]) -> list[str]:
    lines = [f"- レース名: {race_name}"]
    race_date = str(race_config.get("race_date", "")).strip()
    track = str(race_config.get("track", "")).strip()
    race_number = str(race_config.get("race_number", "")).strip()
    source_url = str(race_config.get("source_url", "")).strip()
    if race_date:
        lines.append(f"- 開催日: {race_date}")
    if track or race_number:
        lines.append(f"- 開催情報: {track}{race_number}R".strip())
    if source_url:
        lines.append(f"- 参照元: {source_url}")
    return lines


def _conclusion_lines(
    review_status: str,
    review_reason: str,
    ticket_rows: list[dict[str, object]],
    sorted_by_ev: list[dict[str, object]],
) -> list[str]:
    if review_status != "OK":
        lines = ["- 今回は購入見送りです。"]
        if review_reason:
            lines.append(f"- 見送り理由: {review_reason}")
        return lines

    if ticket_rows:
        primary = ticket_rows[0]
        lines = [
            f"- 現時点の本線は {primary.get('horse_number')} {primary.get('horse_name')} の単勝です。",
        ]
        if len(ticket_rows) >= 2:
            secondary = ticket_rows[1]
            lines.append(
                f"- 相手候補は {secondary.get('horse_number')} {secondary.get('horse_name')} の単勝です。"
            )
        lines.append(f"- 購入点数は {len(ticket_rows)} 点です。")
        return lines

    if sorted_by_ev:
        top = sorted_by_ev[0]
        return [
            "- reviewer は OK ですが、運用条件に合う買い目が少ないため無理打ちは避けます。",
            f"- 評価上位は {top.get('horse_number')} {top.get('horse_name')} です。",
        ]
    return ["- 今回は有効な評価データが不足しています。"]


def _mark_lines(
    ticket_rows: list[dict[str, object]],
    sorted_by_prob: list[dict[str, object]],
    sorted_by_ev: list[dict[str, object]],
) -> list[str]:
    marks = ["◎", "○", "▲", "☆"]
    selected: list[dict[str, object]] = []
    seen: set[str] = set()

    for source in (ticket_rows, sorted_by_prob, sorted_by_ev):
        for row in source:
            horse_id = str(row.get("horse_id", "")).strip()
            if not horse_id or horse_id in seen:
                continue
            seen.add(horse_id)
            selected.append(row)
            if len(selected) >= len(marks):
                break
        if len(selected) >= len(marks):
            break

    if not selected:
        return ["- 印を出すだけの十分な候補がありません。"]

    lines = []
    for mark, row in zip(marks, selected):
        lines.append(
            f"- {mark} {row.get('horse_number')} {row.get('horse_name')} "
            f"(勝率 {_fmt_pct(row.get('win_prob'))}, EV {_fmt_value(row.get('ev_current') or row.get('ev'))})"
        )
    return lines


def _ticket_lines(
    review_status: str,
    review_reason: str,
    ticket_rows: list[dict[str, object]],
) -> list[str]:
    if review_status != "OK":
        lines = ["- 今回は見送りです。"]
        if review_reason:
            lines.append(f"- 理由: {review_reason}")
        return lines

    if not ticket_rows:
        return ["- 期待値条件を満たす買い目はありません。"]

    lines = []
    for ticket in ticket_rows:
        lines.append(
            f"- 単勝 {ticket.get('horse_number')} {ticket.get('horse_name')} "
            f"{ticket.get('stake')}円"
            f" / 勝率 {_fmt_pct(ticket.get('win_prob'))}"
            f" / 現在オッズ {_fmt_odds(ticket.get('win_odds'))}"
            f" / EV {_fmt_value(ticket.get('ev_current') or ticket.get('ev'))}"
        )
    return lines


def _ranking_lines(sorted_by_ev: list[dict[str, object]]) -> list[str]:
    if not sorted_by_ev:
        return ["- 評価対象なし"]

    lines = []
    for idx, row in enumerate(sorted_by_ev[:5], start=1):
        lines.append(
            f"- {idx}位: {row.get('horse_number')} {row.get('horse_name')}"
            f" / 勝率 {_fmt_pct(row.get('win_prob'))}"
            f" / 現在オッズ {_fmt_odds(row.get('current_odds'))}"
            f" / EV {_fmt_value(row.get('ev_current') or row.get('ev'))}"
            f" / 予測オッズ {_fmt_odds(row.get('predicted_odds'))}"
            f" ({row.get('predicted_odds_source', '')})"
        )
    return lines


def _data_quality_lines(
    review: dict[str, object],
    quality_report: dict[str, object],
    ticket_rows: list[dict[str, object]],
) -> list[str]:
    issue_count = int(quality_report.get("issue_count", 0) or 0)
    live_snapshot_count = int(quality_report.get("live_snapshot_count", 0) or 0)
    return [
        f"- review_status: {review.get('status', 'UNKNOWN')}",
        f"- review_reason: {review.get('reason', '')}",
        f"- parser_issues: {issue_count}",
        f"- live_odds_snapshots: {live_snapshot_count}",
        f"- ticket_count: {len(ticket_rows)}",
    ]


def _risk_lines(
    review_status: str,
    sorted_by_prob: list[dict[str, object]],
    sorted_by_ev: list[dict[str, object]],
) -> list[str]:
    lines = []
    if review_status != "OK":
        lines.append("- reviewer が NG のときは無理に買わず、直前の再取得を優先します。")
    if sorted_by_prob:
        top_prob = sorted_by_prob[0]
        lines.append(
            f"- 勝率最上位は {top_prob.get('horse_number')} {top_prob.get('horse_name')} "
            f"({_fmt_pct(top_prob.get('win_prob'))}) です。"
        )
    if sorted_by_ev:
        top_ev = sorted_by_ev[0]
        lines.append(
            f"- EV最上位は {top_ev.get('horse_number')} {top_ev.get('horse_name')} "
            f"(EV {_fmt_value(top_ev.get('ev_current') or top_ev.get('ev'))}) です。"
        )
    lines.append("- 発走直前はオッズが動くので、購入前に再計算するのが安全です。")
    return lines


def _sort_rows(rows: list[dict[str, object]], *, key: str) -> list[dict[str, object]]:
    return sorted(
        list(rows),
        key=lambda row: (_to_float(row.get(key) or row.get("ev") or 0.0), _to_float(row.get("win_prob"), 0.0)),
        reverse=True,
    )


def _fmt_pct(value: object) -> str:
    return f"{_to_float(value) * 100:.1f}%"


def _fmt_value(value: object) -> str:
    return f"{_to_float(value):.3f}"


def _fmt_odds(value: object) -> str:
    number = _to_float(value)
    if number <= 0:
        return "-"
    return f"{number:.1f}倍"


def _to_float(value: object, default: float = 0.0) -> float:
    if value in (None, "", "None"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.ev import compute_ev, load_rows, save_ev
from jra_scraper.config import ScrapeConfig
from jra_scraper.pipeline import JRAPipeline
from report.note import generate_note_markdown, write_note
from strategy.betting import generate_tickets


def load_race_configs(path: Path) -> list[dict]:
    configs = json.loads(path.read_text(encoding="utf-8"))
    required = {"race_name", "race_date", "track", "race_number", "source_url", "output_slug", "note_title", "note_tags"}
    for idx, cfg in enumerate(configs, start=1):
        missing = sorted(required - set(cfg.keys()))
        if missing:
            raise ValueError(f"config index={idx} missing keys: {missing}")
    return configs


def run_analysis_phase(
    race_configs: list[dict],
    *,
    race_urls: list[str] | None = None,
    force_rebuild: bool = False,
    race_limit: int | None = None,
    horse_limit: int | None = None,
) -> dict:
    logging.info("analysis phase started")
    urls = race_urls or [cfg["source_url"] for cfg in race_configs]

    pipeline = JRAPipeline(ScrapeConfig())
    try:
        pipeline.run(
            race_urls=urls,
            force_rebuild=force_rebuild,
            race_limit=race_limit,
            horse_limit=horse_limit,
        )
    finally:
        pipeline.close()

    processed_path = ROOT / "data/processed/race_last5.csv"
    ev_path = ROOT / "data/processed/race_ev.csv"
    note_path = ROOT / "report/note.md"
    payload_path = ROOT / "report/publish_payload.json"

    rows = load_rows(processed_path)
    scored = compute_ev(rows)
    save_ev(scored, ev_path)

    race_name = race_configs[0]["race_name"]
    tickets = generate_tickets(scored, mode="safe")
    note = generate_note_markdown(race_name, scored, tickets)
    write_note(note_path, note)

    payload = {
        "title": race_configs[0]["note_title"],
        "tags": race_configs[0]["note_tags"],
        "slug": race_configs[0]["output_slug"],
        "race_name": race_name,
        "race_date": race_configs[0]["race_date"],
        "markdown_path": str(note_path),
        "body_markdown_path": str(note_path),
        "mode_default": "browser:draft",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
    }
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("analysis phase completed")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run JRA analysis pipeline")
    parser.add_argument(
        "--config-path",
        default=str(ROOT / "config/races.json"),
        help="Race config json path",
    )
    parser.add_argument(
        "--race-url",
        action="append",
        default=None,
        help="Direct race URL. Can be repeated.",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore processed state and rebuild races",
    )
    parser.add_argument(
        "--race-limit",
        type=int,
        default=None,
        help="Max races to process (default: no limit)",
    )
    parser.add_argument(
        "--horse-limit",
        type=int,
        default=None,
        help="Max horses per race (default: no limit)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg_path = Path(args.config_path)
    race_configs = load_race_configs(cfg_path)
    payload = run_analysis_phase(
        race_configs,
        race_urls=args.race_url,
        force_rebuild=args.force_rebuild,
        race_limit=args.race_limit,
        horse_limit=args.horse_limit,
    )
    logging.info("outputs ready: %s", payload)


if __name__ == "__main__":
    main()

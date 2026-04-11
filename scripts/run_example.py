#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jra_scraper.config import ScrapeConfig
from jra_scraper.pipeline import JRAPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run JRA scraper pipeline")

    parser.add_argument(
        "--config-path",
        default="config/races.json",
        help="Race config json path",
    )
    parser.add_argument(
        "--output-path",
        default="data/processed/race_last5.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--state-path",
        default="data/processed/pipeline_state.json",
        help="State json path",
    )
    parser.add_argument(
        "--reprocess-raw",
        action="store_true",
        help="Parse only cached HTML (no network)",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Ignore state and rebuild",
    )
    parser.add_argument(
        "--race-list-path",
        default="/JRADB/accessS.html",
        help="Race list relative path",
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

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # config読み込み
    cfg = json.loads(Path(args.config_path).read_text(encoding="utf-8"))
    race_specs = list(cfg)

    config = ScrapeConfig(
        race_list_path=args.race_list_path,
        output_csv=Path(args.output_path),
        state_path=Path(args.state_path),
    )

    pipeline = JRAPipeline(config)

    try:
        rows = pipeline.run(
            race_limit=args.race_limit,
            horse_limit=args.horse_limit,
            race_specs=race_specs,
            reprocess_raw=args.reprocess_raw,
            force_rebuild=args.force_rebuild,
        )
        logging.info(
            "Finished. Rows=%d output=%s state=%s",
            len(rows),
            config.output_csv,
            config.state_path,
        )
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()

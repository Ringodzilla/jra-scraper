#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    parser.add_argument("--race-limit", type=int, default=2, help="How many races to process")
    parser.add_argument("--horse-limit", type=int, default=5, help="How many horses per race")
    parser.add_argument("--output-path", default="data/processed/race_last5.csv", help="CSV output path")
    parser.add_argument("--state-path", default="data/processed/pipeline_state.json", help="State json path")
    parser.add_argument("--reprocess-raw", action="store_true", help="Do not fetch network; parse only cached raw HTML")
    parser.add_argument("--force-rebuild", action="store_true", help="Ignore incremental state and rebuild CSV")
    parser.add_argument(
        "--race-list-path",
        default="/JRADB/accessS.html",
        help="Relative path to race list page",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    config = ScrapeConfig(
        race_list_path=args.race_list_path,
        output_csv=Path(args.output_path),
        state_path=Path(args.state_path),
    )
    pipeline = JRAPipeline(config)
    try:
        rows = pipeline.run(
            race_urls=[
                "https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0107202601061120260329/50"
            ]
        )
        logging.info("Finished. Rows=%d output=%s state=%s", len(rows), config.output_csv, config.state_path)
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()

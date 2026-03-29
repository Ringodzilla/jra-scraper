#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jra_scraper.config import ScrapeConfig
from jra_scraper.pipeline import JRAPipeline


def main():
    logging.basicConfig(level=logging.INFO)

    config = ScrapeConfig(
        output_csv=Path("data/processed/race_last5.csv"),
        state_path=Path("data/processed/pipeline_state.json"),
    )

    pipeline = JRAPipeline(config)

    try:
        rows = pipeline.run(
            race_urls=[
                "https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0107202601061120260329/50"
            ]
        )
        logging.info(f"Finished. Rows={len(rows)}")

    finally:
        pipeline.close()


if __name__ == "__main__":
    main()

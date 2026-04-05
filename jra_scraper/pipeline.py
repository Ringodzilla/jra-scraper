from __future__ import annotations

import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import ScrapeConfig
from .parser import JRAParser, RaceLink
from .scraper import JRAScraper, safe_filename
from .validation import build_race_info_rows, validate_rows


logger = logging.getLogger(__name__)


class JRAPipeline:
    """Persistent pipeline with caching, incremental updates, and idempotent writes."""

    def __init__(self, config: ScrapeConfig | None = None) -> None:
        self.config = config or ScrapeConfig()
        self.config.ensure_dirs()
        self.scraper = JRAScraper(self.config)
        self.parser = JRAParser(self.config.base_url)

    def run(
        self,
        race_limit: int | None = None,
        horse_limit: int | None = None,
        *,
        race_urls: list[str] | None = None,
        reprocess_raw: bool = False,
        force_rebuild: bool = False,
    ) -> list[dict[str, str]]:

        logger.info(
            "Pipeline start race_limit=%s horse_limit=%s race_urls=%s reprocess_raw=%s force_rebuild=%s",
            race_limit,
            horse_limit,
            len(race_urls) if race_urls else 0,
            reprocess_raw,
            force_rebuild,
        )

        state = self._load_state()
        existing_rows = [] if force_rebuild else self._read_existing_rows(self.config.output_csv)
        processed_races = set(state.get("processed_race_ids", []))
        failures = state.get("failures", {})
        all_new_rows: list[dict[str, str]] = []
        processed_this_run: list[str] = []

        # 🔥 race_urls対応
        if race_urls:
            races = []
            for race_url in race_urls:
                race_id = self._build_direct_race_id(race_url)
                races.append(
                    RaceLink(
                        race_id=race_id,
                        race_name=f"direct_race_{race_id[:8]}",
                        race_url=race_url,
                    )
                )
            logger.info("Using direct race URLs: %d", len(races))
        else:
            race_list_html = self.scraper.fetch_relative(
                self.config.race_list_path,
                raw_name="race_list.html",
                use_cache=True,
                cache_only=reprocess_raw,
            )
            if not race_list_html:
                logger.error("Race list unavailable.")
                self._write_csv(existing_rows, self.config.output_csv)
                self._save_state(processed_races, failures, 0, 0)
                return existing_rows

            races = self.parser.parse_race_list(race_list_html)
            if race_limit is not None:
                races = races[:race_limit]
            logger.info("Parsed races=%d", len(races))

        for race in races:
            if force_rebuild:
                logger.info(
                    "Rebuild mode active, process race regardless of state race_id=%s force_rebuild=%s",
                    race.race_id,
                    force_rebuild,
                )
            elif race.race_id in processed_races:
                logger.info(
                    "Skip already processed race race_id=%s force_rebuild=%s",
                    race.race_id,
                    force_rebuild,
                )
                continue

            race_html = self.scraper.fetch(
                race.race_url,
                raw_name=f"race_{safe_filename(race.race_id)}.html",
                use_cache=True,
                cache_only=reprocess_raw,
            )
            if not race_html:
                failures[race.race_url] = failures.get(race.race_url, 0) + 1
                logger.warning("Skip race due to missing html: %s", race.race_url)
                continue

            horses = self.parser.parse_race_detail(
                race_html, race.race_id, race.race_name
            )
            if horse_limit is not None:
                horses = horses[:horse_limit]
            logger.info("Race=%s horses=%d", race.race_id, len(horses))
            field_size = str(len(horses))

            race_rows = []
            race_failed = False

            for horse in horses:
                horse_html = self.scraper.fetch(
                    horse.horse_url,
                    raw_name=f"horse_{safe_filename(horse.horse_id)}.html",
                    use_cache=True,
                    cache_only=reprocess_raw,
                )
                if not horse_html:
                    failures[horse.horse_url] = failures.get(horse.horse_url, 0) + 1
                    logger.warning("Skip horse due to missing html: %s", horse.horse_url)
                    race_failed = True
                    continue

                rows = self.parser.parse_horse_last5(
                    horse_html,
                    race_id=horse.race_id,
                    horse_id=horse.horse_id,
                    horse_name=horse.horse_name,
                    horse_url=horse.horse_url,
                    field_size=field_size,
                )
                race_rows.extend(rows)

            all_new_rows.extend(race_rows)

            if not race_failed:
                processed_races.add(race.race_id)
                processed_this_run.append(race.race_id)
                logger.info(
                    "Processed race race_id=%s force_rebuild=%s rows=%d",
                    race.race_id,
                    force_rebuild,
                    len(race_rows),
                )

        final_rows = validate_rows(existing_rows + all_new_rows)
        self._write_csv(final_rows, self.config.output_csv)
        race_info_rows = build_race_info_rows(final_rows)
        self._write_csv(race_info_rows, self.config.race_info_csv)
        self._save_state(
            processed_races,
            failures,
            len(processed_this_run),
            len(all_new_rows),
        )

        logger.info(
            "Pipeline complete total_rows=%d new_rows=%d processed_races=%d",
            len(final_rows),
            len(all_new_rows),
            len(processed_this_run),
        )

        return final_rows

    def close(self) -> None:
        self.scraper.close()

    @staticmethod
    def _write_csv(rows: list[dict[str, str]], output_csv: Path) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8", newline="") as f:
            if not rows:
                return
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _read_existing_rows(path: Path) -> list[dict[str, str]]:
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _load_state(self) -> dict:
        if not self.config.state_path.exists():
            return {"processed_race_ids": [], "failures": {}}
        with self.config.state_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_state(
        self,
        processed_races: set[str],
        failures: dict[str, int],
        processed_count: int,
        new_rows: int,
    ) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "processed_race_ids": sorted(processed_races),
            "failures": failures,
            "last_run": {
                "processed_races": processed_count,
                "new_rows": new_rows,
            },
        }
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.state_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _build_direct_race_id(race_url: str) -> str:
        return hashlib.md5(race_url.encode("utf-8")).hexdigest()

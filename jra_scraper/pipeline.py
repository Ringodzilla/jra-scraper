from __future__ import annotations

import csv
import hashlib
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import ScrapeConfig
from .models import ParserIssue, RaceLink
from .parser import JRAParser
from .scraper import JRAScraper, safe_filename
from .validation import ENTRY_COLUMNS, OUTPUT_COLUMNS, build_entry_rows, validate_rows

LIVE_ODDS_SNAPSHOT_COLUMNS = [
    "race_id",
    "horse_id",
    "horse_name",
    "horse_number",
    "current_odds",
    "current_popularity",
    "captured_at",
]


logger = logging.getLogger(__name__)


class JRAPipeline:
    """Persistent pipeline with caching, repair logs, and race-level entry outputs."""

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
        race_specs: list[dict[str, object]] | None = None,
        reprocess_raw: bool = False,
        force_rebuild: bool = False,
        aggressive_repair: bool = False,
    ) -> list[dict[str, str]]:
        logger.info(
            "Pipeline start race_limit=%s horse_limit=%s race_specs=%s race_urls=%s reprocess_raw=%s force_rebuild=%s aggressive_repair=%s",
            race_limit,
            horse_limit,
            len(race_specs) if race_specs else 0,
            len(race_urls) if race_urls else 0,
            reprocess_raw,
            force_rebuild,
            aggressive_repair,
        )

        state = self._load_state()
        existing_rows = [] if force_rebuild else self._read_existing_rows(self.config.output_csv)
        processed_races = set(state.get("processed_race_ids", []))
        failures = state.get("failures", {})
        all_new_rows: list[dict[str, str]] = []
        processed_this_run: list[str] = []
        issues: list[ParserIssue] = []

        races = self._resolve_races(
            race_specs=race_specs,
            race_urls=race_urls,
            race_limit=race_limit,
            reprocess_raw=reprocess_raw,
            issues=issues,
        )
        if not races:
            self._write_csv(existing_rows, self.config.output_csv, OUTPUT_COLUMNS)
            self._write_csv(build_entry_rows(existing_rows), self.config.entries_csv, ENTRY_COLUMNS)
            self._save_state(processed_races, failures, 0, 0)
            self._write_quality_report(issues, build_entry_rows(existing_rows))
            return existing_rows

        for race in races:
            if not force_rebuild and race.race_id in processed_races:
                logger.info("Skip already processed race race_id=%s", race.race_id)
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

            try:
                horses = self.parser.parse_race_detail(
                    race_html,
                    race.race_id,
                    race.race_name,
                    issue_sink=issues,
                    aggressive_repair=aggressive_repair,
                )
            except ValueError as exc:
                failures[race.race_url] = failures.get(race.race_url, 0) + 1
                logger.warning("Skip race due to parse failure race_id=%s err=%s", race.race_id, exc)
                continue

            if horse_limit is not None:
                horses = horses[:horse_limit]
            logger.info("Race=%s horses=%d", race.race_id, len(horses))

            race_rows: list[dict[str, str]] = []
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
                    current_entry=horse,
                    issue_sink=issues,
                    aggressive_repair=aggressive_repair,
                )
                if not rows:
                    race_failed = True
                race_rows.extend(rows)

            all_new_rows.extend(race_rows)
            if not race_failed:
                processed_races.add(race.race_id)
                processed_this_run.append(race.race_id)

        final_rows = validate_rows(existing_rows + all_new_rows)
        entry_rows = build_entry_rows(final_rows)
        self._write_csv(final_rows, self.config.output_csv, OUTPUT_COLUMNS)
        self._write_csv(entry_rows, self.config.entries_csv, ENTRY_COLUMNS)
        append_live_odds_snapshots(self.config.odds_snapshots_csv, entry_rows)
        self._save_state(processed_races, failures, len(processed_this_run), len(all_new_rows))
        self._write_quality_report(issues, entry_rows)

        logger.info(
            "Pipeline complete total_rows=%d entry_rows=%d new_rows=%d processed_races=%d",
            len(final_rows),
            len(entry_rows),
            len(all_new_rows),
            len(processed_this_run),
        )
        return final_rows

    def close(self) -> None:
        self.scraper.close()

    def _resolve_races(
        self,
        *,
        race_specs: list[dict[str, object]] | None,
        race_urls: list[str] | None,
        race_limit: int | None,
        reprocess_raw: bool,
        issues: list[ParserIssue],
    ) -> list[RaceLink]:
        if race_specs:
            races = [self._race_from_spec(spec) for spec in race_specs]
            if race_limit is not None:
                races = races[:race_limit]
            return races

        if race_urls:
            races = [self._race_from_spec({"source_url": url}) for url in race_urls]
            if race_limit is not None:
                races = races[:race_limit]
            return races

        race_list_html = self.scraper.fetch_relative(
            self.config.race_list_path,
            raw_name="race_list.html",
            use_cache=True,
            cache_only=reprocess_raw,
        )
        if not race_list_html:
            logger.error("Race list unavailable.")
            issues.append(
                ParserIssue(
                    stage="pipeline",
                    severity="high",
                    code="race_list_unavailable",
                    message="Race list HTML was unavailable.",
                    context={"race_list_path": self.config.race_list_path},
                )
            )
            return []

        races = self.parser.parse_race_list(race_list_html)
        if race_limit is not None:
            races = races[:race_limit]
        return races

    @staticmethod
    def _write_csv(rows: list[dict[str, str]], output_csv: Path, fieldnames: list[str]) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        with output_csv.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})

    @staticmethod
    def _read_existing_rows(path: Path) -> list[dict[str, str]]:
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", encoding="utf-8", newline="") as file_obj:
            return list(csv.DictReader(file_obj))

    def _load_state(self) -> dict:
        if not self.config.state_path.exists():
            return {"processed_race_ids": [], "failures": {}}
        with self.config.state_path.open("r", encoding="utf-8") as file_obj:
            return json.load(file_obj)

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
        with self.config.state_path.open("w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    def _write_quality_report(self, issues: list[ParserIssue], entry_rows: list[dict[str, str]]) -> None:
        severity_counts = Counter(issue.severity for issue in issues)
        code_counts = Counter(issue.code for issue in issues)
        snapshot_rows = self._read_existing_rows(self.config.odds_snapshots_csv)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "issue_count": len(issues),
            "issues_by_severity": dict(severity_counts),
            "issues_by_code": dict(code_counts),
            "repaired_row_count": sum(1 for issue in issues if issue.code in {"row_padding", "row_merge"}),
            "missing_current_odds_entries": sum(1 for row in entry_rows if not row.get("current_odds")),
            "entry_count": len(entry_rows),
            "live_snapshot_count": len(snapshot_rows),
            "issues": [issue.to_dict() for issue in issues],
        }
        with self.config.quality_report_path.open("w", encoding="utf-8") as file_obj:
            json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    def _race_from_spec(self, spec: dict[str, object]) -> RaceLink:
        race_name = str(spec.get("race_name", "")).strip()
        race_url = str(spec.get("source_url") or spec.get("race_url") or "").strip()
        race_date = str(spec.get("race_date", "")).strip()
        track = str(spec.get("track", "")).strip()
        race_number = str(spec.get("race_number", "")).strip()
        target_surface = str(spec.get("target_surface", "")).strip()
        target_distance = str(spec.get("target_distance", "")).strip()

        race_id = str(spec.get("race_id", "")).strip()
        if not race_id and race_date and track and race_number:
            compact_date = race_date.replace("-", "")
            race_id = f"{compact_date}_{track}_{int(race_number):02d}"
        if not race_id and race_url:
            race_id = self._build_direct_race_id(race_url)
        if not race_name:
            race_name = f"{track}{race_number}R" if track or race_number else f"direct_race_{race_id[:8]}"

        return RaceLink(
            race_id=race_id,
            race_name=race_name,
            race_url=race_url,
            race_date=race_date,
            track=track,
            race_number=race_number,
            target_surface=target_surface,
            target_distance=target_distance,
        )

    @staticmethod
    def _build_direct_race_id(race_url: str) -> str:
        return f"direct_{hashlib.md5(race_url.encode('utf-8')).hexdigest()[:12]}"


def append_live_odds_snapshots(
    snapshot_path: Path,
    entry_rows: list[dict[str, str]],
    *,
    captured_at: str | None = None,
) -> list[dict[str, str]]:
    if not entry_rows:
        return []

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    captured_at = captured_at or datetime.now(timezone.utc).isoformat()
    snapshots = [
        {
            "race_id": str(row.get("race_id", "")).strip(),
            "horse_id": str(row.get("horse_id", "")).strip(),
            "horse_name": str(row.get("horse_name", "")).strip(),
            "horse_number": str(row.get("horse_number", "")).strip(),
            "current_odds": str(row.get("current_odds", "")).strip(),
            "current_popularity": str(row.get("current_popularity", "")).strip(),
            "captured_at": captured_at,
        }
        for row in entry_rows
    ]

    existing_keys: set[tuple[str, str, str]] = set()
    if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
        with snapshot_path.open("r", encoding="utf-8", newline="") as file_obj:
            for row in csv.DictReader(file_obj):
                existing_keys.add(
                    (
                        str(row.get("race_id", "")).strip(),
                        str(row.get("horse_number", "")).strip(),
                        str(row.get("captured_at", "")).strip(),
                    )
                )

    pending_rows = [
        row
        for row in snapshots
        if (
            row["race_id"],
            row["horse_number"],
            row["captured_at"],
        ) not in existing_keys
    ]
    if not pending_rows:
        return []

    write_header = not snapshot_path.exists() or snapshot_path.stat().st_size == 0
    with snapshot_path.open("a", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=LIVE_ODDS_SNAPSHOT_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in pending_rows:
            writer.writerow(row)
    return pending_rows

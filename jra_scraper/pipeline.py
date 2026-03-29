class JRAPipeline:

    def run(
        self,
        race_limit: int = 3,
        horse_limit: int = 8,
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
            for idx, race_url in enumerate(race_urls, start=1):
                races.append(
                    RaceLink(
                        race_id=f"direct_{idx:03d}",
                        race_name=f"direct_race_{idx}",
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

            races = self.parser.parse_race_list(race_list_html)[:race_limit]
            logger.info("Parsed races=%d", len(races))

        for race in races:
            if race.race_id in processed_races and not force_rebuild:
                logger.info("Skip already processed race: %s", race.race_id)
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
            )[:horse_limit]
            logger.info("Race=%s horses=%d", race.race_id, len(horses))

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
                )
                race_rows.extend(rows)

            all_new_rows.extend(race_rows)

            if not race_failed:
                processed_races.add(race.race_id)
                processed_this_run.append(race.race_id)

        final_rows = validate_rows(existing_rows + all_new_rows)
        self._write_csv(final_rows, self.config.output_csv)
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
        with self.config.state_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

TRACKS = ("札幌", "函館", "福島", "新潟", "東京", "中山", "中京", "京都", "阪神", "小倉")
logger = logging.getLogger(__name__)


@dataclass
class RaceLink:
    race_id: str
    race_name: str
    race_url: str


@dataclass
class HorseEntry:
    race_id: str
    race_name: str
    horse_id: str
    horse_name: str
    horse_url: str


@dataclass
class HeaderMatch:
    index: int
    canonical: str
    raw: str


class JRAParser:
    """Parser tuned for JRA/JRADB style HTML pages."""
    LAST_3F_NEUTRAL_BASELINE = "36.0"

    RACE_ANCHOR_SELECTORS = (
        'a[href*="/JRADB/accessD.html"]',
        'a[href*="pw01sde"]',
        'a[href*="pw01dde"]',
    )

    HORSE_ANCHOR_SELECTORS = (
        "td.horse a[href]",
        "table tr td:nth-child(3) a[href]",
        'a[href*="/JRADB/accessU.html"]',
        'a[href*="/JRADB/accessC.html"]',
    )

    HEADER_ALIASES: dict[str, tuple[str, ...]] = {
        "date": ("日付", "年月日"),
        "course": ("開催", "競馬場", "場"),
        "race_name": ("レース名", "レース", "競走名", "前走"),
        "position": ("着順", "着", "4走前"),
        "time": ("タイム", "走破タイム"),
        "margin": ("着差",),
        "weight": ("斤量",),
        "jockey": ("騎手", "騎手名"),
        "distance": ("距離", "前々走", "3走前"),
        "pace": ("前半", "前3F", "通過前半", "前半3F"),
        "last_3f": ("上り", "上り3F", "上がり", "上がり3F", "末3F", "後3F"),
        "track_condition": ("馬場", "馬場状態"),
        "weather": ("天候",),
        "passing_order": ("通過", "4角", "4C", "コーナー通過順"),
        "odds": ("単勝", "単勝オッズ", "オッズ"),
        "popularity": ("人気",),
    }

    REQUIRED_CANONICAL_HEADERS = ("position", "last_3f", "popularity")

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def parse_race_list(self, html: str) -> list[RaceLink]:
        soup = BeautifulSoup(html, "html.parser")
        links: list[RaceLink] = []

        for selector in self.RACE_ANCHOR_SELECTORS:
            for anchor in soup.select(selector):
                href = anchor.get("href") or ""
                race_name = " ".join(anchor.get_text(" ", strip=True).split())
                if not href or not race_name:
                    continue
                links.append(
                    RaceLink(
                        race_id=self._build_race_id(href, race_name),
                        race_name=race_name,
                        race_url=urljoin(self.base_url, href),
                    )
                )
        return self._dedupe_races(links)

    def parse_race_detail(self, html: str, race_id: str, race_name: str) -> list[HorseEntry]:
        soup = BeautifulSoup(html, "html.parser")
        horses: list[HorseEntry] = []

        for selector in self.HORSE_ANCHOR_SELECTORS:
            for anchor in soup.select(selector):
                href = anchor.get("href") or ""
                horse_name = " ".join(anchor.get_text(" ", strip=True).split())
                if not href or not horse_name:
                    continue
                if not self._looks_like_horse_link(href, horse_name):
                    continue
                horses.append(
                    HorseEntry(
                        race_id=race_id,
                        race_name=race_name,
                        horse_id=self._extract_horse_id(href, horse_name),
                        horse_name=horse_name,
                        horse_url=urljoin(self.base_url, href),
                    )
                )

        if not horses:
            for row in soup.select("table tr"):
                tds = row.select("td")
                if len(tds) < 3:
                    continue
                anchor = tds[2].select_one("a[href]")
                if not anchor:
                    continue
                href = anchor.get("href") or ""
                horse_name = " ".join(anchor.get_text(" ", strip=True).split())
                if not href or not horse_name:
                    continue
                horses.append(
                    HorseEntry(
                        race_id=race_id,
                        race_name=race_name,
                        horse_id=self._extract_horse_id(href, horse_name),
                        horse_name=horse_name,
                        horse_url=urljoin(self.base_url, href),
                    )
                )
        return self._dedupe_horses(horses)

    def parse_horse_last5(
        self,
        html: str,
        race_id: str,
        horse_id: str,
        horse_name: str,
        horse_url: str,
        field_size: str = "",
    ) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        table = self._select_last5_table(soup)
        if table is None:
            logger.warning("No suitable last5 table found for horse=%s url=%s", horse_name, horse_url)
            return []

        headers = self._extract_headers(table)
        header_matches = self._build_header_matches(headers)

        found_canonicals = {m.canonical for m in header_matches}
        for required in self.REQUIRED_CANONICAL_HEADERS:
            if required not in found_canonicals:
                logger.warning(
                    "Missing expected canonical header '%s' in horse history table for horse=%s raw_headers=%s",
                    required,
                    horse_name,
                    headers,
                )

        body_rows = [tr for tr in table.select("tr") if tr.select("td")]

        out: list[dict[str, str]] = []
        for run_idx, tr in enumerate(body_rows[:5], start=1):
            values = [self._norm(td.get_text(" ", strip=True)) for td in tr.select("td")]
            if not any(values):
                continue

            mapped = self._map_row(header_matches, values)
            self._apply_last_3f_fallback(
                mapped,
                horse_name=horse_name,
                race_id=race_id,
                run_index=run_idx,
            )
            mapped.update(
                {
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "horse_url": horse_url,
                    "run_index": str(run_idx),
                    "field_size": field_size,
                }
            )
            out.append(mapped)

        return out

    def _apply_last_3f_fallback(
        self,
        row: dict[str, str],
        *,
        horse_name: str,
        race_id: str,
        run_index: int,
    ) -> None:
        if row.get("last_3f"):
            return
        row["last_3f"] = self.LAST_3F_NEUTRAL_BASELINE
        logger.warning(
            "Missing last_3f -> fallback baseline applied horse=%s race_id=%s run_index=%s last_3f=%s",
            horse_name,
            race_id,
            run_index,
            row["last_3f"],
        )

    def _select_last5_table(self, soup: BeautifulSoup):
        best_table = None
        best_score = -1

        for table in soup.select("table"):
            headers = self._extract_headers(table)
            if not headers:
                continue

            matches = self._build_header_matches(headers)
            canonicals = {m.canonical for m in matches}
            score = 0

            if "position" in canonicals:
                score += 3
            if "race_name" in canonicals:
                score += 3
            if "distance" in canonicals:
                score += 2
            if "time" in canonicals:
                score += 2
            if "last_3f" in canonicals:
                score += 3
            if "popularity" in canonicals:
                score += 2
            if "date" in canonicals:
                score += 1
            if "jockey" in canonicals:
                score += 1
            if "weight" in canonicals:
                score += 1

            body_row_count = len([tr for tr in table.select("tr") if tr.select("td")])
            if body_row_count >= 5:
                score += 2

            if score > best_score:
                best_score = score
                best_table = table

        return best_table

    def _extract_headers(self, table) -> list[str]:
        header_rows = table.select("tr")
        if not header_rows:
            return []

        for tr in header_rows[:3]:
            cells = tr.select("th")
            if not cells:
                cells = tr.select("td")
            values = [self._norm(cell.get_text(" ", strip=True)) for cell in cells]
            non_empty = [v for v in values if v]
            if len(non_empty) >= 3:
                return values

        return []

    def _build_header_matches(self, headers: list[str]) -> list[HeaderMatch]:
        matches: list[HeaderMatch] = []
        for idx, raw_header in enumerate(headers):
            canonical = self._canonicalize_header(raw_header)
            if canonical:
                matches.append(HeaderMatch(index=idx, canonical=canonical, raw=raw_header))
        return matches

    def _canonicalize_header(self, header: str) -> str | None:
        normalized = self._normalize_header_label(header)
        for canonical, aliases in self.HEADER_ALIASES.items():
            alias_norms = {self._normalize_header_label(a) for a in aliases}
            if normalized in alias_norms:
                return canonical
        return None

    @staticmethod
    def _normalize_header_label(value: str) -> str:
        value = JRAParser._norm(value)
        value = value.replace(" ", "")
        value = value.replace("　", "")
        value = value.replace("Ｆ", "F").replace("３", "3").replace("４", "4")
        value = value.replace("ｆ", "F").replace("ｆ", "F")
        return value

    @staticmethod
    def _map_row(header_matches: list[HeaderMatch], values: list[str]) -> dict[str, str]:
        record = {
            "date": "",
            "race_name": "",
            "course": "",
            "distance": "",
            "position": "",
            "time": "",
            "margin": "",
            "weight": "",
            "jockey": "",
            "pace": "",
            "last_3f": None,
            "track_condition": "",
            "weather": "",
            "passing_order": "",
            "odds": "",
            "popularity": "",
        }

        for match in header_matches:
            if match.index >= len(values):
                continue
            value = values[match.index]
            if not value:
                continue
            record[match.canonical] = value

        # split combined distance field (e.g., 芝2000 / ダ1200)
        raw_dist = record["distance"]
        if raw_dist:
            if not record["course"]:
                m_course = re.search(r"(芝|ダ|ダート|障害)", raw_dist)
                if m_course:
                    record["course"] = "ダート" if m_course.group(1) in ("ダ", "ダート") else m_course.group(1)
            m_dist = re.search(r"(\d{3,4})", raw_dist)
            if m_dist:
                record["distance"] = m_dist.group(1)

        # if course field contains venue text plus surface/distance, salvage surface
        raw_course = record["course"]
        if raw_course and raw_course not in ("芝", "ダート", "障害"):
            m_course = re.search(r"(芝|ダ|ダート|障害)", raw_course)
            if m_course:
                record["course"] = "ダート" if m_course.group(1) in ("ダ", "ダート") else m_course.group(1)

        # normalize passing order to last corner if pattern like 12-10-8-5
        if record["passing_order"]:
            parts = [p for p in re.split(r"[-→]", record["passing_order"]) if p.strip()]
            if parts:
                record["passing_order"] = parts[-1].strip()

        return record

    @staticmethod
    def _build_race_id(href: str, race_name: str) -> str:
        date = ""
        m = re.search(r"(20\d{6})", href)
        if m:
            date = m.group(1)
        track = next((t for t in TRACKS if t in race_name), "unknown")
        m_r = re.search(r"(\d{1,2})R", race_name)
        race_no = f"{int(m_r.group(1)):02d}" if m_r else "00"
        if date:
            return f"{date}_{track}_{race_no}"
        digest = hashlib.md5((href + race_name).encode("utf-8")).hexdigest()[:10]
        return f"race_{digest}"

    @staticmethod
    def _extract_horse_id(href: str, horse_name: str) -> str:
        parsed = urlparse(href)
        query = parse_qs(parsed.query)
        cname = query.get("CNAME", [""])[0]
        if cname:
            return cname
        digits = "".join(ch for ch in href if ch.isdigit())
        if digits:
            return digits
        cleaned = re.sub(r"\s+", "_", horse_name.lower())
        return re.sub(r"[^a-z0-9_\-ぁ-んァ-ヶ一-龠]", "", cleaned) or "unknown_horse"

    @staticmethod
    def _looks_like_horse_link(href: str, name: str) -> bool:
        lowered = href.lower()
        if any(token in lowered for token in ("accessu", "horse", "uma", "pw01ude", "pw01uce")):
            return True
        return len(name) >= 2 and "詳細" not in name and "オッズ" not in name

    @staticmethod
    def _dedupe_races(items: list[RaceLink]) -> list[RaceLink]:
        seen: set[str] = set()
        out: list[RaceLink] = []
        for item in items:
            if item.race_url in seen:
                continue
            seen.add(item.race_url)
            out.append(item)
        return out

    @staticmethod
    def _dedupe_horses(items: list[HorseEntry]) -> list[HorseEntry]:
        seen: set[str] = set()
        out: list[HorseEntry] = []
        for item in items:
            if item.horse_url in seen:
                continue
            seen.add(item.horse_url)
            out.append(item)
        return out

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.split())

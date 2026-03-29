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


class JRAParser:
    """Parser tuned for JRA/JRADB style HTML pages."""

    RACE_ANCHOR_SELECTORS = (
        'a[href*="/JRADB/accessD.html"]',
        'a[href*="pw01sde"]',
        'a[href*="pw01dde"]',
    )

    HORSE_ANCHOR_SELECTORS = (
        'td.horse a[href]',
        'table tr td:nth-child(3) a[href]',
        'a[href*="/JRADB/accessU.html"]',
        'a[href*="/JRADB/accessC.html"]',
    )

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
    ) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        table = self._select_last5_table(soup)
        if table is None:
            return []

        headers = [self._norm(cell.get_text(" ", strip=True)) for cell in table.select("tr th")]
        for required in ("着順", "上り", "上り3F", "人気"):
            if required not in headers:
                logger.warning("Missing expected header '%s' in horse history table", required)

        body_rows = [tr for tr in table.select("tr") if tr.select("td")]

        out: list[dict[str, str]] = []
        for run_idx, tr in enumerate(body_rows[:5], start=1):
            values = [self._norm(td.get_text(" ", strip=True)) for td in tr.select("td")]
            if not any(values):
                continue
            mapped = self._map_row(headers, values)
            mapped.update(
                {
                    "race_id": race_id,
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "horse_url": horse_url,
                    "run_index": str(run_idx),
                }
            )
            out.append(mapped)
        return out

    def _select_last5_table(self, soup: BeautifulSoup):
        keyword_sets = [{"日付", "開催", "レース名", "着順"}, {"前走", "前々走", "3走前", "4走前"}]
        for table in soup.select("table"):
            headers = {self._norm(th.get_text(" ", strip=True)) for th in table.select("tr th")}
            if not headers:
                continue
            if any(len(headers & ks) >= 2 for ks in keyword_sets):
                return table
        return None

    @staticmethod
    def _map_row(headers: list[str], values: list[str]) -> dict[str, str]:
        mapping = {
            "日付": "date",
            "開催": "course",
            "レース名": "race_name",
            "着順": "position",
            "タイム": "time",
            "斤量": "weight",
            "騎手": "jockey",
            "距離": "distance",
            "前半": "pace",
            "前3F": "pace",
            "上り": "last_3f",
            "上り3F": "last_3f",
            "馬場": "track_condition",
            "天候": "weather",
            "通過": "passing_order",
            "4角": "passing_order",
            "単勝": "odds",
            "人気": "popularity",
            "前走": "race_name",
            "前々走": "course",
            "3走前": "distance",
            "4走前": "position",
        }
        record = {
            "date": "",
            "race_name": "",
            "course": "",
            "distance": "",
            "position": "",
            "time": "",
            "weight": "",
            "jockey": "",
            "pace": "",
            "last_3f": "",
            "track_condition": "",
            "weather": "",
            "passing_order": "",
            "odds": "",
            "popularity": "",
        }
        for idx, value in enumerate(values):
            key = headers[idx] if idx < len(headers) else ""
            target = mapping.get(key)
            if target:
                record[target] = value

        # split combined distance field (e.g., 芝2000)
        raw_dist = record["distance"]
        if raw_dist:
            if not record["course"]:
                m_course = re.search(r"(芝|ダ|ダート|障害)", raw_dist)
                if m_course:
                    record["course"] = "ダート" if m_course.group(1) in ("ダ", "ダート") else m_course.group(1)
            m_dist = re.search(r"(\d{3,4})", raw_dist)
            if m_dist:
                record["distance"] = m_dist.group(1)

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
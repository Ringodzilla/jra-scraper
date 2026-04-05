from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScrapeConfig:
    """Configuration for scraping and persistent pipeline operation."""

    base_url: str = "https://www.jra.go.jp"
    race_list_path: str = "/JRADB/accessS.html"

    output_csv: Path = Path("data/processed/race_last5.csv")
    race_info_csv: Path = Path("data/processed/race_info.csv")
    raw_dir: Path = Path("data/raw")
    state_path: Path = Path("data/processed/pipeline_state.json")

    timeout: int = 20
    max_retries: int = 3
    delay_seconds: float = 1.2

    def ensure_dirs(self) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        self.race_info_csv.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

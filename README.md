# JRA Race Data Scraper

JRAのレースデータを取得し、**EVモデリングに直接使える整形済みCSV**を生成する継続運用向けパイプラインです。

## What this pipeline now guarantees

- **Structured output columns**
  - `date, race_name, course, distance, position, time, weight, jockey`
  - `pace, last_3f, track_condition, weather, passing_order, odds, popularity`
- **Unique identifiers**
  - `race_id` = `YYYYMMDD_track_raceNo`
  - `horse_id` = URL由来ID（取得できない場合は馬名正規化）
  - `row_id` = 安定ハッシュ（冪等更新用）
- **Normalization**
  - `distance` / `position` / `popularity` は数値抽出
  - `time` / `pace` は秒 or 数値へ正規化
  - `weight` / `last_3f` / `odds` は数値化
  - `date` は `YYYY-MM-DD`
- **Raw persistence + reprocess**
  - 取得HTMLは `data/raw/` へ保存
  - `--reprocess-raw` でfetchせず再処理可能
- **Incremental + idempotent pipeline**
  - `pipeline_state.json` の `processed_race_ids` で既処理レースをスキップ
  - CSV再実行時も `row_id` 重複排除でデータ重複なし

## Architecture

- `jra_scraper/scraper.py`: HTTP, retry/backoff, raw cache, cache-only再処理
- `jra_scraper/parser.py`: JRA/JRADB構造の解析と列マッピング
- `jra_scraper/validation.py`: 型正規化・ID付与・重複除去・5件上限
- `jra_scraper/pipeline.py`: 増分更新、状態管理、CSV出力

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python scripts/run_example.py \
  --race-limit 2 \
  --horse-limit 5 \
  --output-path data/processed/race_last5.csv \
  --state-path data/processed/pipeline_state.json
```

オプション:

- `--reprocess-raw`: raw HTMLのみを使って再処理
- `--force-rebuild`: 増分処理を無視して全再構築

## CSV schema (`race_last5.csv`)

- `row_id`
- `race_id`
- `horse_id`
- `horse_name`
- `run_index`
- `date`
- `race_name`
- `course`
- `distance`
- `position`
- `time`
- `weight`
- `jockey`
- `pace`
- `last_3f`
- `track_condition`
- `weather`
- `passing_order` (4角通過順)
- `odds`
- `popularity`

## Testing

```bash
python -m unittest discover -s tests -v
```

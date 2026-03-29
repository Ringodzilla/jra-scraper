# JRA Race Data Scraper / EV Pipeline

JRAデータ取得 → 整形 → EV算出 → 買い目生成 → note投稿準備までを再現可能に実行するパイプラインです。

## Config-driven execution

レースURLはコードにハードコードせず `config/races.json` で管理します。

`config/races.json` の各要素は以下キーを持ちます:

- `race_name`
- `race_date`
- `track`
- `race_number`
- `source_url`
- `output_slug`
- `note_title`
- `note_tags`

## One-command analysis pipeline

```bash
python scripts/run_pipeline.py
```

このコマンドで以下を順に実行します:

1. スクレイピング（`source_url` を直接入力として使用）
2. 構造化CSV更新（`data/processed/race_last5.csv`）
3. EV算出（`data/processed/race_ev.csv`）
4. 買い目生成
5. note Markdown生成（`report/note.md`）
6. publish payload生成（`report/publish_payload.json`）

## Publishing phase (separated)

```bash
python scripts/publish_note.py
```

- 分析フェーズと投稿フェーズを分離しています。
- このリポジトリでは安全のため実投稿は行わず、`report/publish_preview.txt` を生成する dry-run 実装です。

## Existing scripts

- `scripts/run_example.py`: 既存スクレイプ実行例
- `scripts/run_analysis.py`: 既存分析実行例（単体）

## Testing

```bash
python -m unittest discover -s tests -v
```

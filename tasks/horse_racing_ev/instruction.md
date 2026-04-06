# Horse Racing EV Task

Given historical horse-racing input files, produce model predictions and win tickets.

## Inputs
- race_last5.csv
- entries.csv
- odds.csv

## Expected outputs
- /workspace/output/predictions.csv
- /workspace/output/tickets.json
- /workspace/output/ev_ranking.csv
- /workspace/output/experiment_log.tsv

The score is written to `/logs/reward.txt` by the task tests.

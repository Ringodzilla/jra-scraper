# Objective

Build and iteratively improve a horse-racing betting agent that maximizes out-of-sample expected return on historical races.

# Hard constraints

- Do not modify task evaluation scripts.
- Do not alter input/output file paths.
- Do not hardcode race results.
- Do not use future information.
- Do not optimize on validation labels directly.
- Keep the system deterministic where possible.

# Inputs

The harness receives:
- race_last5.csv
- entries.csv
- odds.csv

# Required outputs

The harness must write:
- /workspace/output/predictions.csv
- /workspace/output/tickets.json
- /workspace/output/ev_ranking.csv
- /workspace/output/experiment_log.tsv

# What to improve

You may improve:
- feature engineering
- pace scenario modeling
- weight adjustment
- jockey/trainer priors
- EV ranking logic
- Kelly sizing
- ticket construction rules

# What matters

Primary metric:
- out-of-sample ROI

Secondary metrics:
- hit rate
- stability
- reasonable ticket count

# Preferred modeling ideas

- estimate win probability first
- derive place/top3 proxies if useful
- separate ability score and bet selection
- penalize too many low-edge tickets
- preserve explainability in outputs

# Editing strategy

- make small changes
- benchmark after each change
- keep only improvements
- log why the change might help

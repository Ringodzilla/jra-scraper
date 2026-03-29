import pandas as pd
import numpy as np

# =========================
# 設定（調整ポイント）
# =========================
WEIGHT_POSITION = 0.5
WEIGHT_LAST3F = 0.3
WEIGHT_POPULARITY = 0.2

# =========================
# データ読み込み
# =========================
def load_data(path="data/processed/race_last5.csv"):
    df = pd.read_csv(path)
    return df

# =========================
# 前処理
# =========================
def preprocess(df):
    df["position"] = pd.to_numeric(df["position"], errors="coerce")
    df["last_3f"] = pd.to_numeric(df["last_3f"], errors="coerce")
    df["popularity"] = pd.to_numeric(df["popularity"], errors="coerce")

    return df

# =========================
# 馬ごと集約
# =========================
def aggregate_horse(df):
    grouped = df.groupby("horse_name")

    agg = grouped.agg({
        "position": "mean",
        "last_3f": "mean",
        "popularity": "mean",
    }).reset_index()

    return agg

# =========================
# スコア計算
# =========================
def calculate_score(df):
    # 小さいほど良い指標を逆転
    df["position_score"] = 1 / df["position"]
    df["last3f_score"] = 1 / df["last_3f"]
    df["popularity_score"] = 1 / df["popularity"]

    df["score"] = (
        df["position_score"] * WEIGHT_POSITION +
        df["last3f_score"] * WEIGHT_LAST3F +
        df["popularity_score"] * WEIGHT_POPULARITY
    )

    return df

# =========================
# 勝率pに変換（softmax）
# =========================
def calculate_probability(df):
    exp_scores = np.exp(df["score"])
    df["p"] = exp_scores / exp_scores.sum()
    return df

# =========================
# 仮オッズ（※後で差し替え）
# =========================
def attach_dummy_odds(df):
    df["odds"] = np.linspace(3, 30, len(df))
    return df

# =========================
# EV計算
# =========================
def calculate_ev(df):
    df["EV"] = df["p"] * df["odds"]
    return df

# =========================
# 実行
# =========================
def run():
    df = load_data()
    df = preprocess(df)
    df = aggregate_horse(df)
    df = calculate_score(df)
    df = calculate_probability(df)
    df = attach_dummy_odds(df)
    df = calculate_ev(df)

    df = df.sort_values("EV", ascending=False)

    print("\n=== EVランキング ===")
    print(df[["horse_name", "p", "odds", "EV"]])

    return df


if __name__ == "__main__":
    run()

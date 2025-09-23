"""
src/features.py
Create rolling and matchup features.
"""
import pandas as pd

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["target"] = (df["home_score"] > df["away_score"]).astype(int)
    df["month"] = df["game_date"].dt.month
    return df

if __name__ == "__main__":
    print("Features module ready. Use build_features(df).")

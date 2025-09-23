"""
src/data.py
Load and validate MLB data tables.
"""
from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def load_games(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["game_date"])
    required = {"game_id","game_date","home_team","away_team","home_score","away_score"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df.sort_values("game_date")

def save_processed(df: pd.DataFrame, name: str = "games_clean.csv") -> Path:
    out = PROCESSED_DIR / name
    df.to_csv(out, index=False)
    return out

if __name__ == "__main__":
    print("Data module ready. Use load_games(csv_path).")

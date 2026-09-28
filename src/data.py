import pandas as pd

from src.config import RAW_DATA


def load_sales() -> pd.DataFrame:
    if not RAW_DATA.exists():
        raise FileNotFoundError(f"{RAW_DATA} not found; see 'Data' in README.md for the Kaggle download")
    return pd.read_csv(RAW_DATA, parse_dates=["date"])

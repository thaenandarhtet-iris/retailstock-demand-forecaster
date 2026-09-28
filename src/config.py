from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA = ROOT / "data" / "raw" / "train.csv"
PROCESSED = ROOT / "data" / "processed"

HOLDOUT_DAYS = 90
LEAD_TIME_DAYS = 7
SERVICE_LEVEL = 0.95
SEED = 42

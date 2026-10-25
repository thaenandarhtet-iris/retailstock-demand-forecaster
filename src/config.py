from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DATA = ROOT / "data" / "raw" / "train.csv"
PROCESSED = ROOT / "data" / "processed"

HOLDOUT_DAYS = 90
LEAD_TIME_DAYS = 7
SERVICE_LEVEL = 0.95
SEED = 42

LANDING = ROOT / "landing" / "raw"
M5_DIR = ROOT / "data" / "raw" / "m5"
WAREHOUSE = ROOT / "warehouse" / "retailstock.duckdb"
LOOKER = PROCESSED / "looker"

M5_STORE = "CA_1"
M5_DEPT = "FOODS_3"
M5_SKUS = 200

PROMO_THRESHOLD = 0.10
REGULAR_WINDOW_WEEKS = 8
PRE_WEEKS = 4
POST_WEEKS = 2
GROSS_MARGIN = 0.30

USER_AGENT = "RetailStock/2.0 (+https://github.com/thaenandarhtet-iris/retailstock-demand-forecaster)"

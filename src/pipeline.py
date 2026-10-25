"""
Run everything.

Usage:
    python -m src.pipeline         # 1.0: forecast all SKUs, size inventory, export dashboard data
    python -m src.pipeline --v2    # 2.0: load the warehouse, build dbt, promo, elasticity, backtest, Looker exports
"""
import argparse
import subprocess
import sys
from pathlib import Path

from src import backtest, dashboard, forecast, inventory
from src.config import ROOT
from src.pricing import elasticity, export, promo
from warehouse import load


def run_v2():
    load.main()
    dbt = Path(sys.executable).parent / "dbt"  # the venv's dbt, even when the venv isn't activated
    subprocess.run([str(dbt), "build", "--profiles-dir", "."], check=True, cwd=ROOT / "dbt")
    promo.main()
    elasticity.main()
    backtest.main()
    export.main()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v2", action="store_true", help="run the 2.0 price and promo pipeline")
    if parser.parse_args().v2:
        run_v2()
    else:
        forecast.main()
        inventory.main()
        dashboard.main()

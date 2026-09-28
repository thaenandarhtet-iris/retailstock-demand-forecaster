"""
Run everything: forecast all SKUs, size inventory, export the dashboard workbook.

Usage:
    python -m src.pipeline
"""
from src import dashboard, forecast, inventory

if __name__ == "__main__":
    forecast.main()
    inventory.main()
    dashboard.main()

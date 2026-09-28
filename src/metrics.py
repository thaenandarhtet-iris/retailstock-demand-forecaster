import numpy as np


def wape(actual, forecast) -> float:
    """Weighted absolute percentage error: total absolute error / total actual demand, in %."""
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    return float(np.abs(actual - forecast).sum() / actual.sum() * 100)


def mape(actual, forecast) -> float:
    """Mean absolute percentage error in %, skipping days with zero actual demand."""
    actual, forecast = np.asarray(actual, float), np.asarray(forecast, float)
    nonzero = actual != 0
    return float(np.mean(np.abs(actual[nonzero] - forecast[nonzero]) / actual[nonzero]) * 100)


def bias(actual, forecast) -> float:
    """Mean forecast minus actual, in units per day. Positive means over-forecasting."""
    return float(np.mean(np.asarray(forecast, float) - np.asarray(actual, float)))

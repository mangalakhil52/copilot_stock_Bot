from __future__ import annotations

import math
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from strategy import SwingPick
from tracker.market_data import GoogleFinanceMarketData


def _ema(values: Sequence[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1.0 - alpha) * result[-1])
    return result


def _sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    for index in range(len(values)):
        if index + 1 < period:
            result.append(None)
        else:
            window = values[index + 1 - period:index + 1]
            result.append(sum(window) / period)
    return result


def _rsi(values: Sequence[float], period: int = 14) -> List[Optional[float]]:
    if not values:
        return []
    result: List[Optional[float]] = [None]
    gains: List[float] = []
    losses: List[float] = []

    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

        if index < period:
            result.append(None)
            continue

        if index == period:
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gains[-1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[-1]) / period

        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - (100.0 / (1.0 + rs)))

    return result


def _macd(values: Sequence[float]):
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    line = [a - b for a, b in zip(ema12, ema26)]
    signal = _ema(line, 9)
    histogram = [a - b for a, b in zip(line, signal)]
    return line, signal, histogram


def _finite(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(float(value))


def generate_stock_chart(
    pick: SwingPick,
    market_data: GoogleFinanceMarketData,
    lookback_days: int = 140,
) -> Optional[Path]:
    """Generate one detailed PNG chart for a swing pick."""
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    rows = market_data.get_historical_data(
        symbol=pick.ticker,
        start_date=start_date,
        end_date=end_date,
    )

    rows = [
        row for row in rows
        if _finite(row.get("open"))
        and _finite(row.get("high"))
        and _finite(row.get("low"))
        and _finite(row.get("close"))
    ]

    if len(rows) < 35:
        return None

    dates = [row["date"] for row in rows]
    opens = [float(row["open"]) for row in rows]
    highs = [float(row["high"]) for row in rows]
    lows = [float(row["low"]) for row in rows]
    closes = [float(row["close"]) for row in rows]
    volumes = [float(row.get("volume") or 0.0) for row in rows]

    ema20 = _ema(closes, 20)
    sma50 = _sma(closes, 50)
    rsi = _rsi(closes, 14)
    macd_line, macd_signal, macd_hist = _macd(closes)

    fig = plt.figure(figsize=(12, 15), dpi=150)
    grid = fig.add_gridspec(4, 1, height_ratios=[4.8, 1.3, 1.5, 1.5], hspace=0.08)
    ax_price = fig.add_subplot(grid[0])
    ax_volume = fig.add_subplot(grid[1], sharex=ax_price)
    ax_rsi = fig.add_subplot(grid[2], sharex=ax_price)
    ax_macd = fig.add_subplot(grid[3], sharex=ax_price)

    x = list(range(len(rows)))
    candle_width = 0.62

    for i, (o, h, l, c) in enumerate(zip(opens, highs, lows, closes)):
        up = c >= o
        ax_price.vlines(i, l, h, linewidth=0.8)
        lower = min(o, c)
        height = max(abs(c - o), 0.01)
        rect = Rectangle(
            (i - candle_width / 2, lower),
            candle_width,
            height,
            fill=up,
            linewidth=0.8,
        )
        ax_price.add_patch(rect)

    ax_price.plot(x, ema20, linewidth=1.3, label="EMA20")
    valid_sma = [value if value is not None else float("nan") for value in sma50]
    ax_price.plot(x, valid_sma, linewidth=1.2, label="SMA50")

    ax_price.axhline(pick.entry, linestyle="--", linewidth=1.2, label=f"Entry ₹{pick.entry:.2f}")
    ax_price.axhline(pick.target, linestyle="--", linewidth=1.2, label=f"Target ₹{pick.target:.2f}")
    ax_price.axhline(pick.stop_loss, linestyle="--", linewidth=1.2, label=f"SL ₹{pick.stop_loss:.2f}")

    ax_price.set_title(
        f"COPILOT SWING ALERT — {pick.ticker} | Strategy V2 | Daily NSE",
        fontsize=16,
        fontweight="bold",
        pad=14,
    )
    ax_price.set_ylabel("Price (₹)")
    ax_price.legend(loc="upper left", ncol=3, fontsize=8)
    ax_price.grid(alpha=0.2)

    for i, volume in enumerate(volumes):
        ax_volume.bar(i, volume, width=0.62)
    ax_volume.set_ylabel("Volume")
    ax_volume.grid(alpha=0.2)

    rsi_values = [value if value is not None else float("nan") for value in rsi]
    ax_rsi.plot(x, rsi_values, linewidth=1.3, label="RSI 14")
    ax_rsi.axhline(70, linestyle="--", linewidth=0.8)
    ax_rsi.axhline(50, linestyle=":", linewidth=0.8)
    ax_rsi.axhline(30, linestyle="--", linewidth=0.8)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI")
    ax_rsi.legend(loc="upper left", fontsize=8)
    ax_rsi.grid(alpha=0.2)

    ax_macd.bar(x, macd_hist, width=0.62, alpha=0.45)
    ax_macd.plot(x, macd_line, linewidth=1.1, label="MACD")
    ax_macd.plot(x, macd_signal, linewidth=1.0, label="Signal")
    ax_macd.axhline(0, linewidth=0.8)
    ax_macd.set_ylabel("MACD")
    ax_macd.legend(loc="upper left", fontsize=8)
    ax_macd.grid(alpha=0.2)

    tick_positions = list(range(0, len(rows), max(1, len(rows) // 8)))
    labels = [dates[index].strftime("%d %b") for index in tick_positions]
    ax_macd.set_xticks(tick_positions)
    ax_macd.set_xticklabels(labels, rotation=0)

    for axis in (ax_price, ax_volume, ax_rsi):
        plt.setp(axis.get_xticklabels(), visible=False)

    info = (
        f"{pick.ticker}  |  Entry ₹{pick.entry:.2f}  |  "
        f"Target ₹{pick.target:.2f}  |  SL ₹{pick.stop_loss:.2f}  |  "
        f"Score {pick.score:.1f}  |  RSI {pick.rsi:.1f}  |  "
        f"Hold {pick.holding_period}"
    )
    fig.text(0.5, 0.018, info, ha="center", fontsize=9)
    fig.text(
        0.5,
        0.004,
        "For research/tracking only. Validate the setup before taking any trade.",
        ha="center",
        fontsize=7,
    )

    output_dir = Path(tempfile.gettempdir()) / "copilot_stock_bot_charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{pick.ticker}_{date.today().isoformat()}.png"
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import requests

from strategy import SwingPick


STRATEGY_VERSION = "v2"


def format_telegram_alert(picks: List[SwingPick]) -> str:
    """Build the daily Telegram text alert for the active strategy."""
    if not picks:
        return (
            "📉 *Indian Swing Stock Alerts*\n\n"
            f"Strategy: `{STRATEGY_VERSION.upper()}`\n"
            "No strong swing picks found today."
        )

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    message_lines = [
        "🚨 *COPILOT SWING ALERT*",
        f"Strategy: `{STRATEGY_VERSION.upper()}`",
        f"Run: `{run_time}`",
        "",
        "_Actionable candidates generated after the market scan._",
    ]

    for index, pick in enumerate(picks, start=1):
        volume_ratio = (
            f"{pick.volume / pick.avg_volume:.2f}x"
            if pick.avg_volume and pick.avg_volume > 0
            else "N/A"
        )
        distance_ema20 = (
            ((pick.close - pick.ema20) / pick.ema20) * 100
            if pick.ema20
            else 0
        )
        risk_reward = (
            pick.reward_pct / pick.risk_pct
            if pick.risk_pct and pick.risk_pct > 0
            else 0
        )

        block = (
            f"*{index}️⃣ {pick.ticker}* — _{pick.name}_\n"
            f"🏭 Industry: `{pick.industry or 'N/A'}`\n"
            f"💰 Entry: `₹{pick.entry:.2f}`\n"
            f"🎯 Target: `₹{pick.target:.2f}`\n"
            f"🛑 Stop Loss: `₹{pick.stop_loss:.2f}`\n"
            f"⚖️ Risk/Reward: `1:{risk_reward:.2f}`\n"
            f"📊 Score: `{pick.score:.1f}`\n"
            f"📈 RSI: `{pick.rsi:.1f}`  MACD: `{pick.macd:.2f}`\n"
            f"📦 Volume: `{volume_ratio}`\n"
            f"📐 Above EMA20: `{distance_ema20:.1f}%`\n"
            f"⏳ Holding: `{pick.holding_period}`\n"
            f"_Why: {pick.comment}_"
        )
        message_lines.extend(["", block])

    message_lines.extend(
        [
            "",
            "📊 _A detailed chart for each stock follows this message._",
            "",
            "⚠️ _For research/tracking only. Validate the setup before taking any trade._",
        ]
    )
    return "\n".join(message_lines)


def _generate_charts(picks: Sequence[SwingPick]) -> List[Tuple[SwingPick, Path]]:
    """Generate one chart per pick without changing pick-to-chart mapping on failures."""
    try:
        from chart_generator import generate_stock_chart
        from tracker.market_data import GoogleFinanceMarketData

        if not os.getenv("GOOGLE_SHEET_ID") or not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
            print("Chart generation skipped: Google Sheets credentials are unavailable.")
            return []

        market_data = GoogleFinanceMarketData()
        results: List[Tuple[SwingPick, Path]] = []

        for pick in picks:
            try:
                chart_path = generate_stock_chart(
                    pick=pick,
                    market_data=market_data,
                    lookback_days=140,
                )
                if chart_path:
                    results.append((pick, chart_path))
                    print(f"Generated Telegram chart: {chart_path}")
                else:
                    print(f"Chart unavailable for {pick.ticker}: insufficient market data.")
            except Exception as exc:
                print(f"Chart generation failed for {pick.ticker}: {exc}")

        return results

    except Exception as exc:
        print(f"Chart generation setup failed: {exc}")
        return []


def send_telegram_alert(
    bot_token: str,
    chat_id: str,
    message: str,
    picks: Optional[Sequence[SwingPick]] = None,
) -> None:
    """Send the text alert followed by one detailed chart image per stock."""
    base_url = f"https://api.telegram.org/bot{bot_token}"

    message_response = requests.post(
        f"{base_url}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    message_response.raise_for_status()

    data = message_response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram send failed: {data}")

    if not picks:
        return

    for pick, chart_path in _generate_charts(picks):
        risk_reward = (
            pick.reward_pct / pick.risk_pct
            if pick.risk_pct and pick.risk_pct > 0
            else 0
        )
        caption = (
            f"📈 *{pick.ticker} — Strategy {STRATEGY_VERSION.upper()}*\n"
            f"Entry ₹{pick.entry:.2f} | Target ₹{pick.target:.2f} | "
            f"SL ₹{pick.stop_loss:.2f} | R:R 1:{risk_reward:.2f}"
        )

        try:
            with chart_path.open("rb") as photo:
                photo_response = requests.post(
                    f"{base_url}/sendPhoto",
                    data={
                        "chat_id": chat_id,
                        "caption": caption,
                        "parse_mode": "Markdown",
                    },
                    files={"photo": (chart_path.name, photo, "image/png")},
                    timeout=60,
                )

            photo_response.raise_for_status()
            photo_data = photo_response.json()
            if not photo_data.get("ok"):
                raise RuntimeError(f"Telegram chart upload failed: {photo_data}")

            print(f"Telegram chart sent: {pick.ticker}")

        except Exception as exc:
            print(f"Telegram chart upload failed for {pick.ticker}: {exc}")

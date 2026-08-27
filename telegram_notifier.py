from __future__ import annotations

from datetime import datetime
from typing import List

import requests

from strategy import SwingPick


STRATEGY_VERSION = "v2"


def format_telegram_alert(picks: List[SwingPick]) -> str:
    """
    Build the daily Telegram alert for the active strategy.

    Telegram is intentionally focused on actionable information:
    entry, target, stop loss, risk/reward, score and key indicators.
    """

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

        block = (
            f"*{index}️⃣ {pick.ticker}* — _{pick.name}_\n"
            f"🏭 Industry: `{pick.industry or 'N/A'}`\n"
            f"💰 Entry: `₹{pick.entry:.2f}`\n"
            f"🎯 Target: `₹{pick.target:.2f}`\n"
            f"🛑 Stop Loss: `₹{pick.stop_loss:.2f}`\n"
            f"⚖️ Risk/Reward: `1:{pick.reward_pct / pick.risk_pct:.2f}`\n"
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
            "⚠️ _For research/tracking only. Validate the setup before taking any trade._",
        ]
    )

    return "\n".join(message_lines)


def send_telegram_alert(
    bot_token: str,
    chat_id: str,
    message: str,
) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram send failed: {data}"
        )

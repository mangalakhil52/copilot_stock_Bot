from __future__ import annotations

from datetime import datetime
from typing import List

import requests
from strategy import SwingPick


def format_telegram_alert(picks: List[SwingPick]) -> str:
    if not picks:
        return (
            "📉 Indian Swing Stock Finder found no strong swing picks today. "
            "Run the scanner again after the market session."
        )

    run_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    message_lines = [f"📈 *Indian Swing Stock Alerts*\n_Run: {run_time}_"]
    for index, pick in enumerate(picks, start=1):
        line = (
            f"*{index}. {pick.ticker}* — _{pick.name}_\n"
            f"Industry: `{pick.industry or 'N/A'}`\n"
            f"Entry: `{pick.entry:.2f}`  Close: `{pick.close:.2f}`\n"
            f"Target: `{pick.target:.2f}`  SL: `{pick.stop_loss:.2f}`  Hold: `{pick.holding_period}`\n"
            f"Score: `{pick.score:.1f}`  Reward: `{pick.reward_pct:.2f}%`  Risk: `{pick.risk_pct:.2f}%`\n"
            f"EMA20/EMA50: `{pick.ema20:.2f}`/`{pick.ema50:.2f}`  RSI: `{pick.rsi:.1f}`\n"
            f"Notes: {pick.comment}"
        )
        message_lines.append(line)
    message = "\n\n".join(message_lines)
    return message


def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram send failed: {data}")

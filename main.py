from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from chartink import ChartinkClient
from strategy import (
    DEFAULT_COLUMN_CLAUSE,
    EXCLUDE_KEYWORDS,
    SwingPick,
    build_scan_clause,
    build_swing_picks,
)
from telegram_notifier import (
    format_telegram_alert,
    send_telegram_alert,
)
from tracker.signal_tracker import SignalTracker


def load_config(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def build_output_rows(picks: List[SwingPick]) -> List[Dict[str, Any]]:
    run_date = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    rows: List[Dict[str, Any]] = []
    for pick in picks:
        rows.append(
            {
                "run_date": run_date,
                "ticker": pick.ticker,
                "name": pick.name,
                "close": f"{pick.close:.2f}",
                "percent_change": f"{pick.percent_change:.2f}%",
                "volume": f"{pick.volume:.0f}",
                "volume_ratio": (
                    f"{pick.volume / pick.avg_volume:.2f}x"
                    if pick.avg_volume and pick.avg_volume > 0
                    else "N/A"
                ),
                "industry": pick.industry,
                "ema20": f"{pick.ema20:.2f}",
                "ema50": f"{pick.ema50:.2f}",
                "sma20": f"{pick.sma20:.2f}",
                "sma50": f"{pick.sma50:.2f}",
                "rsi": f"{pick.rsi:.2f}",
                "macd": f"{pick.macd:.2f}",
                "score": f"{pick.score:.1f}",
                "entry": f"{pick.entry:.2f}",
                "target": f"{pick.target:.2f}",
                "stop_loss": f"{pick.stop_loss:.2f}",
                "holding_period": pick.holding_period,
                "risk_pct": f"{pick.risk_pct:.2f}%",
                "reward_pct": f"{pick.reward_pct:.2f}%",
                "comment": pick.comment,
            }
        )
    return rows


def print_picks(picks: List[SwingPick]) -> None:
    if not picks:
        print("No strong swing picks were found. Try a broader scan or run again after the market close.")
        return

    print("Top swing stock picks:\n")
    for index, pick in enumerate(picks, start=1):
        print(f"{index}. {pick.ticker} ({pick.name})")
        print(
            f"   Close: {pick.close:.2f}  Entry: {pick.entry:.2f}  "
            f"Score: {pick.score:.1f}  Change: {pick.percent_change:.2f}%"
        )
        print(
            f"   EMA20: {pick.ema20:.2f}  EMA50: {pick.ema50:.2f}  "
            f"SMA20: {pick.sma20:.2f}  SMA50: {pick.sma50:.2f}"
        )
        avg_volume_text = f"{pick.avg_volume:.0f}" if pick.avg_volume and pick.avg_volume > 0 else "N/A"
        print(
            f"   Volume: {pick.volume:.0f}  Avg20: {avg_volume_text}  "
            f"RSI: {pick.rsi:.1f}  MACD: {pick.macd:.2f}"
        )
        print(f"   Industry: {pick.industry or 'N/A'}")
        print(
            f"   Target: {pick.target:.2f}  Stop Loss: {pick.stop_loss:.2f}  "
            f"Hold: {pick.holding_period}  Risk: {pick.risk_pct:.2f}%  "
            f"Reward: {pick.reward_pct:.2f}%"
        )
        print(f"   Notes: {pick.comment}\n")


def run_scan(config: Optional[Dict[str, Any]] = None) -> List[SwingPick]:
    top_n = 3
    exclude_keywords = EXCLUDE_KEYWORDS
    max_candidates = 300
    scan_clause = build_scan_clause(None)
    column_clause = DEFAULT_COLUMN_CLAUSE

    if config:
        scan_config = config.get("scan", {})
        top_n = int(scan_config.get("top_n", top_n))
        max_candidates = int(scan_config.get("max_candidates", max_candidates))
        exclude_keywords = scan_config.get("text_filters", {}).get("exclude_keywords", exclude_keywords)
        scan_clause = build_scan_clause(scan_config)
        column_clause = scan_config.get("column_clause", column_clause)

    print("Running Chartink scan...")
    client = ChartinkClient()
    rows = client.scan_candidates(
        scan_clause=scan_clause,
        column_clause=column_clause,
        max_candidates=max_candidates,
    )
    return build_swing_picks(rows, top_n=top_n, exclude_keywords=exclude_keywords)


def maybe_send_telegram_alert(
    config: Optional[Dict[str, Any]],
    picks: List[SwingPick],
) -> bool:
    if not config:
        return False

    telegram_config = config.get("telegram") or {}
    bot_token = telegram_config.get("bot_token")
    chat_id = telegram_config.get("chat_id")

    if not bot_token or not chat_id:
        print("Skipping Telegram alert because bot token or chat ID is missing.")
        return False

    if "YOUR_TELEGRAM" in str(bot_token) or "YOUR_TELEGRAM" in str(chat_id):
        print("Skipping Telegram alert because the bot token or chat ID is still a placeholder.")
        return False

    try:
        message = format_telegram_alert(picks)
        send_telegram_alert(
            bot_token=bot_token,
            chat_id=chat_id,
            message=message,
            picks=picks,
        )
        print("Telegram alert sent.")
        return True
    except Exception as exc:
        print(f"Telegram alert could not be sent: {exc}")
        return False


def update_google_sheets(picks: List[SwingPick]) -> bool:
    try:
        print("\nConnecting to Google Sheets...")
        tracker = SignalTracker()
        print("Google Sheets connection successful.")
        print("\nUpdating previous OPEN trades...")
        tracker.update_open_trades()
        print("\nRecording today's signals...")
        tracker.record_signals(picks)
        print("Google Sheets tracker updated successfully.")
        return True
    except Exception as exc:
        print(
            "\nWARNING: Google Sheets tracker could not be updated: "
            f"{exc}",
            file=sys.stderr,
        )
        print("The stock scanner and Telegram notification will continue.")
        return False


def command_analyze(args: argparse.Namespace) -> int:
    config = load_config(args.config) if args.config else None
    picks = run_scan(config)
    print_picks(picks)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(build_output_rows(picks), handle, indent=2)
        print(f"Wrote output to {args.output_json}")
    return 0


def command_notify_telegram(args: argparse.Namespace) -> int:
    config = load_config(args.config) if args.config else None
    picks = run_scan(config)
    print_picks(picks)

    if config:
        if args.bot_token and args.chat_id:
            config = dict(config)
            telegram_config = dict(config.get("telegram", {}))
            telegram_config["bot_token"] = args.bot_token
            telegram_config["chat_id"] = args.chat_id
            config["telegram"] = telegram_config
        maybe_send_telegram_alert(config, picks)
    elif args.bot_token and args.chat_id:
        maybe_send_telegram_alert(
            {"telegram": {"bot_token": args.bot_token, "chat_id": args.chat_id}},
            picks,
        )
    else:
        print("No Telegram configuration found. Skipping alert delivery.")
    return 0


def command_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print("Starting Copilot Stock Bot...")
    picks = run_scan(config)
    print_picks(picks)
    update_google_sheets(picks)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as handle:
            json.dump(build_output_rows(picks), handle, indent=2)
        print(f"Wrote output to {args.output_json}")

    if not args.skip_telegram and config.get("telegram"):
        maybe_send_telegram_alert(config, picks)
    elif args.skip_telegram:
        print("Telegram alert skipped because --skip-telegram was used.")
    else:
        print("No Telegram configuration found. Skipping alert.")

    print("\nCopilot Stock Bot run completed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep strong Indian swing stock candidates from Chartink.")
    subparsers = parser.add_subparsers(dest="command")

    analyze_parser = subparsers.add_parser("analyze", help="Run scan and print top picks.")
    analyze_parser.add_argument("--config", help="Optional configuration YAML file.")
    analyze_parser.add_argument("--output-json", help="Write recommendations to a JSON file.")

    notify_parser = subparsers.add_parser("notify-telegram", help="Run scan and send top picks to Telegram.")
    notify_parser.add_argument("--config", help="Optional configuration YAML file.")
    notify_parser.add_argument("--bot-token", help="Telegram bot token.")
    notify_parser.add_argument("--chat-id", help="Telegram chat ID.")

    run_parser = subparsers.add_parser("run", help="Run scan and publish alerts from config.")
    run_parser.add_argument("--config", required=True, help="Configuration YAML file.")
    run_parser.add_argument("--output-json", help="Optionally save output to a JSON file.")
    run_parser.add_argument("--skip-telegram", action="store_true", help="Do not send Telegram alerts.")

    args = parser.parse_args()

    try:
        if args.command == "analyze":
            return command_analyze(args)
        if args.command == "notify-telegram":
            return command_notify_telegram(args)
        if args.command == "run":
            return command_run(args)

        default_config = Path("config.yaml")
        if default_config.exists():
            config = load_config(str(default_config))
            picks = run_scan(config)
            print_picks(picks)
            update_google_sheets(picks)
            if config.get("telegram"):
                maybe_send_telegram_alert(config, picks)
            else:
                print("No Telegram configuration found in config.yaml. Run with --config or use notify-telegram.")
            return 0

        parser.print_help()
        return 1

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from strategy import SwingPick

from tracker.google_sheets import GoogleSheetsTracker
from tracker.market_data import GoogleFinanceMarketData


IST = ZoneInfo("Asia/Kolkata")


class SignalTracker:
    """
    Handles stock-signal tracking in Google Sheets.

    Responsibilities:
    - Record new signals.
    - Prevent duplicate signals.
    - Check existing OPEN positions.
    - Record every market observation in Price_Log.
    - Detect TARGET HIT.
    - Detect SL HIT.
    - Detect AMBIGUOUS target/SL candles.
    - Update current unrealized return.
    """

    def __init__(
        self,
        sheets: GoogleSheetsTracker | None = None,
        market_data: GoogleFinanceMarketData | None = None,
    ) -> None:

        self.sheets = (
            sheets
            or GoogleSheetsTracker()
        )

        self.market_data = (
            market_data
            or GoogleFinanceMarketData(
                sheets=self.sheets
            )
        )

    # =========================================================
    # TIME
    # =========================================================

    @staticmethod
    def now_ist() -> datetime:
        return datetime.now(IST)

    # =========================================================
    # SIGNAL ID
    # =========================================================

    @staticmethod
    def create_signal_id(
        signal_date: date,
        ticker: str,
        rank: int,
    ) -> str:

        return (
            f"{signal_date.strftime('%Y%m%d')}"
            f"-{ticker.upper()}"
            f"-{rank:02d}"
        )

    # =========================================================
    # BUILD SIGNAL
    # =========================================================

    def build_signal(
        self,
        pick: SwingPick,
        rank: int,
        signal_date: date | None = None,
    ) -> Dict[str, Any]:

        now = self.now_ist()

        if signal_date is None:
            signal_date = now.date()

        signal_id = self.create_signal_id(
            signal_date=signal_date,
            ticker=pick.ticker,
            rank=rank,
        )

        risk_reward = None

        if pick.risk_pct > 0:
            risk_reward = round(
                pick.reward_pct / pick.risk_pct,
                2,
            )

        volume_ratio = None

        if (
            pick.avg_volume
            and pick.avg_volume > 0
        ):
            volume_ratio = round(
                pick.volume / pick.avg_volume,
                2,
            )

        return {
            "Signal ID": signal_id,
            "Signal Date": signal_date.isoformat(),
            "Signal Time": now.strftime(
                "%H:%M:%S"
            ),
            "Rank": rank,
            "Symbol": pick.ticker,
            "Stock Name": pick.name,
            "Industry": pick.industry,
            "Close Price": pick.close,
            "Entry Price": pick.entry,
            "Target Price": pick.target,
            "Stop Loss": pick.stop_loss,
            "Score": round(
                pick.score,
                2,
            ),
            "RSI": round(
                pick.rsi,
                2,
            ),
            "MACD": round(
                pick.macd,
                2,
            ),
            "Volume Ratio": volume_ratio,
            "EMA20": pick.ema20,
            "SMA50": pick.sma50,
            "Holding Period": pick.holding_period,
            "Risk %": pick.risk_pct,
            "Reward %": pick.reward_pct,
            "Risk/Reward": risk_reward,
            "Status": "OPEN",
            "Exit Date": "",
            "Exit Price": "",
            "Return %": "",
            "Days Held": 0,
            "Exit Reason": "",
            "Current Price": pick.close,
            "Current Return %": 0,
            "Last Checked": now.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

    # =========================================================
    # RECORD NEW SIGNALS
    # =========================================================

    def record_signals(
        self,
        picks: List[SwingPick],
    ) -> int:

        if not picks:

            print(
                "No signals to record."
            )

            return 0

        now = self.now_ist()

        added = 0

        for rank, pick in enumerate(
            picks,
            start=1,
        ):

            signal = self.build_signal(
                pick=pick,
                rank=rank,
                signal_date=now.date(),
            )

            signal_id = signal[
                "Signal ID"
            ]

            if self.sheets.signal_exists(
                signal_id
            ):

                print(
                    f"Signal already exists: "
                    f"{signal_id}"
                )

                continue

            self.sheets.add_signal(
                signal
            )

            print(
                f"Recorded signal: "
                f"{signal_id}"
            )

            added += 1

        print(
            f"Signals added: {added}"
        )

        return added

    # =========================================================
    # UPDATE OPEN TRADES
    # =========================================================

    def update_open_trades(self) -> None:

        open_signals = (
            self.sheets.get_open_signals()
        )

        if not open_signals:

            print(
                "No OPEN signals to track."
            )

            return

        print(
            f"Open signals to check: "
            f"{len(open_signals)}"
        )

        for signal in open_signals:

            try:

                self._update_single_signal(
                    signal
                )

            except Exception as exc:

                signal_id = signal.get(
                    "Signal ID",
                    "UNKNOWN",
                )

                print(
                    f"Could not update "
                    f"{signal_id}: {exc}"
                )

    # =========================================================
    # UPDATE ONE SIGNAL
    # =========================================================

    def _update_single_signal(
        self,
        signal: Dict[str, Any],
    ) -> None:

        signal_id = str(
            signal.get(
                "Signal ID",
                "",
            )
        ).strip()

        symbol = str(
            signal.get(
                "Symbol",
                "",
            )
        ).strip().upper()

        if not signal_id or not symbol:
            return

        signal_date = date.fromisoformat(
            str(
                signal["Signal Date"]
            )[:10]
        )

        entry = float(
            signal["Entry Price"]
        )

        target = float(
            signal["Target Price"]
        )

        stop_loss = float(
            signal["Stop Loss"]
        )

        today = self.now_ist().date()

        market_rows = (
            self.market_data
            .get_data_after_signal(
                symbol=symbol,
                signal_date=signal_date,
                end_date=today,
            )
        )

        if not market_rows:

            self.sheets.update_signal(
                signal_id,
                {
                    "Last Checked":
                        self.now_ist().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                },
            )

            print(
                f"{signal_id}: "
                "No post-signal market data yet."
            )

            return

        # -----------------------------------------------------
        # Process every trading day chronologically.
        # -----------------------------------------------------

        for market_row in market_rows:

            observation_date = market_row[
                "date"
            ]

            high = market_row.get(
                "high"
            )

            low = market_row.get(
                "low"
            )

            close = market_row.get(
                "close"
            )

            volume = market_row.get(
                "volume"
            )

            open_price = market_row.get(
                "open"
            )

            if high is None or low is None:
                continue

            high = float(high)
            low = float(low)

            if open_price is not None:
                open_price = float(
                    open_price
                )

            if close is not None:
                close = float(
                    close
                )

            if volume is not None:
                volume = float(
                    volume
                )

            # -------------------------------------------------
            # Determine outcome.
            # -------------------------------------------------

            target_hit = (
                high >= target
            )

            sl_hit = (
                low <= stop_loss
            )

            status = "OPEN"
            exit_price = None
            exit_reason = ""

            # Both levels touched on same candle.
            if target_hit and sl_hit:

                status = "AMBIGUOUS"

                exit_reason = (
                    "Target and SL both touched "
                    "on same daily candle"
                )

            elif target_hit:

                status = "TARGET HIT"

                exit_price = target

                exit_reason = (
                    "Target reached"
                )

            elif sl_hit:

                status = "SL HIT"

                exit_price = stop_loss

                exit_reason = (
                    "Stop loss reached"
                )

            # -------------------------------------------------
            # Current price.
            # -------------------------------------------------

            current_price = (
                exit_price
                if exit_price is not None
                else close
            )

            current_return = None

            if current_price is not None:

                current_return = (
                    (
                        current_price
                        - entry
                    )
                    / entry
                    * 100
                )

            days_held = (
                observation_date
                - signal_date
            ).days

            # -------------------------------------------------
            # Add audit record.
            # -------------------------------------------------

            price_log = {
                "Date":
                    observation_date.isoformat(),

                "Time":
                    "15:30:00",

                "Symbol":
                    symbol,

                "Signal ID":
                    signal_id,

                "Signal Date":
                    signal_date.isoformat(),

                "Entry Price":
                    entry,

                "Target Price":
                    target,

                "Stop Loss":
                    stop_loss,

                "Open":
                    open_price
                    if open_price is not None
                    else "",

                "High":
                    high,

                "Low":
                    low,

                "Close":
                    close
                    if close is not None
                    else "",

                "Volume":
                    volume
                    if volume is not None
                    else "",

                "Current Price":
                    current_price
                    if current_price is not None
                    else "",

                "Target Hit":
                    "YES"
                    if target_hit
                    else "NO",

                "SL Hit":
                    "YES"
                    if sl_hit
                    else "NO",

                "Status":
                    status,

                "Data Source":
                    "GOOGLEFINANCE",
            }

            self._append_price_log_if_new(
                price_log
            )

            # -------------------------------------------------
            # If trade closed, update Signals and stop
            # processing later candles.
            # -------------------------------------------------

            if status in (
                "TARGET HIT",
                "SL HIT",
                "AMBIGUOUS",
            ):

                updates = {
                    "Status":
                        status,

                    "Exit Date":
                        observation_date.isoformat(),

                    "Days Held":
                        days_held,

                    "Exit Reason":
                        exit_reason,

                    "Last Checked":
                        self.now_ist().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                }

                if exit_price is not None:

                    return_pct = (
                        (
                            exit_price
                            - entry
                        )
                        / entry
                        * 100
                    )

                    updates[
                        "Exit Price"
                    ] = round(
                        exit_price,
                        2,
                    )

                    updates[
                        "Return %"
                    ] = round(
                        return_pct,
                        2,
                    )

                    updates[
                        "Current Price"
                    ] = round(
                        exit_price,
                        2,
                    )

                    updates[
                        "Current Return %"
                    ] = round(
                        return_pct,
                        2,
                    )

                else:

                    # Ambiguous trades intentionally have
                    # no realized return.
                    updates[
                        "Exit Price"
                    ] = ""

                    updates[
                        "Return %"
                    ] = ""

                self.sheets.update_signal(
                    signal_id,
                    updates,
                )

                print(
                    f"{signal_id}: "
                    f"{status} on "
                    f"{observation_date}"
                )

                return

        # -----------------------------------------------------
        # No exit occurred.
        #
        # Use the latest available trading day.
        # -----------------------------------------------------

        latest = market_rows[-1]

        latest_close = latest.get(
            "close"
        )

        if latest_close is not None:

            latest_close = float(
                latest_close
            )

            current_return = (
                (
                    latest_close
                    - entry
                )
                / entry
                * 100
            )

            days_held = (
                latest["date"]
                - signal_date
            ).days

            self.sheets.update_signal(
                signal_id,
                {
                    "Status":
                        "OPEN",

                    "Current Price":
                        round(
                            latest_close,
                            2,
                        ),

                    "Current Return %":
                        round(
                            current_return,
                            2,
                        ),

                    "Days Held":
                        days_held,

                    "Last Checked":
                        self.now_ist().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                },
            )

        print(
            f"{signal_id}: Still OPEN."
        )

    # =========================================================
    # PREVENT DUPLICATE PRICE LOG ENTRIES
    # =========================================================

    def _append_price_log_if_new(
        self,
        price_log: Dict[str, Any],
    ) -> None:

        signal_id = str(
            price_log.get(
                "Signal ID",
                "",
            )
        ).strip()

        observation_date = str(
            price_log.get(
                "Date",
                "",
            )
        ).strip()

        if not signal_id or not observation_date:
            return

        # Read existing Price_Log records.
        records = self.sheets.get_all_records(
            "Price_Log"
        )

        for record in records:

            existing_signal_id = str(
                record.get(
                    "Signal ID",
                    "",
                )
            ).strip()

            existing_date = str(
                record.get(
                    "Date",
                    "",
                )
            ).strip()

            if (
                existing_signal_id
                == signal_id
                and existing_date
                == observation_date
            ):

                print(
                    f"Price log already exists: "
                    f"{signal_id} / "
                    f"{observation_date}"
                )

                return

        self.sheets.add_price_log(
            price_log
        )

        print(
            f"Price log added: "
            f"{signal_id} / "
            f"{observation_date}"
        )

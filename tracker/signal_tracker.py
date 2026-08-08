from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List

from strategy import SwingPick

from tracker.google_sheets import GoogleSheetsTracker
from tracker.market_data import GoogleFinanceMarketData


IST = ZoneInfo("Asia/Kolkata")


class SignalTracker:
    """
    Connects the stock scanner to Google Sheets.

    Responsibilities:
    1. Record today's signals.
    2. Prevent duplicate signals.
    3. Check previous OPEN signals.
    4. Detect TARGET / SL hits.
    5. Record market observations.
    6. Update current unrealized return.
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

    # ---------------------------------------------------------
    # CURRENT IST DATE / TIME
    # ---------------------------------------------------------

    @staticmethod
    def now_ist() -> datetime:

        return datetime.now(IST)

    # ---------------------------------------------------------
    # SIGNAL ID
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # CONVERT SWING PICK → GOOGLE SHEETS ROW
    # ---------------------------------------------------------

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
            "Volume Ratio": (
                round(
                    pick.volume / pick.avg_volume,
                    2,
                )
                if pick.avg_volume
                and pick.avg_volume > 0
                else None
            ),
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

    # ---------------------------------------------------------
    # RECORD TODAY'S SIGNALS
    # ---------------------------------------------------------

    def record_signals(
        self,
        picks: List[SwingPick],
    ) -> int:
        """
        Add today's picks to Signals.

        Duplicate Signal IDs are ignored.
        """

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

    # ---------------------------------------------------------
    # UPDATE OPEN TRADES
    # ---------------------------------------------------------

    def update_open_trades(self) -> None:
        """
        Check all OPEN signals against historical market data.
        """

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

    # ---------------------------------------------------------
    # UPDATE ONE SIGNAL
    # ---------------------------------------------------------

    def _update_single_signal(
        self,
        signal: Dict[str, Any],
    ) -> None:

        signal_id = str(
            signal.get("Signal ID", "")
        ).strip()

        symbol = str(
            signal.get("Symbol", "")
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

        # -----------------------------------------------------
        # Get all trading days after the signal date.
        # -----------------------------------------------------

        market_rows = (
            self.market_data
            .get_data_after_signal(
                symbol=symbol,
                signal_date=signal_date,
                end_date=today,
            )
        )

        # -----------------------------------------------------
        # If no subsequent trading session exists yet.
        # -----------------------------------------------------

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
                f"No post-signal market data yet."
            )

            return

        # -----------------------------------------------------
        # Evaluate chronological market data.
        # -----------------------------------------------------

        for market_row in market_rows:

            high = market_row.get(
                "high"
            )

            low = market_row.get(
                "low"
            )

            close = market_row.get(
                "close"
            )

            if high is None or low is None:
                continue

            high = float(high)
            low = float(low)

            # -------------------------------------------------
            # Check both conditions first.
            #
            # If both target and SL occurred during the same
            # daily candle, sequence is unknown.
            # -------------------------------------------------

            target_hit = (
                high >= target
            )

            sl_hit = (
                low <= stop_loss
            )

            if target_hit and sl_hit:

                self._mark_ambiguous(
                    signal=signal,
                    market_row=market_row,
                )

                return

            # -------------------------------------------------
            # Target hit
            # -------------------------------------------------

            if target_hit:

                self._mark_closed(
                    signal=signal,
                    market_row=market_row,
                    status="TARGET HIT",
                    exit_price=target,
                    exit_reason="Target reached",
                )

                return

            # -------------------------------------------------
            # Stop loss hit
            # -------------------------------------------------

            if sl_hit:

                self._mark_closed(
                    signal=signal,
                    market_row=market_row,
                    status="SL HIT",
                    exit_price=stop_loss,
                    exit_reason="Stop loss reached",
                )

                return

            # -------------------------------------------------
            # No target/SL hit.
            #
            # Update current price using closing price.
            # -------------------------------------------------

            if close is not None:

                close = float(close)

                current_return = (
                    (
                        close - entry
                    )
                    / entry
                    * 100
                )

                days_held = (
                    market_row["date"]
                    - signal_date
                ).days

                self.sheets.update_signal(
                    signal_id,
                    {
                        "Current Price":
                            round(
                                close,
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
            f"{signal_id}: "
            f"Still OPEN."
        )

    # ---------------------------------------------------------
    # MARK TARGET / SL
    # ---------------------------------------------------------

    def _mark_closed(
        self,
        signal: Dict[str, Any],
        market_row: Dict[str, Any],
        status: str,
        exit_price: float,
        exit_reason: str,
    ) -> None:

        signal_id = signal[
            "Signal ID"
        ]

        entry = float(
            signal["Entry Price"]
        )

        exit_date = market_row[
            "date"
        ]

        return_pct = (
            (
                exit_price - entry
            )
            / entry
            * 100
        )

        days_held = (
            exit_date
            - date.fromisoformat(
                str(
                    signal["Signal Date"]
                )[:10]
            )
        ).days

        self.sheets.update_signal(
            signal_id,
            {
                "Status": status,
                "Exit Date":
                    exit_date.isoformat(),
                "Exit Price":
                    round(
                        exit_price,
                        2,
                    ),
                "Return %":
                    round(
                        return_pct,
                        2,
                    ),
                "Days Held":
                    days_held,
                "Exit Reason":
                    exit_reason,
                "Current Price":
                    round(
                        exit_price,
                        2,
                    ),
                "Current Return %":
                    round(
                        return_pct,
                        2,
                    ),
                "Last Checked":
                    self.now_ist().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
            },
        )

        print(
            f"{signal_id}: "
            f"{status} "
            f"at {exit_price:.2f}"
        )

    # ---------------------------------------------------------
    # AMBIGUOUS TRADE
    # ---------------------------------------------------------

    def _mark_ambiguous(
        self,
        signal: Dict[str, Any],
        market_row: Dict[str, Any],
    ) -> None:

        signal_id = signal[
            "Signal ID"
        ]

        exit_date = market_row[
            "date"
        ]

        days_held = (
            exit_date
            - date.fromisoformat(
                str(
                    signal["Signal Date"]
                )[:10]
            )
        ).days

        self.sheets.update_signal(
            signal_id,
            {
                "Status": "AMBIGUOUS",
                "Exit Date":
                    exit_date.isoformat(),
                "Exit Price": "",
                "Return %": "",
                "Days Held":
                    days_held,
                "Exit Reason":
                    "Target and SL both touched on same daily candle",
                "Last Checked":
                    self.now_ist().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
            },
        )

        print(
            f"{signal_id}: "
            f"AMBIGUOUS — target and SL "
            f"both touched."
        )

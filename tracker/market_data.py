from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import gspread

from tracker.google_sheets import GoogleSheetsTracker


class GoogleFinanceMarketData:
    """Market-data provider using GOOGLEFINANCE inside Google Sheets."""

    TEST_SHEET = "Price_Log"

    def __init__(
        self,
        sheets: Optional[GoogleSheetsTracker] = None,
    ) -> None:
        self.sheets = sheets or GoogleSheetsTracker()
        self.spreadsheet = self.sheets.spreadsheet
        self._market_data_sheet = None

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        symbol = str(symbol).strip().upper()
        if not symbol:
            raise ValueError("Stock symbol cannot be empty.")
        return symbol

    @staticmethod
    def build_historical_formula(
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> str:
        symbol = GoogleFinanceMarketData.normalize_symbol(symbol)
        start_text = start_date.strftime("%Y-%m-%d")
        end_text = end_date.strftime("%Y-%m-%d")
        return (
            f'=GOOGLEFINANCE('
            f'"NSE:{symbol}",'
            f'"all",'
            f'DATEVALUE("{start_text}"),'
            f'DATEVALUE("{end_text}"),'
            f'"DAILY")'
        )

    def get_historical_data(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        symbol = self.normalize_symbol(symbol)

        if end_date < start_date:
            raise ValueError("end_date cannot be before start_date.")

        worksheet = self._get_or_create_market_data_sheet()
        worksheet.clear()

        formula = self.build_historical_formula(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        worksheet.update(
            "A1",
            [[formula]],
            value_input_option="USER_ENTERED",
        )

        time.sleep(2)
        values = worksheet.get_all_values()
        return self._parse_googlefinance_values(values)

    def get_daily_data(
        self,
        symbol: str,
        trading_date: date,
    ) -> Optional[Dict[str, Any]]:
        start_date = trading_date - timedelta(days=3)
        end_date = trading_date + timedelta(days=1)

        rows = self.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        for row in rows:
            if row["date"] == trading_date:
                return row

        return None

    def get_data_after_signal(
        self,
        symbol: str,
        signal_date: date,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        if end_date is None:
            end_date = date.today()

        start_date = signal_date + timedelta(days=1)

        if start_date > end_date:
            return []

        return self.get_historical_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

    def _get_or_create_market_data_sheet(self):
        """Return the existing helper sheet; never try to recreate it."""
        if self._market_data_sheet is not None:
            return self._market_data_sheet

        sheet_name = "_MarketData"

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=sheet_name,
                rows=5000,
                cols=10,
            )

        self._market_data_sheet = worksheet
        return worksheet

    @staticmethod
    def _parse_googlefinance_values(
        values: List[List[Any]],
    ) -> List[Dict[str, Any]]:
        if not values:
            return []

        header_index = None

        for index, row in enumerate(values):
            normalized = [
                str(value).strip().lower()
                for value in row
            ]

            if (
                "date" in normalized
                and "high" in normalized
                and "low" in normalized
            ):
                header_index = index
                break

        if header_index is None:
            return []

        headers = [
            str(value).strip().lower()
            for value in values[header_index]
        ]

        def find_column(names: List[str]) -> Optional[int]:
            for name in names:
                if name in headers:
                    return headers.index(name)
            return None

        date_col = find_column(["date"])
        open_col = find_column(["open"])
        high_col = find_column(["high"])
        low_col = find_column(["low"])
        close_col = find_column(["close"])
        volume_col = find_column(["volume"])

        if date_col is None or high_col is None or low_col is None:
            return []

        result = []

        for row in values[header_index + 1:]:
            if len(row) <= max(date_col, high_col, low_col):
                continue

            try:
                parsed_date = GoogleFinanceMarketData._parse_date(
                    row[date_col]
                )

                if parsed_date is None:
                    continue

                result.append(
                    {
                        "date": parsed_date,
                        "open": GoogleFinanceMarketData._safe_number(row, open_col),
                        "high": GoogleFinanceMarketData._safe_number(row, high_col),
                        "low": GoogleFinanceMarketData._safe_number(row, low_col),
                        "close": GoogleFinanceMarketData._safe_number(row, close_col),
                        "volume": GoogleFinanceMarketData._safe_number(row, volume_col),
                    }
                )

            except Exception:
                continue

        return result

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        text = str(value).strip()
        if not text:
            return None

        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _safe_number(
        row: List[Any],
        column: Optional[int],
    ) -> Optional[float]:
        if column is None or column >= len(row):
            return None

        value = row[column]

        if value in ("", None, "#N/A", "#VALUE!"):
            return None

        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return None

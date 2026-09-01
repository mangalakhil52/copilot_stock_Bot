from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleSheetsTracker:
    """Google Sheets integration with low-read / low-write tracking."""

    SHEETS = {
        "Signals": [
            "Signal ID", "Signal Date", "Signal Time", "Rank", "Symbol",
            "Stock Name", "Industry", "Close Price", "Entry Price",
            "Target Price", "Stop Loss", "Score", "RSI", "MACD",
            "Volume Ratio", "EMA20", "SMA50", "Holding Period", "Risk %",
            "Reward %", "Risk/Reward", "Strategy Version", "Status",
            "Exit Date", "Exit Price", "Return %", "Days Held", "Exit Reason",
            "Current Price", "Current Return %", "Last Checked",
        ],
        "Price_Log": [
            "Date", "Time", "Symbol", "Signal ID", "Signal Date", "Entry Price",
            "Target Price", "Stop Loss", "Open", "High", "Low", "Close", "Volume",
            "Current Price", "Target Hit", "SL Hit", "Status", "Data Source",
        ],
        "Performance": ["Metric", "Value"],
        "Dashboard": ["Metric", "Value"],
    }

    def __init__(
        self,
        spreadsheet_id: Optional[str] = None,
        credentials_json: Optional[str] = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEET_ID")
        credentials_json = credentials_json or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

        if not self.spreadsheet_id:
            raise ValueError("GOOGLE_SHEET_ID environment variable is missing.")
        if not credentials_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable is missing.")

        try:
            credentials_info = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=SCOPES,
        )
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        self._worksheet_cache: Dict[str, Any] = {}
        self._records_cache: Dict[str, List[dict]] = {}

    def test_connection(self) -> str:
        return self.spreadsheet.title

    def get_worksheet(self, worksheet_name: str):
        if worksheet_name in self._worksheet_cache:
            return self._worksheet_cache[worksheet_name]

        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound as exc:
            raise ValueError(
                f"Worksheet '{worksheet_name}' does not exist."
            ) from exc

        self._worksheet_cache[worksheet_name] = worksheet
        return worksheet

    def initialize_sheets(self) -> None:
        for sheet_name, headers in self.SHEETS.items():
            try:
                worksheet = self.get_worksheet(sheet_name)
            except ValueError:
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=max(len(headers), 20),
                )
                self._worksheet_cache[sheet_name] = worksheet

            existing_values = worksheet.get_all_values()
            has_data = any(
                any(str(cell).strip() for cell in row)
                for row in existing_values
            )

            if not has_data:
                worksheet.append_row(
                    headers,
                    value_input_option="USER_ENTERED",
                )
                worksheet.freeze(rows=1)
                worksheet.format(
                    "1:1",
                    {"textFormat": {"bold": True}},
                )

        self.ensure_strategy_version_column()

    @staticmethod
    def _column_letter(column: int) -> str:
        result = ""
        while column:
            column, remainder = divmod(column - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def ensure_strategy_version_column(self) -> None:
        """Add Strategy Version and migrate blanks using one read + one batch write."""
        worksheet = self.get_worksheet("Signals")
        headers = worksheet.row_values(1)
        column_name = "Strategy Version"

        if column_name not in headers:
            column = len(headers) + 1
            if column > worksheet.col_count:
                worksheet.add_cols(column - worksheet.col_count)
            worksheet.update_cell(1, column, column_name)
            headers.append(column_name)
            print("Google Sheets migration: added Strategy Version column.")
        else:
            column = headers.index(column_name) + 1

        values = worksheet.get_all_values()
        if len(values) <= 1:
            return

        blanks = []
        for row_number, row in enumerate(values[1:], start=2):
            current = row[column - 1] if len(row) >= column else ""
            if not str(current).strip():
                blanks.append(row_number)

        if not blanks:
            return

        # Write contiguous ranges in batches instead of one API request per row.
        start = previous = blanks[0]
        ranges = []
        for row_number in blanks[1:]:
            if row_number == previous + 1:
                previous = row_number
            else:
                ranges.append((start, previous))
                start = previous = row_number
        ranges.append((start, previous))

        col_letter = self._column_letter(column)
        for range_start, range_end in ranges:
            worksheet.update(
                f"{col_letter}{range_start}:{col_letter}{range_end}",
                [["v1"] for _ in range(range_start, range_end + 1)],
                value_input_option="USER_ENTERED",
            )

        print(
            f"Google Sheets migration: marked {len(blanks)} historical signals as v1."
        )

        self._records_cache.pop("Signals", None)

    def append_row(self, worksheet_name: str, row: List[Any]) -> None:
        self.get_worksheet(worksheet_name).append_row(
            row,
            value_input_option="USER_ENTERED",
        )
        self._records_cache.pop(worksheet_name, None)

    def append_rows(self, worksheet_name: str, rows: List[List[Any]]) -> None:
        if rows:
            self.get_worksheet(worksheet_name).append_rows(
                rows,
                value_input_option="USER_ENTERED",
            )
            self._records_cache.pop(worksheet_name, None)

    def get_all_records(
        self,
        worksheet_name: str,
        refresh: bool = False,
    ) -> List[dict]:
        if not refresh and worksheet_name in self._records_cache:
            return self._records_cache[worksheet_name]

        records = self.get_worksheet(worksheet_name).get_all_records()
        self._records_cache[worksheet_name] = records
        return records

    def get_all_values(self, worksheet_name: str) -> List[List[Any]]:
        return self.get_worksheet(worksheet_name).get_all_values()

    def update_cell(
        self,
        worksheet_name: str,
        row: int,
        column: int,
        value: Any,
    ) -> None:
        self.get_worksheet(worksheet_name).update_cell(
            row,
            column,
            value,
        )
        self._records_cache.pop(worksheet_name, None)

    def update_range(
        self,
        worksheet_name: str,
        cell_range: str,
        values: List[List[Any]],
    ) -> None:
        self.get_worksheet(worksheet_name).update(
            cell_range,
            values,
            value_input_option="USER_ENTERED",
        )
        self._records_cache.pop(worksheet_name, None)

    def find_row(
        self,
        worksheet_name: str,
        column_name: str,
        search_value: Any,
    ) -> Optional[int]:
        records = self.get_all_records(worksheet_name)
        for index, record in enumerate(records, start=2):
            if str(record.get(column_name, "")).strip() == str(search_value).strip():
                return index
        return None

    def signal_exists(self, signal_id: str) -> bool:
        return self.find_row(
            "Signals",
            "Signal ID",
            signal_id,
        ) is not None

    def update_signal(
        self,
        signal_id: str,
        updates: dict,
    ) -> bool:
        worksheet = self.get_worksheet("Signals")
        records = self.get_all_records("Signals")
        if not records:
            return False

        headers = worksheet.row_values(1)
        signal_row = None

        for index, record in enumerate(records, start=2):
            if str(record.get("Signal ID", "")).strip() == str(signal_id).strip():
                signal_row = index
                break

        if signal_row is None:
            return False

        row = list(worksheet.row_values(signal_row))
        if len(row) < len(headers):
            row.extend([""] * (len(headers) - len(row)))

        for field, value in updates.items():
            if field not in headers:
                raise ValueError(
                    f"Column '{field}' does not exist in Signals."
                )
            row[headers.index(field)] = value

        worksheet.update(
            f"A{signal_row}:{self._column_letter(len(headers))}{signal_row}",
            [row[:len(headers)]],
            value_input_option="USER_ENTERED",
        )

        # Keep in-memory cache synchronized without another read.
        for record in records:
            if str(record.get("Signal ID", "")).strip() == str(signal_id).strip():
                record.update(updates)
                break

        return True

    def get_open_signals(self) -> List[dict]:
        records = self.get_all_records("Signals")
        return [
            record for record in records
            if str(record.get("Status", "")).strip().upper() == "OPEN"
        ]

    def add_signal(self, signal: dict) -> bool:
        signal_id = signal.get("Signal ID")
        if not signal_id:
            raise ValueError("Signal must contain 'Signal ID'.")

        # One cached Signals read for all duplicate checks during a run.
        if self.signal_exists(signal_id):
            return False

        headers = self.get_worksheet("Signals").row_values(1)
        row = [signal.get(header, "") for header in headers]
        self.append_row("Signals", row)

        # Update cache immediately so the next signal does not need another read.
        self._records_cache.setdefault("Signals", []).append(
            {header: signal.get(header, "") for header in headers}
        )
        return True

    def add_price_log(self, price_data: dict) -> None:
        headers = self.SHEETS["Price_Log"]
        self.append_row(
            "Price_Log",
            [price_data.get(header, "") for header in headers],
        )

        self._records_cache.setdefault("Price_Log", []).append(
            {header: price_data.get(header, "") for header in headers}
        )

    def initialize(self) -> None:
        self.initialize_sheets()
        print("Google Sheets tracker initialized successfully.")
        print(f"Spreadsheet: {self.spreadsheet.title}")
        for sheet_name in self.SHEETS:
            print(f" - {sheet_name}")

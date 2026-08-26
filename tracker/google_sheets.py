from __future__ import annotations

import json
import os
from typing import Any, List, Optional

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleSheetsTracker:
    """
    Google Sheets integration for Copilot Stock Bot.
    """

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

    def test_connection(self) -> str:
        return self.spreadsheet.title

    def get_worksheet(self, worksheet_name: str):
        try:
            return self.spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            raise ValueError(f"Worksheet '{worksheet_name}' does not exist.")

    def initialize_sheets(self) -> None:
        for sheet_name, headers in self.SHEETS.items():
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=max(len(headers), 20),
                )

            existing_values = worksheet.get_all_values()
            has_data = any(
                any(str(cell).strip() for cell in row)
                for row in existing_values
            )

            if not has_data:
                worksheet.append_row(headers, value_input_option="USER_ENTERED")
                worksheet.freeze(rows=1)
                worksheet.format("1:1", {"textFormat": {"bold": True}})

        self.ensure_strategy_version_column()

    def ensure_strategy_version_column(self) -> None:
        """
        Make the Signals schema self-healing.

        - If Strategy Version is missing, add it at the end.
        - If it already exists, keep it.
        - Fill blank historical rows with v1.
        - Never overwrite an existing version.
        """
        worksheet = self.get_worksheet("Signals")
        headers = worksheet.row_values(1)
        column_name = "Strategy Version"

        if column_name not in headers:
            new_column = len(headers) + 1
            if new_column > worksheet.col_count:
                worksheet.add_cols(new_column - worksheet.col_count)
            worksheet.update_cell(1, new_column, column_name)
            headers.append(column_name)
            print("Google Sheets migration: added Strategy Version column.")
        else:
            new_column = headers.index(column_name) + 1

        records = worksheet.get_all_records()
        migrated = 0

        for row_number, record in enumerate(records, start=2):
            current = str(record.get(column_name, "")).strip()
            if not current:
                worksheet.update_cell(row_number, new_column, "v1")
                migrated += 1

        if migrated:
            print(f"Google Sheets migration: marked {migrated} historical signals as v1.")

    def append_row(self, worksheet_name: str, row: List[Any]) -> None:
        self.get_worksheet(worksheet_name).append_row(row, value_input_option="USER_ENTERED")

    def append_rows(self, worksheet_name: str, rows: List[List[Any]]) -> None:
        if rows:
            self.get_worksheet(worksheet_name).append_rows(rows, value_input_option="USER_ENTERED")

    def get_all_records(self, worksheet_name: str) -> List[dict]:
        return self.get_worksheet(worksheet_name).get_all_records()

    def get_all_values(self, worksheet_name: str) -> List[List[Any]]:
        return self.get_worksheet(worksheet_name).get_all_values()

    def update_cell(self, worksheet_name: str, row: int, column: int, value: Any) -> None:
        self.get_worksheet(worksheet_name).update_cell(row, column, value)

    def update_range(self, worksheet_name: str, cell_range: str, values: List[List[Any]]) -> None:
        self.get_worksheet(worksheet_name).update(cell_range, values, value_input_option="USER_ENTERED")

    def find_row(self, worksheet_name: str, column_name: str, search_value: Any) -> Optional[int]:
        for index, record in enumerate(self.get_all_records(worksheet_name), start=2):
            if str(record.get(column_name, "")).strip() == str(search_value).strip():
                return index
        return None

    def signal_exists(self, signal_id: str) -> bool:
        return self.find_row("Signals", "Signal ID", signal_id) is not None

    def update_signal(self, signal_id: str, updates: dict) -> bool:
        worksheet = self.get_worksheet("Signals")
        records = worksheet.get_all_records()
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

        for field, value in updates.items():
            if field not in headers:
                raise ValueError(f"Column '{field}' does not exist in Signals.")
            worksheet.update_cell(signal_row, headers.index(field) + 1, value)
        return True

    def get_open_signals(self) -> List[dict]:
        return [
            record for record in self.get_all_records("Signals")
            if str(record.get("Status", "")).strip().upper() == "OPEN"
        ]

    def add_signal(self, signal: dict) -> bool:
        signal_id = signal.get("Signal ID")
        if not signal_id:
            raise ValueError("Signal must contain 'Signal ID'.")
        if self.signal_exists(signal_id):
            return False

        # Ensure migrations are complete before appending so the row matches the header.
        self.ensure_strategy_version_column()
        headers = self.get_worksheet("Signals").row_values(1)
        row = [signal.get(header, "") for header in headers]
        self.append_row("Signals", row)
        return True

    def add_price_log(self, price_data: dict) -> None:
        headers = self.SHEETS["Price_Log"]
        self.append_row("Price_Log", [price_data.get(header, "") for header in headers])

    def initialize(self) -> None:
        self.initialize_sheets()
        print("Google Sheets tracker initialized successfully.")
        print(f"Spreadsheet: {self.spreadsheet.title}")
        for sheet_name in self.SHEETS:
            print(f" - {sheet_name}")

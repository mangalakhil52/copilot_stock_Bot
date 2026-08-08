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

    Handles Google Sheets connectivity and basic worksheet operations.
    Trading logic is intentionally kept outside this module.
    """

    SHEETS = {
        "Signals": [
            "Signal ID",
            "Signal Date",
            "Signal Time",
            "Rank",
            "Symbol",
            "Stock Name",
            "Industry",
            "Close Price",
            "Entry Price",
            "Target Price",
            "Stop Loss",
            "Score",
            "RSI",
            "MACD",
            "Volume Ratio",
            "EMA20",
            "SMA50",
            "Holding Period",
            "Risk %",
            "Reward %",
            "Risk/Reward",
            "Status",
            "Exit Date",
            "Exit Price",
            "Return %",
            "Days Held",
            "Exit Reason",
            "Current Price",
            "Current Return %",
            "Last Checked",
        ],

        "Price_Log": [
            "Date",
            "Time",
            "Symbol",
            "Signal ID",
            "Signal Date",
            "Entry Price",
            "Target Price",
            "Stop Loss",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Current Price",
            "Target Hit",
            "SL Hit",
            "Status",
            "Data Source",
        ],

        "Performance": [
            "Metric",
            "Value",
        ],

        "Dashboard": [
            "Metric",
            "Value",
        ],
    }

    def __init__(
        self,
        spreadsheet_id: Optional[str] = None,
        credentials_json: Optional[str] = None,
    ) -> None:

        self.spreadsheet_id = (
            spreadsheet_id
            or os.getenv("GOOGLE_SHEET_ID")
        )

        credentials_json = (
            credentials_json
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        )

        if not self.spreadsheet_id:
            raise ValueError(
                "GOOGLE_SHEET_ID environment variable is missing."
            )

        if not credentials_json:
            raise ValueError(
                "GOOGLE_SERVICE_ACCOUNT_JSON environment variable is missing."
            )

        try:
            credentials_info = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from exc

        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=SCOPES,
        )

        self.client = gspread.authorize(credentials)

        self.spreadsheet = self.client.open_by_key(
            self.spreadsheet_id
        )

    def get_worksheet(self, worksheet_name: str):

        return self.spreadsheet.worksheet(
            worksheet_name
        )

    def append_row(
        self,
        worksheet_name: str,
        row: List[Any],
    ) -> None:

        worksheet = self.get_worksheet(
            worksheet_name
        )

        worksheet.append_row(
            row,
            value_input_option="USER_ENTERED",
        )

    def get_all_records(
        self,
        worksheet_name: str,
    ) -> List[dict]:

        worksheet = self.get_worksheet(
            worksheet_name
        )

        return worksheet.get_all_records()

    def update_cell(
        self,
        worksheet_name: str,
        row: int,
        column: int,
        value: Any,
    ) -> None:

        worksheet = self.get_worksheet(
            worksheet_name
        )

        worksheet.update_cell(
            row,
            column,
            value,
        )

    def initialize_sheets(self) -> None:
        """
        Create/initialize required worksheets and headers.
        Existing data is preserved.
        """

        for sheet_name, headers in self.SHEETS.items():

            try:
                worksheet = self.get_worksheet(
                    sheet_name
                )

            except gspread.WorksheetNotFound:

                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=max(len(headers), 20),
                )

            # Only write headers if sheet is empty.
            existing_values = worksheet.get_all_values()

            if not existing_values:

                worksheet.append_row(
                    headers,
                    value_input_option="USER_ENTERED",
                )

                # Freeze header row.
                worksheet.freeze(rows=1)

                # Make header bold.
                worksheet.format(
                    "1:1",
                    {
                        "textFormat": {
                            "bold": True
                        }
                    },
                )

    def test_connection(self) -> str:

        return self.spreadsheet.title

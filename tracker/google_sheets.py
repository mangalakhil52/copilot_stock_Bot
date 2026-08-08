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
    Minimal Google Sheets client for the Copilot Stock Bot.

    This module only handles Google Sheets connectivity.
    It does NOT contain trading logic.
    """

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
        return self.spreadsheet.worksheet(worksheet_name)

    def append_row(
        self,
        worksheet_name: str,
        row: List[Any],
    ) -> None:

        worksheet = self.get_worksheet(worksheet_name)

        worksheet.append_row(
            row,
            value_input_option="USER_ENTERED",
        )

    def get_all_records(
        self,
        worksheet_name: str,
    ) -> List[dict]:

        worksheet = self.get_worksheet(worksheet_name)

        return worksheet.get_all_records()

    def update_cell(
        self,
        worksheet_name: str,
        row: int,
        column: int,
        value: Any,
    ) -> None:

        worksheet = self.get_worksheet(worksheet_name)

        worksheet.update_cell(
            row,
            column,
            value,
        )

    def test_connection(self) -> str:

        return self.spreadsheet.title

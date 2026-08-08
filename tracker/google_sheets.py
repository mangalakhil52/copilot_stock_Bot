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

    Responsibilities:
    - Connect to Google Sheets using a service account
    - Create required worksheets if missing
    - Initialize worksheet headers
    - Append rows
    - Read worksheet records
    - Update individual cells
    - Check spreadsheet connectivity

    Trading logic is intentionally NOT handled here.
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
        """
        Initialize Google Sheets connection.

        Credentials are expected from environment variables:

        GOOGLE_SHEET_ID
        GOOGLE_SERVICE_ACCOUNT_JSON
        """

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

    # ---------------------------------------------------------
    # CONNECTION
    # ---------------------------------------------------------

    def test_connection(self) -> str:
        """
        Return the connected spreadsheet name.
        """

        return self.spreadsheet.title

    # ---------------------------------------------------------
    # WORKSHEET ACCESS
    # ---------------------------------------------------------

    def get_worksheet(self, worksheet_name: str):
        """
        Return a worksheet by name.
        """

        try:
            return self.spreadsheet.worksheet(
                worksheet_name
            )

        except gspread.WorksheetNotFound:
            raise ValueError(
                f"Worksheet '{worksheet_name}' does not exist."
            )

    # ---------------------------------------------------------
    # WORKSHEET INITIALIZATION
    # ---------------------------------------------------------

    def initialize_sheets(self) -> None:
        """
        Create required worksheets if they don't exist.

        If a worksheet already exists but is completely blank,
        the required headers are added.

        Existing data is never overwritten.
        """

        for sheet_name, headers in self.SHEETS.items():

            # -------------------------------------------------
            # Get existing worksheet or create it
            # -------------------------------------------------

            try:

                worksheet = self.spreadsheet.worksheet(
                    sheet_name
                )

            except gspread.WorksheetNotFound:

                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name,
                    rows=1000,
                    cols=max(len(headers), 20),
                )

            # -------------------------------------------------
            # Read existing data
            # -------------------------------------------------

            existing_values = worksheet.get_all_values()

            # -------------------------------------------------
            # Determine whether sheet actually contains data
            #
            # Google Sheets can return blank rows such as:
            #
            # [[""]]
            #
            # Therefore simply checking:
            #
            # if not existing_values
            #
            # is not sufficient.
            # -------------------------------------------------

            has_data = any(
                any(
                    str(cell).strip()
                    for cell in row
                )
                for row in existing_values
            )

            # -------------------------------------------------
            # Add headers only to genuinely empty sheets
            # -------------------------------------------------

            if not has_data:

                worksheet.append_row(
                    headers,
                    value_input_option="USER_ENTERED",
                )

                # Freeze first row.
                worksheet.freeze(rows=1)

                # Bold header row.
                worksheet.format(
                    "1:1",
                    {
                        "textFormat": {
                            "bold": True
                        }
                    },
                )

    # ---------------------------------------------------------
    # APPEND DATA
    # ---------------------------------------------------------

    def append_row(
        self,
        worksheet_name: str,
        row: List[Any],
    ) -> None:
        """
        Append one row to a worksheet.
        """

        worksheet = self.get_worksheet(
            worksheet_name
        )

        worksheet.append_row(
            row,
            value_input_option="USER_ENTERED",
        )

    # ---------------------------------------------------------
    # APPEND MULTIPLE ROWS
    # ---------------------------------------------------------

    def append_rows(
        self,
        worksheet_name: str,
        rows: List[List[Any]],
    ) -> None:
        """
        Append multiple rows to a worksheet.
        """

        if not rows:
            return

        worksheet = self.get_worksheet(
            worksheet_name
        )

        worksheet.append_rows(
            rows,
            value_input_option="USER_ENTERED",
        )

    # ---------------------------------------------------------
    # READ ALL RECORDS
    # ---------------------------------------------------------

    def get_all_records(
        self,
        worksheet_name: str,
    ) -> List[dict]:
        """
        Return worksheet data as a list of dictionaries.

        First row is treated as the header.
        """

        worksheet = self.get_worksheet(
            worksheet_name
        )

        return worksheet.get_all_records()

    # ---------------------------------------------------------
    # READ ALL VALUES
    # ---------------------------------------------------------

    def get_all_values(
        self,
        worksheet_name: str,
    ) -> List[List[Any]]:
        """
        Return raw worksheet values.
        """

        worksheet = self.get_worksheet(
            worksheet_name
        )

        return worksheet.get_all_values()

    # ---------------------------------------------------------
    # UPDATE CELL
    # ---------------------------------------------------------

    def update_cell(
        self,
        worksheet_name: str,
        row: int,
        column: int,
        value: Any,
    ) -> None:
        """
        Update one cell.
        """

        worksheet = self.get_worksheet(
            worksheet_name
        )

        worksheet.update_cell(
            row,
            column,
            value,
        )

    # ---------------------------------------------------------
    # UPDATE RANGE
    # ---------------------------------------------------------

    def update_range(
        self,
        worksheet_name: str,
        cell_range: str,
        values: List[List[Any]],
    ) -> None:
        """
        Update a range of cells.
        """

        worksheet = self.get_worksheet(
            worksheet_name
        )

        worksheet.update(
            cell_range,
            values,
            value_input_option="USER_ENTERED",
        )

    # ---------------------------------------------------------
    # FIND ROW BY VALUE
    # ---------------------------------------------------------

    def find_row(
        self,
        worksheet_name: str,
        column_name: str,
        search_value: Any,
    ) -> Optional[int]:
        """
        Find the first row where column_name equals search_value.

        Returns:
            Row number
            None if not found
        """

        worksheet = self.get_worksheet(
            worksheet_name
        )

        records = worksheet.get_all_records()

        for index, record in enumerate(
            records,
            start=2,
        ):
            value = record.get(column_name)

            if str(value).strip() == str(
                search_value
            ).strip():
                return index

        return None

    # ---------------------------------------------------------
    # CHECK IF SIGNAL EXISTS
    # ---------------------------------------------------------

    def signal_exists(
        self,
        signal_id: str,
    ) -> bool:
        """
        Check whether a Signal ID already exists.

        This prevents duplicate signals if GitHub Actions
        accidentally executes twice.
        """

        row = self.find_row(
            worksheet_name="Signals",
            column_name="Signal ID",
            search_value=signal_id,
        )

        return row is not None

    # ---------------------------------------------------------
    # UPDATE SIGNAL
    # ---------------------------------------------------------

    def update_signal(
        self,
        signal_id: str,
        updates: dict,
    ) -> bool:
        """
        Update fields for an existing signal.

        Example:

        {
            "Status": "TARGET HIT",
            "Exit Price": 1500,
            "Return %": 5.63
        }

        Returns:
            True if signal was found and updated.
            False otherwise.
        """

        worksheet = self.get_worksheet(
            "Signals"
        )

        records = worksheet.get_all_records()

        if not records:
            return False

        headers = worksheet.row_values(1)

        signal_row = None

        for index, record in enumerate(
            records,
            start=2,
        ):

            if str(
                record.get("Signal ID", "")
            ).strip() == str(
                signal_id
            ).strip():

                signal_row = index
                break

        if signal_row is None:
            return False

        for field, value in updates.items():

            if field not in headers:
                raise ValueError(
                    f"Column '{field}' does not exist in Signals."
                )

            column_number = (
                headers.index(field) + 1
            )

            worksheet.update_cell(
                signal_row,
                column_number,
                value,
            )

        return True

    # ---------------------------------------------------------
    # GET OPEN SIGNALS
    # ---------------------------------------------------------

    def get_open_signals(self) -> List[dict]:
        """
        Return all signals currently marked OPEN.
        """

        records = self.get_all_records(
            "Signals"
        )

        return [
            record
            for record in records
            if str(
                record.get("Status", "")
            ).strip().upper() == "OPEN"
        ]

    # ---------------------------------------------------------
    # ADD SIGNAL
    # ---------------------------------------------------------

    def add_signal(
        self,
        signal: dict,
    ) -> bool:
        """
        Add a signal to the Signals sheet.

        Returns:
            True  -> added
            False -> already exists
        """

        signal_id = signal.get(
            "Signal ID"
        )

        if not signal_id:
            raise ValueError(
                "Signal must contain 'Signal ID'."
            )

        # Prevent duplicates.
        if self.signal_exists(
            signal_id
        ):
            return False

        headers = self.SHEETS["Signals"]

        row = [
            signal.get(header, "")
            for header in headers
        ]

        self.append_row(
            "Signals",
            row,
        )

        return True

    # ---------------------------------------------------------
    # ADD PRICE LOG
    # ---------------------------------------------------------

    def add_price_log(
        self,
        price_data: dict,
    ) -> None:
        """
        Add one market-price observation.
        """

        headers = self.SHEETS[
            "Price_Log"
        ]

        row = [
            price_data.get(header, "")
            for header in headers
        ]

        self.append_row(
            "Price_Log",
            row,
        )

    # ---------------------------------------------------------
    # INITIALIZE
    # ---------------------------------------------------------

    def initialize(self) -> None:
        """
        Public helper for initializing the complete tracker.
        """

        self.initialize_sheets()

        print(
            "Google Sheets tracker initialized successfully."
        )

        print(
            f"Spreadsheet: {self.spreadsheet.title}"
        )

        for sheet_name in self.SHEETS:
            print(
                f" - {sheet_name}"
            )

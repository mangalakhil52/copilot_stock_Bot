from google_sheets import GoogleSheetsTracker


def main():
    tracker = GoogleSheetsTracker()

    title = tracker.test_connection()

    print(f"Google Sheets connection successful.")
    print(f"Spreadsheet: {title}")


if __name__ == "__main__":
    main()

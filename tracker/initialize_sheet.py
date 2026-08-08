from tracker.google_sheets import GoogleSheetsTracker


def main():

    print("Connecting to Google Sheets...")

    tracker = GoogleSheetsTracker()

    print(
        f"Connected to: {tracker.test_connection()}"
    )

    print("Initializing worksheets...")

    tracker.initialize_sheets()

    print("Google Sheets initialized successfully.")

    print("Created/verified:")

    for sheet_name in tracker.SHEETS:
        print(f" - {sheet_name}")


if __name__ == "__main__":
    main()

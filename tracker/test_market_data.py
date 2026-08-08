from datetime import date, timedelta

from tracker.market_data import GoogleFinanceMarketData


def main():

    print(
        "Testing Google Finance market data..."
    )

    market_data = (
        GoogleFinanceMarketData()
    )

    end_date = date.today()

    start_date = (
        end_date - timedelta(days=10)
    )

    rows = market_data.get_historical_data(
        symbol="RELIANCE",
        start_date=start_date,
        end_date=end_date,
    )

    if not rows:

        raise RuntimeError(
            "No market data returned."
        )

    print(
        f"Received {len(rows)} trading-day records."
    )

    for row in rows:

        print(
            f"{row['date']} | "
            f"Open={row['open']} | "
            f"High={row['high']} | "
            f"Low={row['low']} | "
            f"Close={row['close']} | "
            f"Volume={row['volume']}"
        )


if __name__ == "__main__":
    main()

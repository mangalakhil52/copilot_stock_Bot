# Indian Swing Stock Finder

A command-line program that finds strong Indian stock swing candidates using real-time Chartink scanner data and provides smart entry, target, and stop-loss guidance.

Features:
- Scans the full Indian cash stock universe with Chartink's real-time scanner.
- Applies momentum, trend, and volume strength filters.
- Picks the top 2-3 swing trade candidates with actionable entry, target, stop-loss, and expected holding period guidance.
- The holding period now considers industry, trend strength, and volatility.
- Supports Telegram alerts for push notifications of the top picks.

## Setup

1. Install Python 3.10+.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Create a Telegram bot and note your bot token and chat ID.
   - Use BotFather on Telegram to create the bot and receive a token.
   - Add the bot to your chat or channel and obtain the chat ID.
   - Put `telegram.bot_token` and `telegram.chat_id` in `config.yaml`.

## Usage

Run the scanner and send Telegram alerts using the local `config.yaml`:
```powershell
python main.py
```

Run a scan and print top picks without sending alerts:
```powershell
python main.py analyze
```

Run a scan and send Telegram alerts explicitly:
```powershell
python main.py notify-telegram --config config.yaml
```

Run with a configuration file and publish alerts automatically:
```powershell
python main.py run --config config.yaml
```

## Configuration

Use `config.example.yaml` as the template for `config.yaml`.

## Scheduling

### GitHub Actions (recommended for 8 PM IST)

This repository includes a GitHub Actions workflow that runs every weekday at 8:00 PM IST.

1. In your GitHub repository, add these repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. Push this repository to GitHub.
3. In the Actions tab, enable the workflow and run it once manually to confirm it works.

The workflow file is [.github/workflows/daily-telegram-alerts.yml](.github/workflows/daily-telegram-alerts.yml).

### Windows Task Scheduler (local fallback)

A helper script is included to run the scan every weekday at 9:00 PM.

1. Create `config.yaml` from `config.example.yaml` and fill in your Telegram settings.
   - The sample `config.yaml` included here uses `telegram.bot_token` and `telegram.chat_id`.
2. Run the scheduler helper:
   ```powershell
   .\create_task.ps1
   ```
3. The scheduled task executes `run_daily.ps1`, which runs `main.py run --config config.yaml`.

If you prefer manual scheduling, use Task Scheduler with the same Python command.
## Notes

- The program uses Chartink's real-time scanner, not a stale API.
- For robust results, keep the configuration tuned and run daily on market weekdays.

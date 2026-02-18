# Medical RAG Telegram Bot

## Run the Telegram bot locally (polling mode)

1. Install dependencies (including the new Telegram adapter dependency):
   - `pip install python-telegram-bot`
2. Ensure your retrieval artifacts already exist:
   - `artifacts/guidelines.index`
   - `artifacts/guidelines_metadata.json`
3. Copy environment template and set your bot token:
   - `cp .env.example .env`
   - Set `TELEGRAM_BOT_TOKEN` in `.env`
4. Export environment variables:
   - `set -a && source .env && set +a`
5. Run the bot:
   - `python -m app.interfaces.telegram_bot`

The bot runs using Telegram long polling (no webhook setup required).

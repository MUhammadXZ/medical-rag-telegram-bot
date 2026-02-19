# CMPA Medical RAG Telegram Bot

A Telegram bot that provides retrieval-augmented guidance for **Cow's Milk Protein Allergy (CMPA)** using a FAISS knowledge index.

> **Medical notice:** This project is for educational support only and is not a diagnostic system.

## Quick Start

```bash
cd medical-rag-telegram-bot
python -m pip install -r requirements.txt
cp .env.example .env
python -m app.interfaces.telegram_bot
```

## Configuration

- `TELEGRAM_BOT_TOKEN` is prefilled in `.env.example`.
- FAISS artifacts expected by default:
  - `eval/faiss/guidelines.index`
  - `eval/faiss/guidelines_metadata.json`

## Optional Launch Helpers

- Linux/macOS: `./run_bot.sh`
- Windows: `run_bot.bat`
- Guided setup: `python setup_and_run.py`

## Troubleshooting

- **Bot does not start:** reinstall dependencies with `python -m pip install -r requirements.txt`.
- **Index load errors:** verify FAISS files above exist or update paths in `.env`.
- **Telegram errors:** validate token and bot status in BotFather.

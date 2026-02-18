from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.services.cmpa_rag_service import CmpaRagService


logger = logging.getLogger(__name__)


BOT_TIMEOUT_MESSAGE = (
    "I'm taking too long to process your request. "
    "Please try again with a shorter or clearer CMPA-related question."
)

GENERIC_ERROR_MESSAGE = (
    "Sorry, something went wrong while preparing your answer. "
    "Please try again shortly."
)


@dataclass(frozen=True)
class TelegramBotConfig:
    token: str
    index_path: str = "artifacts/guidelines.index"
    metadata_path: str = "artifacts/guidelines_metadata.json"
    request_timeout_seconds: float = 20.0


class TelegramCmpaBot:
    """Telegram polling bot adapter for the CMPA RAG service."""

    def __init__(self, *, service: CmpaRagService, config: TelegramBotConfig) -> None:
        self._service = service
        self._config = config

    @classmethod
    def from_config(cls, config: TelegramBotConfig) -> "TelegramCmpaBot":
        service = CmpaRagService.from_index_files(
            index_path=config.index_path,
            metadata_path=config.metadata_path,
        )
        return cls(service=service, config=config)

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG002
        await update.message.reply_text(
            "Hello. I provide CMPA-focused guidance only. "
            "Share your question, and I will answer using the CMPA knowledge base."
        )

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: ARG002
        message = update.effective_message
        if message is None or not message.text:
            return

        try:
            answer = await asyncio.wait_for(
                self._service.answer(message.text),
                timeout=self._config.request_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await message.reply_text(BOT_TIMEOUT_MESSAGE)
            return
        except Exception:  # pragma: no cover - final safety net at adapter layer.
            logger.exception("Unexpected Telegram handler error.")
            await message.reply_text(GENERIC_ERROR_MESSAGE)
            return

        await message.reply_text(answer.text, parse_mode=ParseMode.MARKDOWN)

    def build_application(self) -> Application:
        app = Application.builder().token(self._config.token).build()
        app.add_handler(CommandHandler("start", self.on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_message))
        return app

    def run_polling(self) -> None:
        application = self.build_application()
        application.run_polling(close_loop=False)


def load_bot_config_from_env() -> TelegramBotConfig:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required.")

    return TelegramBotConfig(
        token=token,
        index_path=os.getenv("CMPA_INDEX_PATH", "artifacts/guidelines.index"),
        metadata_path=os.getenv("CMPA_METADATA_PATH", "artifacts/guidelines_metadata.json"),
        request_timeout_seconds=float(os.getenv("CMPA_BOT_TIMEOUT_SECONDS", "20")),
    )


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_bot_config_from_env()
    bot = TelegramCmpaBot.from_config(config)
    bot.run_polling()


if __name__ == "__main__":
    run()

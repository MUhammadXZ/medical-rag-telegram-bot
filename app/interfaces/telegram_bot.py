from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
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
    index_path: str = "eval/faiss/guidelines.index"
    metadata_path: str = "eval/faiss/guidelines_metadata.json"
    request_timeout_seconds: float = 10.0
    emergency_timeout_override_seconds: float | None = None
    log_level: str = "INFO"
    webhook_url: str | None = None
    webhook_listen: str = "0.0.0.0"
    webhook_port: int = 8080

    def effective_timeout_seconds(self) -> float:
        if self.emergency_timeout_override_seconds is None:
            return self.request_timeout_seconds
        return min(self.request_timeout_seconds, self.emergency_timeout_override_seconds)


class TelegramCmpaBot:
    """Telegram polling/webhook adapter for the CMPA RAG service."""

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
                timeout=self._config.effective_timeout_seconds(),
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

    def run(self) -> None:
        application = self.build_application()
        if self._config.webhook_url:
            logger.info("Starting bot in webhook mode at %s", self._config.webhook_url)
            application.run_webhook(
                listen=self._config.webhook_listen,
                port=self._config.webhook_port,
                url_path=self._config.token,
                webhook_url=f"{self._config.webhook_url.rstrip('/')}/{self._config.token}",
                close_loop=False,
            )
            return

        logger.info("Starting bot in polling mode")
        application.run_polling(close_loop=False)


def _parse_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r. Falling back to %s.", name, raw_value, default)
        return default

    if value < minimum or value > maximum:
        logger.warning(
            "%s=%s out of range [%s, %s]. Falling back to %s.",
            name,
            value,
            minimum,
            maximum,
            default,
        )
        return default
    return value


def _parse_log_level() -> str:
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
    if log_level not in valid_levels:
        logger.warning("Invalid LOG_LEVEL=%r. Falling back to INFO.", log_level)
        return "INFO"
    return log_level


def load_bot_config_from_env() -> TelegramBotConfig:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required.")

    timeout = _parse_float("CMPA_BOT_TIMEOUT_SECONDS", default=10.0, minimum=5.0, maximum=60.0)
    emergency_timeout_raw = os.getenv("CMPA_EMERGENCY_TIMEOUT_SECONDS", "").strip()
    emergency_timeout = None
    if emergency_timeout_raw:
        emergency_timeout = _parse_float(
            "CMPA_EMERGENCY_TIMEOUT_SECONDS",
            default=timeout,
            minimum=3.0,
            maximum=30.0,
        )

    webhook_port = int(os.getenv("WEBHOOK_PORT", "8080"))

    return TelegramBotConfig(
        token=token,
        index_path=os.getenv("CMPA_INDEX_PATH", "eval/faiss/guidelines.index"),
        metadata_path=os.getenv("CMPA_METADATA_PATH", "eval/faiss/guidelines_metadata.json"),
        request_timeout_seconds=timeout,
        emergency_timeout_override_seconds=emergency_timeout,
        log_level=_parse_log_level(),
        webhook_url=os.getenv("WEBHOOK_URL", "").strip() or None,
        webhook_listen=os.getenv("WEBHOOK_LISTEN", "0.0.0.0").strip(),
        webhook_port=webhook_port,
    )


def run() -> None:
    config = load_bot_config_from_env()
    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))
    bot = TelegramCmpaBot.from_config(config)
    bot.run()


if __name__ == "__main__":
    run()

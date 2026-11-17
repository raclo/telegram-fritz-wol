"""Private-chat command and callback handlers with a common authorization gate."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings
from .i18n import translate
from .router import FritzRouter
from .service import WolService

LOGGER = logging.getLogger("telegram_fritz_wol")


def is_authorized(update: Update, allowed_ids: frozenset[int]) -> bool:
    user, chat = update.effective_user, update.effective_chat
    return bool(user and user.id in allowed_ids and chat and chat.type == "private")


class BotHandlers:
    def __init__(self, settings: Settings, service: WolService):
        self._allowed_ids = settings.allowed_user_ids
        self._language = settings.language
        self._service = service

    async def _authorize(self, update: Update) -> bool:
        if is_authorized(update, self._allowed_ids):
            return True
        LOGGER.warning("Accesso Telegram rifiutato.")
        if update.callback_query:
            await update.callback_query.answer(translate(self._language, "access_denied"), show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(translate(self._language, "access_denied"))
        return False

    def keyboard(self, action: str | None = None) -> InlineKeyboardMarkup:
        rows = []
        for device in self._service.devices.values():
            actions = (action,) if action else ("wol", "status")
            rows.append([
                InlineKeyboardButton(
                    translate(self._language, f"button_{verb}", name=device.name),
                    callback_data=f"{verb}:{device.id}",
                ) for verb in actions
            ])
        return InlineKeyboardMarkup(rows)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._authorize(update):
            await update.effective_message.reply_text(translate(self._language, "help"), reply_markup=self.keyboard())

    async def list_devices(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorize(update):
            return
        devices = "\n".join(translate(self._language, "device_entry", id=device.id, name=device.name)
                            for device in self._service.devices.values())
        text = translate(self._language, "device_list", devices=devices)
        await update.effective_message.reply_text(text, reply_markup=self.keyboard())

    async def _send_typing(self, update: Update) -> None:
        try:
            await update.get_bot().send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        except TelegramError:
            # Optional feedback must not prevent the authorized operation.
            # Exception details can include token-bearing request URLs.
            LOGGER.warning("Indicatore di attività Telegram non disponibile.")

    async def _command(self, action: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorize(update):
            return
        if not context.args:
            await update.effective_message.reply_text(translate(self._language, "select_device"), reply_markup=self.keyboard(action))
        elif len(context.args) != 1:
            await update.effective_message.reply_text(translate(self._language, "command_usage", action=action))
        else:
            if context.args[0] in self._service.devices:
                await self._send_typing(update)
            await update.effective_message.reply_text(await self._service.execute(action, context.args[0]))

    async def wol(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._command("wol", update, context)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._command("status", update, context)

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._authorize(update):
            return
        query = update.callback_query
        if not isinstance(query.message, Message):
            await query.answer(translate(self._language, "message_unavailable"), show_alert=True)
            return
        # Treat callback_data as untrusted input, including callbacks from old menus.
        data = query.data
        parts = data.split(":") if isinstance(data, str) else []
        if len(parts) != 2 or parts[0] not in ("wol", "status") or parts[1] not in self._service.devices:
            await query.answer(translate(self._language, "invalid_selection"), show_alert=True)
            return
        await query.answer()  # Acknowledge before the potentially slow TR-064 operation.
        await self._send_typing(update)
        await query.message.reply_text(await self._service.execute(*parts))

    async def unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await self._authorize(update):
            await update.effective_message.reply_text(translate(self._language, "unknown_command"))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Exception strings, tracebacks and HTTP request URLs can contain the bot token.
    LOGGER.error("Errore Telegram/rete." if isinstance(context.error, TelegramError) else "Errore applicativo inatteso.")
    if isinstance(update, Update) and update.effective_chat and update.effective_chat.type == "private":
        settings = context.application.bot_data["settings"]
        if is_authorized(update, settings.allowed_user_ids) and update.effective_message:
            try:
                await update.effective_message.reply_text(translate(settings.language, "operation_failed"))
            except TelegramError:
                pass


def build_application(settings: Settings) -> Application:
    service = WolService(settings.devices, FritzRouter(settings), settings.language)
    handlers = BotHandlers(settings, service)

    async def shutdown(application: Application) -> None:
        await service.close()
        LOGGER.info("Arresto completato.")

    application = (
        Application.builder().token(settings.token)
        .concurrent_updates(False)
        .connect_timeout(10).read_timeout(10).write_timeout(10).pool_timeout(10)
        .get_updates_connect_timeout(10).get_updates_read_timeout(10)
        .get_updates_write_timeout(10).get_updates_pool_timeout(10)
        .post_shutdown(shutdown).build()
    )
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler(["start", "help"], handlers.help))
    application.add_handler(CommandHandler("list", handlers.list_devices))
    application.add_handler(CommandHandler("wol", handlers.wol))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CallbackQueryHandler(handlers.callback))
    application.add_handler(MessageHandler(filters.ALL, handlers.unknown))
    application.add_error_handler(on_error)
    return application

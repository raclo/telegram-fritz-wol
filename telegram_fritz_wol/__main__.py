"""Entrypoint: offline validation or graceful long polling."""

import argparse
import logging
import signal

from .config import ConfigError, load_settings


def configure_logging() -> logging.Logger:
    # Only application-controlled messages are emitted. Third-party HTTP/debug
    # logs may include tokens, SOAP bodies or credentials and stay suppressed.
    logging.basicConfig(handlers=[logging.NullHandler()], level=logging.CRITICAL + 1, force=True)
    logger = logging.getLogger("telegram_fritz_wol")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram FRITZ!Box WoL")
    parser.add_argument("--check-config", action="store_true", help="Valida senza chiamate di rete")
    args = parser.parse_args()
    logger = configure_logging()
    try:
        settings = load_settings()
    except ConfigError as exc:
        logger.error("Configurazione non valida: %s", exc)
        return 2
    if args.check_config:
        logger.info("Configurazione valida; nessuna chiamata di rete eseguita.")
        return 0
    try:
        from .bot import build_application

        application = build_application(settings)
        logger.info("Avvio long polling Telegram.")
        application.run_polling(
            timeout=20,
            bootstrap_retries=0,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            stop_signals=(signal.SIGINT, signal.SIGTERM),
        )
    except Exception:
        logger.error("Avvio o esecuzione falliti. Verificare configurazione e connettività.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

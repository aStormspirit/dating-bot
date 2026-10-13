"""Запуск моста Chat API ↔ chat-engine."""

from __future__ import annotations

import asyncio
import logging

from app import config
from app.bridge import Bridge
from app.chat_api import ChatApiClient
from app.engine import EngineClient
from app.events import consume_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("engine_bridge")


async def _run() -> None:
    chat_api = ChatApiClient(config.CHAT_API_URL, config.CHAT_API_ENGINE_TOKEN)
    engine = EngineClient(config.CHAT_ENGINE_URL, config.CHAT_ENGINE_TOKEN)
    bridge = Bridge(
        chat_api,
        engine,
        reconcile_interval=config.RECONCILE_INTERVAL_SECONDS,
        accounts_refresh=config.ACCOUNTS_REFRESH_SECONDS,
        heartbeat=config.HEARTBEAT_SECONDS,
    )
    logger.info("Chat API %s, chat-engine %s", config.CHAT_API_URL, config.CHAT_ENGINE_URL)
    try:
        await asyncio.gather(
            bridge.run(),
            consume_events(bridge, config.REDIS_URL, config.EVENTS_CONSUMER),
        )
    finally:
        await chat_api.aclose()
        await engine.aclose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()

import asyncio
import logging

from .bot import WidgetBot
from .config import Settings


def main() -> None:
    settings = Settings.from_env()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    asyncio.run(WidgetBot(settings).start_bot())


if __name__ == "__main__":
    main()

import asyncio

from src.app import start_app
from src.utils.core_logger import get_logger


async def main():
    await start_app()


if __name__ == '__main__':
    logger = get_logger(__name__)
    try:
        logger.info("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот завершил работу")
    except Exception as e:
        logger.exception(f"ошибка: {e}")
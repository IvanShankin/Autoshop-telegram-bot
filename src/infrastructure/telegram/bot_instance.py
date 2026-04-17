from aiogram import Bot, Dispatcher

from src.config import Config


def init_bot(conf: Config) -> Bot:
    return Bot(token=conf.secrets.token_bot)


def init_dispatcher() -> Dispatcher:
    return Dispatcher()


def init_bot_logger(conf: Config) -> Bot:
    return Bot(token=conf.secrets.token_logger_bot)


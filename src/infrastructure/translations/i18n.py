from functools import lru_cache
from gettext import translation

from src.config import get_config


class I18n:
    def __init__(self, language: str, domain: str):
        self.trans = translation(domain=domain, localedir=get_config().paths.locales_dir, languages=[language])

    def gettext(self, message: str)->str:
        return self.trans.gettext(message)

    def ngettext(self, msgid1: str,  msgid2: str, n: int)->str:
        return self.trans.ngettext(msgid1, msgid2, n)


@lru_cache(maxsize=None)
def get_i18n(language: str, domain: str)->I18n:
    return I18n(language, domain)


def get_text(language: str, domain: str, key: str) -> str:
    return get_i18n(language, domain).gettext(key)


def n_get_text(language: str, domain: str, msgid1: str,  msgid2: str, n: int) -> str:
    return get_i18n(language, domain).ngettext(msgid1, msgid2, n)
from functools import lru_cache
from gettext import translation

from src.config import LOCALES_DIR


class I18n:
    def __init__(self, lang: str, domain: str, localedir: str = LOCALES_DIR):
        self.trans = translation(domain=domain, localedir=localedir, languages=[lang])

    def gettext(self, message: str)->str:
        return self.trans.gettext(message)

    def ngettext(self, msgid1: str,  msgid2: str, n: int)->str:
        return self.trans.ngettext(msgid1, msgid2, n)

@lru_cache(maxsize=None)
def get_i18n(lang: str, domain: str)->I18n:
    return I18n(lang, domain)

def get_text(lang: str, domain: str, key: str) -> str:
    return get_i18n(lang, domain).gettext(key)

def n_get_text(lang: str, domain: str, msgid1: str,  msgid2: str, n: int) -> str:
    return get_i18n(lang, domain).ngettext(msgid1, msgid2, n)
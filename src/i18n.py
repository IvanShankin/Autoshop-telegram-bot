from functools import lru_cache
from gettext import translation

from src.config import LOCALES_DIR


class I18n:
    def __init__(self, lang: str, domain: str, localedir: str = LOCALES_DIR):
        self.trans = translation(domain=domain, localedir=localedir, languages=[lang])
        self._ = self.trans.gettext
        self.ngettext = self.trans.ngettext

@lru_cache(maxsize=None)
def get_i18n(lang: str, domain: str)->I18n:
    return I18n(lang, domain)
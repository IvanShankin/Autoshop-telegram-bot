
class TelegramException(Exception):
    """Все исключения связанные с telegram для сервисного слоя"""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class TelegramBadRequestService(TelegramException):
    pass

class TelegramAPIErrorService(TelegramException):
    pass

class TelegramNotFoundService(TelegramException):
    pass

class TelegramRetryAfterService(TelegramException):
    pass

class TelegramForbiddenErrorService(TelegramException):
    pass
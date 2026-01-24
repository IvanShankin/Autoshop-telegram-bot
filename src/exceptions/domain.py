"""
Доменные исключения.
Исключения, связанные с отсутствием сущностей в системе.
"""

class CategoryNotFound(Exception):
    pass

class UniversalProductNotFound(Exception):
    pass

class UniversalStorageNotFound(Exception):
    pass

class TypeAccountServiceNotFound(Exception):
    pass

class AccountServiceNotFound(Exception):
    pass

class UserNotFound(Exception):
    pass

class AdminNotFound(Exception):
    pass

class AccountCategoryNotFound(Exception):
    pass

class ProductAccountNotFound(Exception):
    pass

class ArchiveNotFount(Exception):
    pass

class DirNotFount(Exception):
    pass
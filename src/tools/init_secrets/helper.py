import os
from getpass import getpass


def read_secret(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value

    return getpass(f"Enter {name}: ")

import builtins
import traceback
import os
from contextlib import contextmanager

_PROJECT_ROOT = os.path.abspath(os.getcwd())
_ORIGINAL_IMPORT = builtins.__import__
_ENABLED = False


def _make_tracker(target_prefix: str):
    def _tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith(target_prefix):
            stack = traceback.extract_stack()

            project_frames = []
            for frame in stack:
                path = os.path.abspath(frame.filename)

                if path.startswith(_PROJECT_ROOT) and ".venv" not in path:
                    project_frames.append(
                        f"{path}:{frame.lineno} -> {frame.name}"
                    )

            raise RuntimeError(
                f"Обнаружен ранний импорт {target_prefix}!\n\n"
                f"Импортируемый модуль: {name}\n\n"
                "Цепочка импорта внутри проекта:\n"
                + ("\n".join(project_frames) if project_frames else "не найдено")
            )

        return _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)

    return _tracking_import


def enable_import_tracking(target_prefix: str = "aiogram"):
    """
    Включает отслеживание импорта.
    """
    global _ENABLED

    if _ENABLED:
        return

    builtins.__import__ = _make_tracker(target_prefix)
    _ENABLED = True


def disable_import_tracking():
    """
    Возвращает стандартное поведение импорта.
    """
    global _ENABLED

    if not _ENABLED:
        return

    builtins.__import__ = _ORIGINAL_IMPORT
    _ENABLED = False


@contextmanager
def track_imports(target_prefix: str = "aiogram"):
    """
    Контекстный менеджер для точечного трекинга.
    """
    enable_import_tracking(target_prefix)
    try:
        yield
    finally:
        disable_import_tracking()
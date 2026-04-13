"""
Configuration logging racine : timestamp, niveau, logger, fichier:ligne, fonction, message.
Variable d'environnement LOG_LEVEL (DEBUG, INFO, WARNING, ERROR).
"""
import logging
import os
import sys
from typing import Set


class AppLogFormatter(logging.Formatter):
    """Format classique + champs `extra` non standard en fin de ligne."""

    _RESERVED: Set[str] = frozenset(
        {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
            "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
            "relativeCreated", "thread", "threadName", "processName", "process", "message",
            "asctime", "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extra = {k: v for k, v in record.__dict__.items() if k not in self._RESERVED}
        if extra:
            line += " | extra=%s" % extra
        return line


def setup_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(pathname)s:%(lineno)d | "
        "%(funcName)s | %(message)s"
    )
    formatter = AppLogFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Laisse uvicorn/fastapi remonter vers la racine (pas de double handler).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
        lg.setLevel(level)

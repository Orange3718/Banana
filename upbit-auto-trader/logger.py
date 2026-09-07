from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import colorlog


def setup_logger(name: str = "upbit_auto_trader", log_dir: str = "logs") -> logging.Logger:
    """Configure a colored console logger and a rotating file logger."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    Path(log_dir).mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    color_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s%(reset)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    )

    console_handler = colorlog.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(color_formatter)

    file_handler = RotatingFileHandler(
        Path(log_dir) / "trading.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

"""
Simorgh - Logging setup
"""

import logging
import sys
from logging.handlers import RotatingFileHandler


def setup_logger(log_config: dict) -> logging.Logger:
    """
    Configure and return the root logger for Simorgh.

    Config keys (all optional):
        level   : DEBUG | INFO | WARNING | ERROR  (default: INFO)
        file    : path to log file (default: no file logging)
        max_mb  : max log file size in MB (default: 5)
        backups : number of backup files to keep (default: 3)
    """
    level_name = log_config.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    logger = logging.getLogger("simorgh")
    logger.setLevel(level)
    logger.handlers.clear()

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Optional rotating file handler
    log_file = log_config.get("file")
    if log_file:
        max_bytes = int(log_config.get("max_mb", 5)) * 1024 * 1024
        backups = int(log_config.get("backups", 3))
        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

"""
Simorgh - SOCKS5 Proxy with TLS Fragmentation
Entry point
"""

import asyncio
import logging
import sys
import argparse
from pathlib import Path

import yaml

from core.proxy import Socks5Proxy
from core.logger import setup_logger


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not path.is_file():
        raise ValueError(f"Config path is not a file: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError("Config file is empty or invalid YAML")

    return config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simorgh - SOCKS5 Proxy with TLS Fragmentation"
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level from config",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    if args.log_level:
        config.setdefault("logging", {})["level"] = args.log_level

    logger = setup_logger(config.get("logging", {}))
    logger.info("Simorgh starting up...")

    proxy = Socks5Proxy(config, logger)

    try:
        await proxy.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down...")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await proxy.stop()
        logger.info("Simorgh stopped.")


if __name__ == "__main__":
    asyncio.run(main())

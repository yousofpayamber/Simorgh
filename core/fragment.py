"""
Simorgh - TLS ClientHello detection and fragmentation logic
"""

import asyncio
import random
import logging
from typing import Optional

logger = logging.getLogger("simorgh.fragment")


# TLS record type for Handshake
TLS_HANDSHAKE = 0x16
# TLS ClientHello handshake type
TLS_CLIENT_HELLO = 0x01


def is_tls_client_hello(data: bytes) -> bool:
    """
    Returns True if data looks like a TLS ClientHello record.

    TLS record header:
      byte 0   : Content Type  (0x16 = Handshake)
      byte 1-2 : Version       (0x03 0x01 / 0x03 0x03)
      byte 3-4 : Length
    Handshake header (inside record):
      byte 5   : Handshake Type (0x01 = ClientHello)
    """
    if len(data) < 6:
        return False
    if data[0] != TLS_HANDSHAKE:
        return False
    if data[1] != 0x03:
        return False
    if data[5] != TLS_CLIENT_HELLO:
        return False
    return True


def fragment_data(data: bytes, min_size: int, max_size: int) -> list[bytes]:
    """Split data into chunks of random sizes between min_size and max_size."""
    chunks = []
    offset = 0
    while offset < len(data):
        size = random.randint(min_size, max_size)
        chunk = data[offset: offset + size]
        chunks.append(chunk)
        offset += size
    return chunks


async def send_fragmented(
    writer: asyncio.StreamWriter,
    data: bytes,
    frag_config: dict,
) -> None:
    """
    Send data in fragments with optional random ordering and delays.

    Args:
        writer       : asyncio StreamWriter to write to
        data         : raw bytes to fragment and send
        frag_config  : fragment section from config
    """
    min_size = frag_config.get("min_size", 10)
    max_size = frag_config.get("max_size", 40)
    delay_min = frag_config.get("delay_min", 0.01)
    delay_max = frag_config.get("delay_max", 0.05)
    randomize = frag_config.get("randomize_order", False)

    chunks = fragment_data(data, min_size, max_size)

    if randomize:
        # Keep first chunk in place (contains TLS record header),
        # only shuffle the rest to avoid breaking the TLS framing
        tail = chunks[1:]
        random.shuffle(tail)
        chunks = chunks[:1] + tail

    logger.debug(
        f"Sending {len(data)} bytes as {len(chunks)} fragments "
        f"(randomize={randomize})"
    )

    for chunk in chunks:
        writer.write(chunk)
        await writer.drain()
        delay = random.uniform(delay_min, delay_max)
        await asyncio.sleep(delay)

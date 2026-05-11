"""
Simorgh - SOCKS5 protocol handshake & authentication (RFC 1928 / RFC 1929)
"""

import asyncio
import logging
import struct
from enum import IntEnum
from typing import Tuple, Optional

logger = logging.getLogger("simorgh.socks5")


# ── SOCKS5 constants ──────────────────────────────────────────────────────────

SOCKS_VERSION = 0x05

class AuthMethod(IntEnum):
    NO_AUTH       = 0x00
    GSSAPI        = 0x01
    USERNAME_PASS = 0x02
    NO_ACCEPTABLE = 0xFF

class Command(IntEnum):
    CONNECT       = 0x01
    BIND          = 0x02
    UDP_ASSOCIATE = 0x03

class AddrType(IntEnum):
    IPV4   = 0x01
    DOMAIN = 0x03
    IPV6   = 0x04

class Reply(IntEnum):
    SUCCESS              = 0x00
    GENERAL_FAILURE      = 0x01
    NOT_ALLOWED          = 0x02
    NETWORK_UNREACHABLE  = 0x03
    HOST_UNREACHABLE     = 0x04
    CONNECTION_REFUSED   = 0x05
    TTL_EXPIRED          = 0x06
    CMD_NOT_SUPPORTED    = 0x07
    ADDR_TYPE_NOT_SUPP   = 0x08


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    """Read exactly n bytes; raises ConnectionError on short read."""
    data = await reader.readexactly(n)
    return data


def _reply_packet(reply_code: int) -> bytes:
    """Build a minimal SOCKS5 reply packet (IPv4 0.0.0.0:0)."""
    return struct.pack("!BBBBIH", SOCKS_VERSION, reply_code, 0x00, AddrType.IPV4, 0, 0)


# ── Auth negotiation ──────────────────────────────────────────────────────────

async def negotiate_auth(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    auth_config: dict,
) -> bool:
    """
    Perform SOCKS5 method sub-negotiation (RFC 1928 §3).
    Returns True on success, False if auth failed or method rejected.
    """
    auth_enabled = auth_config.get("enabled", False)

    # Client greeting: VER NMETHODS METHODS
    header = await _read_exact(reader, 2)
    if header[0] != SOCKS_VERSION:
        logger.warning(f"Not a SOCKS5 client (version byte: {header[0]:#x})")
        return False

    n_methods = header[1]
    if n_methods == 0:
        logger.warning("Client sent 0 auth methods")
        return False

    methods = set(await _read_exact(reader, n_methods))

    if auth_enabled:
        if AuthMethod.USERNAME_PASS not in methods:
            logger.warning("Client does not support username/password auth")
            writer.write(bytes([SOCKS_VERSION, AuthMethod.NO_ACCEPTABLE]))
            await writer.drain()
            return False
        # Tell client to use username/password
        writer.write(bytes([SOCKS_VERSION, AuthMethod.USERNAME_PASS]))
        await writer.drain()
        return await _verify_credentials(reader, writer, auth_config)
    else:
        # No auth required
        writer.write(bytes([SOCKS_VERSION, AuthMethod.NO_AUTH]))
        await writer.drain()
        return True


async def _verify_credentials(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    auth_config: dict,
) -> bool:
    """
    Verify username/password sub-negotiation (RFC 1929).
    Returns True on success.
    """
    # Sub-negotiation version
    ver = (await _read_exact(reader, 1))[0]
    if ver != 0x01:
        logger.warning(f"Invalid auth sub-negotiation version: {ver}")
        return False

    ulen = (await _read_exact(reader, 1))[0]
    username = (await _read_exact(reader, ulen)).decode("utf-8", errors="replace")

    plen = (await _read_exact(reader, 1))[0]
    password = (await _read_exact(reader, plen)).decode("utf-8", errors="replace")

    expected_user = auth_config.get("username", "")
    expected_pass = auth_config.get("password", "")

    # Constant-time comparison to prevent timing attacks
    import hmac
    user_ok = hmac.compare_digest(username, expected_user)
    pass_ok = hmac.compare_digest(password, expected_pass)

    if user_ok and pass_ok:
        writer.write(bytes([0x01, 0x00]))  # success
        await writer.drain()
        logger.debug(f"Auth success for user '{username}'")
        return True
    else:
        writer.write(bytes([0x01, 0x01]))  # failure
        await writer.drain()
        logger.warning(f"Auth failed for user '{username}'")
        return False


# ── Request parsing ───────────────────────────────────────────────────────────

async def parse_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> Optional[Tuple[str, int]]:
    """
    Parse SOCKS5 CONNECT request (RFC 1928 §4).
    Returns (host, port) on success, or None on failure (reply already sent).
    Only CONNECT command is supported.
    """
    header = await _read_exact(reader, 4)
    ver, cmd, _rsv, atype = header

    if ver != SOCKS_VERSION:
        logger.warning(f"Bad SOCKS version in request: {ver}")
        return None

    if cmd != Command.CONNECT:
        logger.warning(f"Unsupported SOCKS5 command: {cmd}")
        writer.write(_reply_packet(Reply.CMD_NOT_SUPPORTED))
        await writer.drain()
        return None

    # Parse destination address
    if atype == AddrType.IPV4:
        raw = await _read_exact(reader, 4)
        host = ".".join(str(b) for b in raw)
    elif atype == AddrType.DOMAIN:
        dlen = (await _read_exact(reader, 1))[0]
        host = (await _read_exact(reader, dlen)).decode("utf-8", errors="replace")
    elif atype == AddrType.IPV6:
        import socket
        raw = await _read_exact(reader, 16)
        host = socket.inet_ntop(socket.AF_INET6, raw)
    else:
        logger.warning(f"Unsupported address type: {atype}")
        writer.write(_reply_packet(Reply.ADDR_TYPE_NOT_SUPP))
        await writer.drain()
        return None

    port_raw = await _read_exact(reader, 2)
    port = struct.unpack("!H", port_raw)[0]

    return host, port


async def send_reply(
    writer: asyncio.StreamWriter,
    reply_code: int,
    bind_host: str = "0.0.0.0",
    bind_port: int = 0,
) -> None:
    """Send a SOCKS5 reply packet."""
    import socket
    try:
        packed_ip = socket.inet_aton(bind_host)
        writer.write(
            struct.pack("!BBBB4sH", SOCKS_VERSION, reply_code, 0x00, AddrType.IPV4, packed_ip, bind_port)
        )
    except OSError:
        writer.write(_reply_packet(reply_code))
    await writer.drain()

"""
Simorgh - SOCKS5 Proxy Server
Handles incoming connections, auth, CONNECT, TLS detection, and relay.
"""

import asyncio
import logging
from typing import Optional

from core.config_validator import validate_and_fill, ConfigError
from core.socks5 import (
    negotiate_auth,
    parse_request,
    send_reply,
    Reply,
)
from core.fragment import is_tls_client_hello, send_fragmented

BUFFER_SIZE = 65536  # 64 KB read buffer


class Socks5Proxy:
    def __init__(self, raw_config: dict, logger: Optional[logging.Logger] = None):
        try:
            self.config = validate_and_fill(raw_config)
        except ConfigError as e:
            raise ConfigError(f"Invalid configuration: {e}") from e

        self.logger = logger or logging.getLogger("simorgh.proxy")
        self._server: Optional[asyncio.Server] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._active_connections = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        host = self.config["listen_host"]
        port = self.config["listen_port"]
        max_conn = self.config["max_connections"]
        self._semaphore = asyncio.Semaphore(max_conn)

        self._server = await asyncio.start_server(
            self._handle_client,
            host,
            port,
            reuse_address=True,
        )

        auth_status = (
            f"auth=ON (user: {self.config['auth']['username']})"
            if self.config["auth"]["enabled"]
            else "auth=OFF"
        )
        frag_status = (
            "fragment=ON" if self.config["fragment"]["enabled"] else "fragment=OFF"
        )
        self.logger.info(
            f"Simorgh listening on {host}:{port} | "
            f"max_connections={max_conn} | {auth_status} | {frag_status}"
        )

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self.logger.info("Server socket closed.")

    # ── Connection handling ───────────────────────────────────────────────────

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Entry point for each new client connection."""
        peer = writer.get_extra_info("peername", ("?", 0))
        client_addr = f"{peer[0]}:{peer[1]}"

        # Enforce connection limit
        if not self._semaphore or self._semaphore.locked():
            # Try to acquire without blocking; refuse if at capacity
            if self._semaphore and not await self._try_acquire():
                self.logger.warning(
                    f"[{client_addr}] Connection limit reached. Rejecting."
                )
                writer.close()
                return

        async with self._semaphore:
            self._active_connections += 1
            self.logger.debug(
                f"[{client_addr}] New connection "
                f"(active: {self._active_connections})"
            )
            try:
                timeout = self.config.get("connection_timeout", 30)
                await asyncio.wait_for(
                    self._process_client(reader, writer, client_addr),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                self.logger.warning(f"[{client_addr}] Connection timed out")
            except asyncio.IncompleteReadError:
                self.logger.debug(f"[{client_addr}] Client disconnected early")
            except ConnectionResetError:
                self.logger.debug(f"[{client_addr}] Connection reset by peer")
            except Exception as e:
                self.logger.error(f"[{client_addr}] Unhandled error: {e}", exc_info=True)
            finally:
                self._active_connections -= 1
                self._safe_close(writer)
                self.logger.debug(
                    f"[{client_addr}] Connection closed "
                    f"(active: {self._active_connections})"
                )

    async def _try_acquire(self) -> bool:
        try:
            return self._semaphore.acquire_nowait() or True
        except Exception:
            return False

    async def _process_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        client_addr: str,
    ) -> None:
        """Full SOCKS5 handshake → connect → relay pipeline."""

        # 1. Auth negotiation
        auth_ok = await negotiate_auth(reader, writer, self.config["auth"])
        if not auth_ok:
            self.logger.warning(f"[{client_addr}] Auth failed")
            return

        # 2. Parse CONNECT request
        result = await parse_request(reader, writer)
        if result is None:
            return
        dest_host, dest_port = result
        self.logger.info(f"[{client_addr}] CONNECT → {dest_host}:{dest_port}")

        # 3. Connect to destination
        try:
            dest_reader, dest_writer = await asyncio.wait_for(
                asyncio.open_connection(dest_host, dest_port),
                timeout=self.config.get("connection_timeout", 30),
            )
        except asyncio.TimeoutError:
            self.logger.warning(f"[{client_addr}] Timeout connecting to {dest_host}:{dest_port}")
            await send_reply(writer, Reply.HOST_UNREACHABLE)
            return
        except OSError as e:
            self.logger.warning(f"[{client_addr}] Cannot connect to {dest_host}:{dest_port}: {e}")
            await send_reply(writer, Reply.CONNECTION_REFUSED)
            return

        # 4. Send success reply
        await send_reply(writer, Reply.SUCCESS)
        self.logger.debug(f"[{client_addr}] Tunnel established to {dest_host}:{dest_port}")

        # 5. Relay traffic bidirectionally
        try:
            await self._relay(reader, writer, dest_reader, dest_writer, client_addr)
        finally:
            self._safe_close(dest_writer)

    # ── Traffic relay ─────────────────────────────────────────────────────────

    async def _relay(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        dest_reader: asyncio.StreamReader,
        dest_writer: asyncio.StreamWriter,
        client_addr: str,
    ) -> None:
        """
        Bidirectional relay between client and destination.
        Applies TLS fragmentation on the first client→server chunk if enabled.
        """
        first_chunk = True
        frag_cfg = self.config.get("fragment", {})
        frag_enabled = frag_cfg.get("enabled", True)

        async def client_to_dest():
            nonlocal first_chunk
            while True:
                try:
                    data = await client_reader.read(BUFFER_SIZE)
                except Exception:
                    break
                if not data:
                    break

                if first_chunk and frag_enabled and is_tls_client_hello(data):
                    self.logger.debug(
                        f"[{client_addr}] TLS ClientHello detected — fragmenting"
                    )
                    await send_fragmented(dest_writer, data, frag_cfg)
                else:
                    dest_writer.write(data)
                    try:
                        await dest_writer.drain()
                    except Exception:
                        break

                first_chunk = False

            # Signal EOF to destination
            try:
                dest_writer.write_eof()
                await dest_writer.drain()
            except Exception:
                pass

        async def dest_to_client():
            while True:
                try:
                    data = await dest_reader.read(BUFFER_SIZE)
                except Exception:
                    break
                if not data:
                    break
                client_writer.write(data)
                try:
                    await client_writer.drain()
                except Exception:
                    break

        await asyncio.gather(
            client_to_dest(),
            dest_to_client(),
            return_exceptions=True,
        )

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_close(writer: asyncio.StreamWriter) -> None:
        try:
            if not writer.is_closing():
                writer.close()
        except Exception:
            pass

"""
Simorgh - Unit Tests
Run with: python -m pytest tests/ -v
"""

import asyncio
import struct
import pytest

from core.config_validator import validate_and_fill, ConfigError
from core.fragment import is_tls_client_hello, fragment_data
from core.socks5 import AuthMethod, Reply, SOCKS_VERSION


# ── Config Validator ──────────────────────────────────────────────────────────

class TestConfigValidator:

    def test_defaults_applied(self):
        cfg = validate_and_fill({})
        assert cfg["listen_host"] == "127.0.0.1"
        assert cfg["listen_port"] == 1080
        assert cfg["max_connections"] == 200
        assert cfg["fragment"]["enabled"] is True

    def test_user_values_override_defaults(self):
        cfg = validate_and_fill({"listen_port": 9090, "max_connections": 50})
        assert cfg["listen_port"] == 9090
        assert cfg["max_connections"] == 50

    def test_invalid_port_string(self):
        with pytest.raises(ConfigError):
            validate_and_fill({"listen_port": "abc"})

    def test_invalid_port_out_of_range(self):
        with pytest.raises(ConfigError):
            validate_and_fill({"listen_port": 99999})

    def test_auth_enabled_without_credentials(self):
        with pytest.raises(ConfigError):
            validate_and_fill({"auth": {"enabled": True, "username": "", "password": ""}})

    def test_auth_enabled_with_credentials(self):
        cfg = validate_and_fill({
            "auth": {"enabled": True, "username": "user", "password": "pass"}
        })
        assert cfg["auth"]["enabled"] is True

    def test_fragment_min_greater_than_max(self):
        with pytest.raises(ConfigError):
            validate_and_fill({"fragment": {"min_size": 100, "max_size": 10}})

    def test_fragment_negative_delay(self):
        with pytest.raises(ConfigError):
            validate_and_fill({"fragment": {"delay_min": -1}})

    def test_negative_max_connections(self):
        with pytest.raises(ConfigError):
            validate_and_fill({"max_connections": 0})


# ── TLS Detection ─────────────────────────────────────────────────────────────

class TestTLSDetection:

    def _make_client_hello(self) -> bytes:
        """Build a minimal valid TLS ClientHello byte sequence."""
        # Record header: type=Handshake(0x16), version=TLS1.0(0x03,0x01), length=...
        # Handshake header: type=ClientHello(0x01)
        payload = bytes(100)  # dummy payload
        handshake = bytes([0x01]) + struct.pack("!I", len(payload))[1:] + payload
        record = bytes([0x16, 0x03, 0x01]) + struct.pack("!H", len(handshake)) + handshake
        return record

    def test_detects_client_hello(self):
        data = self._make_client_hello()
        assert is_tls_client_hello(data) is True

    def test_rejects_non_tls(self):
        assert is_tls_client_hello(b"GET / HTTP/1.1\r\n") is False

    def test_rejects_short_data(self):
        assert is_tls_client_hello(b"\x16\x03") is False

    def test_rejects_wrong_content_type(self):
        data = self._make_client_hello()
        data = bytes([0x17]) + data[1:]  # Change to ApplicationData
        assert is_tls_client_hello(data) is False

    def test_rejects_wrong_handshake_type(self):
        data = self._make_client_hello()
        # byte 5 is handshake type; change to ServerHello(0x02)
        data = data[:5] + bytes([0x02]) + data[6:]
        assert is_tls_client_hello(data) is False


# ── Fragmentation ─────────────────────────────────────────────────────────────

class TestFragmentation:

    def test_reassembly_is_complete(self):
        data = bytes(range(256))
        chunks = fragment_data(data, min_size=10, max_size=30)
        assert b"".join(chunks) == data

    def test_chunk_sizes_in_range(self):
        data = bytes(1000)
        chunks = fragment_data(data, min_size=5, max_size=20)
        for chunk in chunks[:-1]:  # last chunk may be smaller
            assert 5 <= len(chunk) <= 20

    def test_single_byte_data(self):
        data = b"\xff"
        chunks = fragment_data(data, min_size=1, max_size=10)
        assert b"".join(chunks) == data

    def test_empty_data(self):
        chunks = fragment_data(b"", min_size=1, max_size=10)
        assert chunks == []


# ── SOCKS5 Handshake (async) ─────────────────────────────────────────────────

class TestSocks5Auth:

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _make_stream_pair(self, data: bytes):
        """Create a mock reader with data and a capturing writer."""
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()

        # Minimal mock writer
        class MockWriter:
            def __init__(self):
                self.buf = b""
                self._closing = False
            def write(self, d):
                self.buf += d
            async def drain(self):
                pass
            def is_closing(self):
                return self._closing
            def close(self):
                self._closing = True
            def get_extra_info(self, key, default=None):
                return default

        return reader, MockWriter()

    def test_no_auth_success(self):
        from core.socks5 import negotiate_auth
        # Client greeting: SOCKS5, 1 method, NO_AUTH
        data = bytes([SOCKS_VERSION, 1, AuthMethod.NO_AUTH])
        reader, writer = self._make_stream_pair(data)
        result = self._run(negotiate_auth(reader, writer, {"enabled": False}))
        assert result is True
        assert writer.buf == bytes([SOCKS_VERSION, AuthMethod.NO_AUTH])

    def test_no_auth_client_only_offers_userpass(self):
        from core.socks5 import negotiate_auth
        # Client offers USERNAME_PASS but server has auth disabled → should still work
        data = bytes([SOCKS_VERSION, 1, AuthMethod.USERNAME_PASS])
        reader, writer = self._make_stream_pair(data)
        result = self._run(negotiate_auth(reader, writer, {"enabled": False}))
        assert result is True

    def test_auth_required_client_no_support(self):
        from core.socks5 import negotiate_auth
        # Client only offers NO_AUTH but server requires credentials
        data = bytes([SOCKS_VERSION, 1, AuthMethod.NO_AUTH])
        reader, writer = self._make_stream_pair(data)
        result = self._run(
            negotiate_auth(reader, writer, {"enabled": True, "username": "u", "password": "p"})
        )
        assert result is False
        assert writer.buf[-1] == AuthMethod.NO_ACCEPTABLE

    def test_wrong_socks_version(self):
        from core.socks5 import negotiate_auth
        data = bytes([0x04, 1, AuthMethod.NO_AUTH])  # SOCKS4
        reader, writer = self._make_stream_pair(data)
        result = self._run(negotiate_auth(reader, writer, {"enabled": False}))
        assert result is False

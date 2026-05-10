import asyncio
import struct

from core.fragment import send_fragmented
from core.logger import log
from core.tls import is_tls_client_hello

BUFFER_SIZE = 8192


class Socks5Proxy:

    def __init__(self, config):
        self.config = config

    async def handle_client(self, reader, writer):

        try:
            await self.handshake(reader, writer)

            host, port = await self.parse_request(reader)

            log(f"CONNECT {host}:{port}")

            remote_reader, remote_writer = await asyncio.open_connection(
                host,
                port
            )

            await self.send_success(writer)

            await asyncio.gather(
                self.client_to_remote(reader, remote_writer),
                self.remote_to_client(remote_reader, writer)
            )

        except Exception as e:
            log(f"ERROR: {e}")

        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def handshake(self, reader, writer):

        data = await reader.read(2)

        if len(data) < 2:
            raise Exception("Invalid handshake")

        version, nmethods = data

        if version != 5:
            raise Exception("Only SOCKS5 supported")

        await reader.read(nmethods)

        writer.write(b"\x05\x00")
        await writer.drain()

    async def parse_request(self, reader):

        data = await reader.read(4)

        if len(data) < 4:
            raise Exception("Invalid request")

        version, cmd, _, atyp = data

        if cmd != 1:
            raise Exception("Only CONNECT supported")

        if atyp == 1:

            addr = await reader.read(4)
            host = ".".join(map(str, addr))

        elif atyp == 3:

            length = (await reader.read(1))[0]
            host = (await reader.read(length)).decode()

        else:
            raise Exception("Unsupported address type")

        port = struct.unpack(">H", await reader.read(2))[0]

        return host, port

    async def send_success(self, writer):

        writer.write(
            b"\x05\x00\x00\x01"
            b"\x00\x00\x00\x00"
            b"\x00\x00"
        )

        await writer.drain()

    async def client_to_remote(self, reader, writer):

        first_packet = True

        while True:

            data = await reader.read(BUFFER_SIZE)

            if not data:
                break

            if first_packet and is_tls_client_hello(data):

                log("TLS ClientHello detected")

                await send_fragmented(
                    writer,
                    data,
                    self.config
                )

                first_packet = False
                continue

            writer.write(data)
            await writer.drain()

    async def remote_to_client(self, reader, writer):

        while True:

            data = await reader.read(BUFFER_SIZE)

            if not data:
                break

            writer.write(data)
            await writer.drain()

    async def start(self):

        server = await asyncio.start_server(
            self.handle_client,
            self.config["listen_host"],
            self.config["listen_port"]
        )

        log(
            f"Listening on "
            f"{self.config['listen_host']}:"
            f"{self.config['listen_port']}"
        )

        async with server:
            await server.serve_forever()
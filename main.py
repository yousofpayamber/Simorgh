import asyncio
import yaml

from core.proxy import Socks5Proxy


async def main():

    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    proxy = Socks5Proxy(config)

    await proxy.start()


if __name__ == "__main__":
    asyncio.run(main())
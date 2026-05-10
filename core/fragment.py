import asyncio
import random


async def send_fragmented(writer, data, config):

    fragment_config = config["fragment"]

    min_size = fragment_config["min_size"]
    max_size = fragment_config["max_size"]

    delay_min = fragment_config["delay_min"]
    delay_max = fragment_config["delay_max"]

    offset = 0

    while offset < len(data):

        size = random.randint(min_size, max_size)

        chunk = data[offset:offset + size]

        writer.write(chunk)
        await writer.drain()

        offset += size

        await asyncio.sleep(
            random.uniform(delay_min, delay_max)
        )
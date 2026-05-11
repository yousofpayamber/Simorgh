import httpx


async def resolve_doh(domain):

    url = "https://dns.google/resolve"

    params = {
        "name": domain,
        "type": "A"
    }

    async with httpx.AsyncClient() as client:

        response = await client.get(url, params=params)

        data = response.json()

    if "Answer" not in data:
        return None

    return data["Answer"][0]["data"]
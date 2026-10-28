#!/usr/bin/env python3
"""
A small check that the demo server really runs and both tools answer.

It starts server.py the same way an MCP client would (over stdio),
lists the tools, calls search_listings, then takes the first listing
it finds and calls get_listing_detail on it. Nothing here is mocked:
both calls read the live public listing search.

Run:
  pip install -r requirements.txt
  python3 test_client.py
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    # env is passed through so the server inherits this machine's
    # network settings (proxy variables and the like), the same way a
    # desktop MCP client passes its own environment to the server.
    params = StdioServerParameters(
        command=sys.executable, args=["server.py"], env=dict(os.environ)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("Tools the server offers:", names)
            assert "search_listings" in names and "get_listing_detail" in names

            print("\n--- search_listings(area='Clearwater', max_price=600000, min_beds=3) ---")
            result = await session.call_tool(
                "search_listings",
                {"area": "Clearwater", "max_price": 600000, "min_beds": 3, "limit": 3},
            )
            text = result.content[0].text
            print(text)
            data = json.loads(text)
            assert data["count"] > 0, "search returned no listings"
            first_id = data["listings"][0]["listing_id"]
            assert first_id, "first listing has no ID"

            print(f"\n--- get_listing_detail(listing_id='{first_id}') ---")
            result = await session.call_tool(
                "get_listing_detail", {"listing_id": first_id}
            )
            text = result.content[0].text
            print(text)
            detail = json.loads(text)
            assert detail["listing_id"] == first_id
            assert detail["price"], "detail has no price"

            print("\nPASS: server runs, both tools answered with live public data.")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

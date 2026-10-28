# Listing Lookup Demo: an MCP server

A small MCP server that lets an AI assistant search real home listings and pull up the full public detail on any one of them. Two tools, one job: answer questions like "what is for sale in Clearwater under $600,000 with at least three bedrooms" with live listings, not guesses.

**This is a demo build of a production pattern.** It is not the production server. It rebuilds the listing part of a working system, small enough to read in five minutes and run in two.

## The two tools

**search_listings**: search by area, price, and beds.
- `area`: a city name (Clearwater, St. Petersburg, Tampa), a county (Pinellas), or a 5-digit ZIP code. Optional.
- `min_price` / `max_price`: whole dollars. Optional.
- `min_beds`: minimum bedrooms. Optional.
- `limit`: how many listings come back, up to 25. Default 10.

Each result has the listing ID, status, price, beds, baths, square feet, address, a photo, and a link to the full listing page.

**get_listing_detail**: everything public about one listing.
- `listing_id`: the ID from a search result, for example TB8530778.

Returns price, status, beds, baths, square feet, property type, year built, the listing's own public description, and every other public field on the page.

## Where the pattern comes from

This demo is modeled on the listing tools inside a production MCP server I built for the agent system for real estate agents. In production, that server does more: it holds the instructions that tell a real estate agent's AI how to run the agent's day, and it answers knowledge questions for the system. The listing tools are the part that reads only public data, so they are the part that can be shown. This demo rebuilds that one pattern on its own: same idea, same public source, fresh small code, so anyone can run it and see how the production system handles listing questions. The production server itself is not included here.

## What it reads

Everlane Realty's public listing search, [search.everlanerealty.com](https://search.everlanerealty.com): the same pages anyone can open in a browser. No account, no key, no database, no private data. Results are whatever the public search shows at that moment, including rentals the MLS feed carries.

## How to run it

You need Python 3.10 or newer.

```
pip install -r requirements.txt
python3 server.py
```

The server speaks MCP over stdio, which is how most MCP clients connect. To use it with an MCP client such as Claude Desktop or Claude Code, add it to the client's server config:

```json
{
  "mcpServers": {
    "selenko-listings-demo": {
      "command": "python3",
      "args": ["/path/to/server.py"]
    }
  }
}
```

## Three example prompts

Once the server is connected, ask the assistant:

1. "Search for homes in Clearwater under $600,000 with at least 3 bedrooms."
2. "What is for sale in ZIP code 33760 right now?"
3. "Show me the full detail for listing TB8530778: beds, baths, year built, and the description." (Listing IDs come from the search results.)

## Check that it works

```
python3 test_client.py
```

This starts the server the same way an MCP client would, lists its tools, runs a real search, and then pulls the full detail on the first listing it finds. It prints PASS at the end when both tools answer with live public data.

## Files

- `server.py`: the whole server. Two tools, standard MCP setup, plain Python.
- `test_client.py`: the check described above.
- `requirements.txt`: the one dependency, the official MCP Python SDK.

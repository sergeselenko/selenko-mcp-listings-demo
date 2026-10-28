#!/usr/bin/env python3
"""
Listing lookup demo: a small MCP server with two tools.

This is a demo build of a production pattern. The production server
(selenko-mcp) runs the agent system for real estate agents and includes
two listing tools that read Everlane Realty's public listing search.
This demo rebuilds just that listing pattern, small and readable:
no credentials, no database, no private data: it reads the same
public search pages anyone can open in a browser
(search.everlanerealty.com, an IDX Broker search site).

Tools:
  search_listings    search by area (city name or ZIP code), price, beds
  get_listing_detail  full public detail for one listing, by listing ID

Run it:
  pip install -r requirements.txt
  python3 server.py            # speaks MCP over stdio
"""

import html as html_lib
import json
import re
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

BASE = "https://search.everlanerealty.com"
IDX_ID = "d003"  # the MLS feed id used by Everlane's public search
USER_AGENT = "Mozilla/5.0 (compatible; selenko-mcp-listings-demo/1.0)"
TIMEOUT = 25

mcp = FastMCP("selenko-listings-demo")

_area_cache: dict[str, dict[str, str]] | None = None


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def area_index() -> dict[str, dict[str, str]]:
    """Map of area name -> IDX id, read from the public search page.

    The public search page carries a picker of every city, county, and
    ZIP code in the feed, each with the numeric id the results URL
    expects. We read that picker once and reuse it.
    """
    global _area_cache
    if _area_cache is not None:
        return _area_cache
    page = fetch(f"{BASE}/idx/search")
    index: dict[str, dict[str, str]] = {"city": {}, "county": {}, "zipcode": {}}
    for value, kind, name in re.findall(
        r'value="(\d+)" data-type="(city|county|zipcode)">([^<]+)</option>', page
    ):
        index[kind][name.strip().lower()] = value
    _area_cache = index
    return index


def resolve_area(area: str) -> tuple[str, str]:
    """Turn a plain area name into the results-URL parameter for it.

    Returns (param_name, id). Raises ValueError with a plain message
    when the area is not in the public feed.
    """
    index = area_index()
    key = area.strip().lower()
    if re.fullmatch(r"\d{5}", key):
        # City and county lookups take the picker's numeric id; the ZIP
        # lookup takes the ZIP code itself. Both verified against the
        # live public search.
        if key in index["zipcode"]:
            return "zipcode[]", key
        raise ValueError(f"ZIP code {area} is not in the public listing feed.")
    # City names in the feed sometimes drop punctuation ("St Petersburg"
    # vs "St. Petersburg"), so compare with punctuation removed too.
    squashed = re.sub(r"[^a-z0-9 ]", "", key)
    for kind in ("city", "county"):
        for name, value in index[kind].items():
            if name == key or re.sub(r"[^a-z0-9 ]", "", name) == squashed:
                return f"{kind}[]", value
    raise ValueError(
        f"Area '{area}' is not in the public listing feed. "
        "Try a city name in the Tampa Bay area, or a 5-digit ZIP code."
    )


def parse_results(page: str, limit: int) -> list[dict]:
    """Pull the listing cards out of a public results page.

    Each card on the page carries its key facts in data attributes
    (price, beds, baths, square feet, listing id, detail link, photo),
    plus a printed address and status. We read those, nothing else.
    """
    listings = []
    cells = [
        m.group(0)
        for m in re.finditer(
            r'<article[^>]*class="IDX-resultsCell[^"]*"[^>]*>.*?</article>',
            page,
            re.S,
        )
    ]
    for cell in cells[:limit]:
        attrs = dict(
            re.findall(r'data-(price|beds|baths|sqft|listingid|idxStatus)="([^"]*)"', cell)
        )
        url_m = re.search(r'data-detailsURL="([^"]+)"', cell)
        photo_m = re.search(r'data-photo="([^"]+)"', cell)
        status_m = re.search(
            r'--propStatus.*?idx-text">([^<]+)<', cell, re.S
        )

        def addr(cls: str) -> str:
            m = re.search(rf'address--{cls}[^"]*">(.*?)</span>', cell, re.S)
            return clean(m.group(1)) if m else ""

        number, street = addr("number"), addr("street-name")
        address = " ".join(p for p in [number, street] if p)
        city, state, zipcode = addr("City"), addr("state-abrv"), addr("zip")
        listings.append(
            {
                "listing_id": attrs.get("listingid", ""),
                "status": clean(status_m.group(1)) if status_m else attrs.get("idxStatus", ""),
                "price": int(attrs["price"]) if attrs.get("price", "").isdigit() else None,
                "beds": attrs.get("beds", ""),
                "baths": attrs.get("baths", ""),
                "sqft": attrs.get("sqft", ""),
                "address": address,
                "city": city,
                "state": state,
                "zip": zipcode.replace("&nbsp;", "").strip(),
                "detail_url": url_m.group(1) if url_m else "",
                "photo": photo_m.group(1) if photo_m else "",
            }
        )
    return listings


@mcp.tool()
def search_listings(
    area: str = "",
    min_price: int = 0,
    max_price: int = 0,
    min_beds: int = 0,
    limit: int = 10,
) -> str:
    """Search public real estate listings by area, price, and beds.

    Reads Everlane Realty's public listing search
    (search.everlanerealty.com). All arguments are optional:
    area is a city name (for example "Clearwater") or a 5-digit ZIP
    code; min_price / max_price are whole dollars; min_beds is a
    minimum bedroom count; limit caps how many listings come back
    (default 10, max 25).
    """
    limit = max(1, min(limit, 25))
    params: dict[str, str] = {"idxID": IDX_ID, "per": str(limit), "srt": "newest"}
    if area:
        try:
            param, value = resolve_area(area)
        except ValueError as err:
            return json.dumps({"error": str(err)}, indent=2)
        params[param] = value
    if min_price > 0:
        params["lp"] = str(min_price)
    if max_price > 0:
        params["hp"] = str(max_price)
    if min_beds > 0:
        params["bd"] = str(min_beds)

    url = f"{BASE}/idx/results/listings?" + urllib.parse.urlencode(params)
    try:
        page = fetch(url)
    except Exception as err:  # network or site error: say so plainly
        return json.dumps(
            {"error": f"Could not read the public listing search: {err}"}, indent=2
        )
    listings = parse_results(page, limit)
    return json.dumps(
        {"source": url, "count": len(listings), "listings": listings}, indent=2
    )


@mcp.tool()
def get_listing_detail(listing_id: str) -> str:
    """Get the full public detail for one listing, by its listing ID.

    The listing ID comes from search_listings results (for example
    "TB8530778"). Reads the listing's public detail page on
    search.everlanerealty.com and returns the printed facts: price,
    status, beds, baths, square feet, address, property type, year
    built, the public remarks, and the detail page link.
    """
    listing_id = listing_id.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{4,20}", listing_id):
        return json.dumps(
            {"error": f"'{listing_id}' does not look like a listing ID."}, indent=2
        )
    url = f"{BASE}/idx/details/listing/{IDX_ID}/{listing_id}"
    try:
        page = fetch(url)
    except Exception as err:
        return json.dumps(
            {"error": f"Could not read the listing page: {err}"}, indent=2
        )
    if "IDX-details" not in page and "IDX-field" not in page:
        return json.dumps(
            {"error": f"No public listing found with ID {listing_id}."}, indent=2
        )

    fields: dict[str, str] = {}
    for label, value in re.findall(
        r'IDX-field[^"]*">\s*<span class="IDX-label">([^<]+)</span>'
        r'\s*<span class="IDX-text">(.*?)</span>',
        page,
        re.S,
    ):
        fields.setdefault(label.strip(), clean(value))

    remarks_m = re.search(r'property="og:description" content="([^"]+)"', page)
    addr_m = re.search(r'IDX-detailsAddress[^>]*>(.*?)</div>', page, re.S)
    photos = re.findall(r'mlsphotos\.idxbroker\.com/photos/[a-f0-9/]+', page)

    detail = {
        "listing_id": listing_id,
        "address": clean(addr_m.group(1)) if addr_m else "",
        "price": fields.get("Price", ""),
        "status": fields.get("Status", ""),
        "beds": fields.get("Bedrooms", ""),
        "baths": fields.get("Total Baths", ""),
        "sqft": fields.get("SqFt", ""),
        "property_type": fields.get("Property Type", ""),
        "property_sub_type": fields.get("Property Sub Type", ""),
        "year_built": fields.get("Year Built", ""),
        "description": html_lib.unescape(remarks_m.group(1)) if remarks_m else "",
        "photo_count": len(set(photos)),
        "detail_url": url,
        "all_public_fields": fields,
    }
    return json.dumps(detail, indent=2)


if __name__ == "__main__":
    mcp.run()  # stdio transport

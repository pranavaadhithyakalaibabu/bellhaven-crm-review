"""Requirement 1: collect every community from the live website."""

import re
import html
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
import settings
import crm
from normalization import clean, norm, street


def verify_absent(account):
    """Require a fresh complete crawl before treating a facility as absent."""
    locations, _ = scrape()
    for location in locations:
        same_city = (
            norm(account["billing_city"]) == norm(location["billing_city"])
            and account["billing_state"] == location["billing_state"]
        )
        same_name = norm(account["name"]) == norm(location["name"])
        same_address = street(account["billing_street"]) == street(
            location["billing_street"]
        )
        if same_name or (same_city and same_address):
            raise RuntimeError(
                "Facility is on the website now. Rerun and review; no CRM change made."
            )


CARE = {
    "Assisted Living": "Assisted Living",
    "Memory Support": "Memory Care",
    "Short-Term Rehabilitation & Nursing": "Skilled Nursing",
    "Independent Living": "Independent Living",
}


def parse_location(path, raw):
    """Extract the address and care offerings from one community page."""
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S)
    pairs = {
        clean(k): v
        for k, v in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", raw, re.S)
    }
    if not heading or "Address" not in pairs:
        raise ValueError("Missing location fields: " + path)
    address_lines = re.split(r"<br\s*/?>", pairs["Address"])
    city_state_zip = re.fullmatch(
        r"(.+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)", clean(address_lines[-1])
    )
    if len(address_lines) != 2 or not city_state_zip:
        raise ValueError("Unrecognized address: " + path)
    offerings = [
        clean(x)
        for x in re.findall(
            r"<span[^>]*>(.*?)</span>", pairs.get("Care Offerings", ""), re.S
        )
    ]
    if not offerings or any(x not in CARE for x in offerings):
        raise ValueError("Unknown care type: " + path)
    return dict(
        name=clean(heading[1]),
        billing_street=clean(address_lines[0]),
        billing_city=city_state_zip[1],
        billing_state=city_state_zip[2],
        billing_zip=city_state_zip[3],
        care_offerings=offerings,
        care_type="; ".join(CARE[x] for x in offerings),
        administrator=clean(pairs.get("Administrator", "")),
        phone=clean(pairs.get("Phone", "")),
        source_url=settings.BASE + path,
        source_hash=hashlib.sha256(raw.encode()).hexdigest(),
    )


def scrape():
    """Collect directory and homepage links, then check crawl completeness."""
    pages = {}
    pending_pages = ["/", "/about", "/communities"]
    directory_links = set()
    expected_count = None
    while pending_pages:
        path = pending_pages.pop(0)
        if path in pages:
            continue
        raw = crm.request(path)
        pages[path] = raw
        if path.startswith("/communities") and "/" not in path[len("/communities") :]:
            count_match = re.search(r"(\d+) communities listed", raw)
            if not count_match:
                raise RuntimeError("Directory count missing")
            if expected_count is not None and expected_count != int(count_match[1]):
                raise RuntimeError("Directory changed mid-scrape")
            expected_count = int(count_match[1])
        for link in re.findall(r'href=["\']([^"\']+)["\']', raw):
            link = html.unescape(link)
            if re.fullmatch(r"/communities\?page=\d+", link) and link not in pages:
                pending_pages.append(link)
            if re.fullmatch(r"/communities/[a-z0-9-]+", link):
                if path.startswith("/communities"):
                    directory_links.add(link)
        if len(pages) > 50:
            raise RuntimeError("Pagination loop")
    links = {
        x
        for raw in pages.values()
        for x in re.findall(r'href=["\'](/communities/[a-z0-9-]+)["\']', raw)
    }
    if expected_count is None or len(directory_links) != expected_count:
        raise RuntimeError("Incomplete directory; no proposals generated")

    def fetch(path):
        return path, crm.request(path)

    for path, raw in ThreadPoolExecutor(6).map(fetch, sorted(links)):
        pages[path] = raw
    locations = [parse_location(path, pages[path]) for path in sorted(links)]
    if len({x["source_url"] for x in locations}) != len(locations):
        raise RuntimeError("Duplicate location")
    previous = settings.DATA / "locations.json"
    if (
        previous.exists()
        and len(locations) < len(json.loads(previous.read_text())) * 0.8
    ):
        raise RuntimeError("Large website drop; investigate before proposing removals")
    return locations, pages

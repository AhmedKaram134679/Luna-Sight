#!/usr/bin/env python3
"""Discover source URLs explicitly exposed by NASA PGDA product pages.

No URL is synthesized: candidates must occur in an href/src attribute and
match the requested product identifier in either the attribute URL or link text.
"""
from __future__ import annotations

import argparse
import json
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PRODUCTS = {
    "https://pgda.gsfc.nasa.gov/products/90": (
        "LDEM_80S_20MPP_ADJ.TIF",
        "LDEM_80S_20MPP_ADJ_EFFRES.TIF",
        "LDEM_80S_20MPP_ADJ_ERR.TIF",
        "LDEC_80S_20MPP_ADJ.TIF",
    ),
    "https://pgda.gsfc.nasa.gov/products/81": (
        "ldem_87s_5mpp",
        "ldec_87s_5mpp",
    ),
}


def discover_links(html: str, page_url: str, requested_names: tuple[str, ...]) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    matches = {name: [] for name in requested_names}
    for tag in soup.find_all(True):
        label = tag.get_text(" ", strip=True)
        for attribute in ("href", "src"):
            raw = tag.get(attribute)
            if not isinstance(raw, str) or not raw.strip():
                continue
            absolute = urljoin(page_url, raw.strip())
            parsed = urlparse(absolute)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            descriptive = " ".join(str(tag.get(key, "")) for key in ("alt", "title", "aria-label", "download"))
            searchable = (raw + " " + label + " " + descriptive + " " + PurePosixPath(parsed.path).name).casefold()
            for name in requested_names:
                needle = name.casefold()
                if needle in searchable and absolute not in matches[name]:
                    matches[name].append(absolute)

    missing = [name for name, urls in matches.items() if not urls]
    if missing:
        raise ValueError(
            f"{page_url} exposes no href/src URL or link text matching: {', '.join(missing)}"
        )
    return {name: urls for name, urls in matches.items()}


def acquire(session: requests.Session, pages: dict[str, tuple[str, ...]]) -> dict:
    result = {}
    for page, names in pages.items():
        response = session.get(page, timeout=120)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").casefold()
        if "html" not in content_type and "<html" not in response.text[:1000].casefold():
            raise ValueError(f"Expected HTML product page at {page}, got {content_type or 'unknown content type'}")
        discovered = discover_links(response.text, page, names)
        for name, urls in discovered.items():
            result[name] = {
                "product_page": page,
                "download_url": urls[0],
                "candidate_urls": urls,
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="official_sources.json")
    args = parser.parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = "LunaSight scientific data acquisition; contact via repository"
    found = acquire(session, PRODUCTS)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(found, stream, indent=2)
        stream.write("\n")
    print(json.dumps(found, indent=2))


if __name__ == "__main__":
    main()

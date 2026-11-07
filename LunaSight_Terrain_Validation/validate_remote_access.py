#!/usr/bin/env python3
"""Diagnose HTTP access required for remote COG range reads."""
from __future__ import annotations
import argparse
import json
import sys
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TRANSIENT_STATUS = (429, 500, 502, 503, 504)

def build_session():
    retry = Retry(total=4, connect=4, read=4, status=4, backoff_factor=1.0,
                  status_forcelist=TRANSIENT_STATUS,
                  allowed_methods=frozenset({"HEAD", "GET"}), raise_on_status=False)
    session = requests.Session()
    session.headers["User-Agent"] = "LunaSight scientific data acquisition; range diagnostic"
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def diagnose_url(session, url, range_size=1024):
    if range_size < 1:
        raise ValueError("range_size must be positive")
    head = session.head(url, allow_redirects=True, timeout=(20, 60))
    head_info = {
        "status": head.status_code, "final_url": head.url,
        "final_host": urlparse(head.url).netloc,
        "content_length": head.headers.get("Content-Length"),
        "accept_ranges": head.headers.get("Accept-Ranges"),
        "etag": head.headers.get("ETag"),
        "last_modified": head.headers.get("Last-Modified"),
        "content_type": head.headers.get("Content-Type"),
    }
    # HEAD may be unsupported (405/501); GET Range is the decisive test.
    if head.status_code >= 500:
        raise RuntimeError(f"HEAD failed after retries: HTTP {head.status_code}")
    response = session.get(url, headers={"Range": f"bytes=0-{range_size-1}"},
                           allow_redirects=True, timeout=(20, 90))
    body = response.content
    content_range = response.headers.get("Content-Range", "")
    result = {
        "url": url, "head": head_info,
        "range": {
            "status": response.status_code, "final_url": response.url,
            "final_host": urlparse(response.url).netloc,
            "content_range": content_range,
            "content_length": response.headers.get("Content-Length"),
            "content_type": response.headers.get("Content-Type"),
            "received_bytes": len(body), "expected_bytes": range_size,
        },
    }
    if response.status_code != 206:
        raise RuntimeError(f"Range request expected HTTP 206, received {response.status_code}")
    if not content_range.startswith(f"bytes 0-{range_size-1}/"):
        raise RuntimeError(f"Unexpected Content-Range {content_range!r}")
    if len(body) != range_size:
        raise RuntimeError(f"Truncated Range body: received {len(body)}, expected {range_size}")
    content_type = response.headers.get("Content-Type", "").casefold()
    if "text/html" in content_type or body.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise RuntimeError("Range response is HTML, not raster bytes")
    result["status"] = "PASS"
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="official_sources.json")
    parser.add_argument("--output", default="remote_access_diagnostics.json")
    parser.add_argument("--range-size", type=int, default=1024)
    args = parser.parse_args()
    with open(args.sources, encoding="utf-8") as stream:
        sources = json.load(stream)
    urls = sorted({item["download_url"] for item in sources.values()})
    session = build_session()
    results, failures = {}, []
    for url in urls:
        try:
            results[url] = diagnose_url(session, url, args.range_size)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            failures.append({"url": url, "error": str(exc)})
    report = {
        "diagnostic_scope": "HTTP transport only; not TIFF or scientific validation",
        "range_size_bytes": args.range_size, "results": results,
        "failures": failures, "overall_status": "PASS" if not failures else "FAIL",
    }
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1

if __name__ == "__main__":
    sys.exit(main())

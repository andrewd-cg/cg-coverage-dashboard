#!/usr/bin/env python3
"""
Reads a Chainguard Python build report CSV and appends the PyPI publish
date for each requirement as a new column.

Usage: python add_pypi_dates.py <input.csv> [output.csv]

Output defaults to <input>-with-pypi-dates.csv if not specified.
"""

import argparse
import asyncio
import csv
import os
import sys
from collections import Counter

import aiohttp
from tqdm import tqdm

PYPI_URL = "https://pypi.org/pypi/{package}/{version}/json"
CONCURRENCY = 30
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2.0


def parse_requirement(req: str) -> tuple:
    """Split 'package==version' into (package, version), or (None, None)."""
    if "==" in req:
        package, version = req.split("==", 1)
        return package.strip(), version.strip()
    return None, None


async def fetch_pypi_date(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    package: str,
    version: str,
) -> str:
    url = PYPI_URL.format(package=package, version=version)
    for attempt in range(RETRY_ATTEMPTS):
        try:
            async with semaphore:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        urls = data.get("urls", [])
                        if urls:
                            ts = urls[0].get("upload_time_iso_8601") or urls[0].get("upload_time", "")
                            if ts:
                                return ts[:10]
                        releases = data.get("releases", {}).get(version, [])
                        if releases:
                            ts = releases[0].get("upload_time_iso_8601") or releases[0].get("upload_time", "")
                            if ts:
                                return ts[:10]
                        return "unknown"
                    elif resp.status == 404:
                        return "not_found"
                    elif resp.status == 429 or resp.status >= 500:
                        if attempt < RETRY_ATTEMPTS - 1:
                            await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                            continue
                        return f"error_{resp.status}"
                    else:
                        return f"error_{resp.status}"
        except asyncio.TimeoutError:
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                return "timeout"
        except Exception as exc:
            if attempt < RETRY_ATTEMPTS - 1:
                await asyncio.sleep(RETRY_DELAY)
            else:
                return f"error:{type(exc).__name__}"
    return "failed"


async def main(input_file: str, output_file: str):
    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found.", file=sys.stderr)
        sys.exit(1)

    with open(input_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    print(f"Loaded {len(rows):,} rows from {input_file}")

    results = [None] * len(rows)
    progress = tqdm(total=len(rows), unit="pkg", desc="Fetching PyPI dates")

    connector = aiohttp.TCPConnector(limit=CONCURRENCY, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(CONCURRENCY)

        async def fetch_one(i: int, row: dict):
            package, version = parse_requirement(row.get("Requirement", ""))
            if package and version:
                result = await fetch_pypi_date(session, semaphore, package, version)
            else:
                result = "invalid_requirement"
            results[i] = result
            progress.update(1)

        await asyncio.gather(*(fetch_one(i, row) for i, row in enumerate(rows)))

    progress.close()

    new_fieldnames = fieldnames + ["PyPI Published"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        for row, pypi_date in zip(rows, results):
            row["PyPI Published"] = pypi_date
            writer.writerow(row)

    print(f"\nWrote {len(rows):,} rows to {output_file}")

    counts = Counter(results)
    errors = sum(v for k, v in counts.items() if k not in ("not_found", "unknown") and not (k[:4].isdigit()))
    dated = sum(v for k, v in counts.items() if len(k) == 10 and k[4] == "-")
    print(f"  Dated:     {dated:,}")
    print(f"  Not found: {counts['not_found']:,}")
    print(f"  Unknown:   {counts['unknown']:,}")
    print(f"  Errors:    {errors:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich a Chainguard build report CSV with PyPI publish dates.")
    parser.add_argument("input", help="Path to the input CSV file")
    parser.add_argument("output", nargs="?", help="Path to the output CSV file (default: <input>-with-pypi-dates.csv)")
    args = parser.parse_args()

    input_file = args.input
    output_file = args.output or input_file.removesuffix(".csv") + "-with-pypi-dates.csv"

    asyncio.run(main(input_file, output_file))

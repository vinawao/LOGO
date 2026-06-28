#!/usr/bin/env python3
"""
m3u_scraper.py

Usage examples:
  python m3u_scraper.py --source "https://example.com/playlist.m3u" --output out.json --format json --check --concurrency 30
  python m3u_scraper.py --source "./playlist.m3u" --output out.csv --format csv --filter-group "News"
"""

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
except Exception:
    aiohttp = None

import urllib.request
from urllib.parse import urlparse

EXTINF_RE = re.compile(r'^#EXTINF:(?P<duration>-?\d+)\s*(?P<attrs>.*?),(?P<title>.*)$')
ATTR_RE = re.compile(r'(?P<key>[A-Za-z0-9\-_]+)=\"(?P<value>.*?)\"')


def load_source(source: str) -> str:
    """
    Load playlist content from a URL or local file path.
    """
    parsed = urlparse(source)
    if parsed.scheme in ('http', 'https'):
        with urllib.request.urlopen(source, timeout=30) as resp:
            return resp.read().decode(errors='replace')
    else:
        with open(source, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()


def parse_m3u(content: str) -> List[Dict]:
    """
    Parse M3U content into a list of entries.
    Each entry: {duration, title, attrs(dict), url}
    """
    lines = [ln.strip() for ln in content.splitlines()]
    entries = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('#EXTINF'):
            m = EXTINF_RE.match(ln)
            if not m:
                # fallback: try to find comma-separated title at the end
                try:
                    duration_part, rest = ln.split(':', 1)[1].split(',', 1)
                    duration = duration_part.strip()
                    attrs_part, title = rest.rsplit(',', 1)
                    attrs_str = attrs_part.strip()
                except Exception:
                    duration = '-1'
                    attrs_str = ''
                    title = ln
            else:
                duration = m.group('duration')
                attrs_str = m.group('attrs') or ''
                title = m.group('title') or ''

            attrs = {km.group('key'): km.group('value') for km in ATTR_RE.finditer(attrs_str)}
            # The stream URL is the next non-empty non-comment line
            url = None
            j = i + 1
            while j < len(lines):
                candidate = lines[j]
                if candidate == '' or candidate.startswith('#'):
                    j += 1
                    continue
                url = candidate
                break
            entries.append({
                'duration': int(duration) if duration.lstrip('-').isdigit() else None,
                'title': title.strip(),
                'attrs': attrs,
                'url': url,
                'raw_extinf': ln,
            })
            i = j if j is not None else i + 1
        else:
            i += 1
    return entries


async def check_streams_async(entries: List[Dict], concurrency: int = 20, timeout: int = 8) -> None:
    """
    Check the HTTP status and response time of each entry's URL, updating entry in place.
    Uses aiohttp if available.
    """
    if aiohttp is None:
        raise RuntimeError("aiohttp is required for async checking. Install with: pip install aiohttp")

    sem = asyncio.Semaphore(concurrency)

    async def check_one(session: aiohttp.ClientSession, entry: Dict):
        url = entry.get('url')
        if not url:
            entry.update({'alive': False, 'status': None, 'latency_ms': None})
            return
        async with sem:
            start = time.perf_counter()
            try:
                # Try HEAD first; if it fails or returns 405, try GET with small range / stream read
                async with session.head(url, allow_redirects=True, timeout=timeout) as resp:
                    status = resp.status
                    end = time.perf_counter()
                    entry.update({'alive': 200 <= status < 400, 'status': status, 'latency_ms': int((end - start) * 1000)})
                    return
            except aiohttp.ClientResponseError as e:
                status = getattr(e, 'status', None)
                # fall through to GET trial
            except Exception:
                status = None

            # Fallback GET attempt
            try:
                headers = {'Range': 'bytes=0-1023'}
                start = time.perf_counter()
                async with session.get(url, headers=headers, allow_redirects=True, timeout=timeout) as resp:
                    status = resp.status
                    end = time.perf_counter()
                    entry.update({'alive': 200 <= status < 400, 'status': status, 'latency_ms': int((end - start) * 1000)})
            except Exception:
                entry.update({'alive': False, 'status': status, 'latency_ms': None})

    timeout_obj = aiohttp.ClientTimeout(total=None, sock_connect=timeout, sock_read=timeout)
    async with aiohttp.ClientSession(timeout=timeout_obj) as session:
        tasks = [asyncio.create_task(check_one(session, e)) for e in entries]
        # progress-aware gather
        for t in asyncio.as_completed(tasks):
            await t


def check_streams_sync(entries: List[Dict], timeout: int = 8) -> None:
    """
    Synchronous check using urllib.request (less reliable for some streams).
    Updates entries in-place.
    """
    for entry in entries:
        url = entry.get('url')
        if not url:
            entry.update({'alive': False, 'status': None, 'latency_ms': None})
            continue
        start = time.perf_counter()
        req = urllib.request.Request(url, method='HEAD')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.getcode()
                end = time.perf_counter()
                entry.update({'alive': 200 <= status < 400, 'status': status, 'latency_ms': int((end - start) * 1000)})
                continue
        except Exception:
            # fallback GET small read
            try:
                req2 = urllib.request.Request(url, headers={'Range': 'bytes=0-1023'})
                start = time.perf_counter()
                with urllib.request.urlopen(req2, timeout=timeout) as resp2:
                    status = resp2.getcode()
                    end = time.perf_counter()
                    entry.update({'alive': 200 <= status < 400, 'status': status, 'latency_ms': int((end - start) * 1000)})
                    continue
            except Exception:
                entry.update({'alive': False, 'status': None, 'latency_ms': None})


def filter_entries(entries: List[Dict], filter_group: Optional[str], filter_title: Optional[str]) -> List[Dict]:
    if not filter_group and not filter_title:
        return entries
    out = []
    for e in entries:
        group = e.get('attrs', {}).get('group-title', '') or e.get('attrs', {}).get('group', '')
        title = e.get('title', '') or ''
        ok = True
        if filter_group:
            if filter_group.lower() not in group.lower():
                ok = False
        if filter_title:
            if filter_title.lower() not in title.lower():
                ok = False
        if ok:
            out.append(e)
    return out


def save_output(entries: List[Dict], path: str, fmt: str = 'json') -> None:
    if fmt == 'json':
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    elif fmt == 'csv':
        # flatten a few common fields
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            header = [
                'title', 'url', 'duration', 'status', 'alive', 'latency_ms'
            ]
            # include attr keys we commonly see
            extra_keys = set()
            for e in entries:
                extra_keys.update(e.get('attrs', {}).keys())
            extra_keys = sorted(extra_keys)
            header.extend(extra_keys)
            writer.writerow(header)
            for e in entries:
                row = [
                    e.get('title'),
                    e.get('url'),
                    e.get('duration'),
                    e.get('status'),
                    e.get('alive'),
                    e.get('latency_ms'),
                ]
                attrs = e.get('attrs', {})
                for k in extra_keys:
                    row.append(attrs.get(k))
                writer.writerow(row)
    else:
        raise ValueError('Unsupported format: ' + fmt)


def main():
    ap = argparse.ArgumentParser(description='M3U playlist scraper and stream checker')
    ap.add_argument('--source', '-s', required=True, help='URL or local path to M3U playlist')
    ap.add_argument('--output', '-o', required=False, help='Output file path (default: stdout for json)', default=None)
    ap.add_argument('--format', '-f', choices=['json', 'csv'], default='json', help='Output format')
    ap.add_argument('--check', action='store_true', help='Check each stream for availability (requires network)')
    ap.add_argument('--concurrency', '-c', type=int, default=20, help='Concurrent checks (async mode, default 20)')
    ap.add_argument('--timeout', type=int, default=8, help='Timeout seconds per stream check (default 8)')
    ap.add_argument('--filter-group', help='Filter by group-title substring (case-insensitive)')
    ap.add_argument('--filter-title', help='Filter by title substring (case-insensitive)')
    args = ap.parse_args()

    try:
        content = load_source(args.source)
    except Exception as e:
        print(f"Failed to load source: {e}", file=sys.stderr)
        sys.exit(2)

    entries = parse_m3u(content)
    print(f"Parsed {len(entries)} entries from playlist.", file=sys.stderr)

    entries = filter_entries(entries, args.filter_group, args.filter_title)
    print(f"{len(entries)} entries after filtering.", file=sys.stderr)

    if args.check:
        print("Checking streams...", file=sys.stderr)
        if aiohttp is not None:
            try:
                asyncio.run(check_streams_async(entries, concurrency=args.concurrency, timeout=args.timeout))
            except Exception as e:
                print(f"Async checking failed, falling back to sync: {e}", file=sys.stderr)
                check_streams_sync(entries, timeout=args.timeout)
        else:
            print("aiohttp not installed; using synchronous checks (slower).", file=sys.stderr)
            check_streams_sync(entries, timeout=args.timeout)

    # Prepare a tidy output (flatten attrs a bit)
    tidy = []
    for e in entries:
        d = {
            'title': e.get('title'),
            'url': e.get('url'),
            'duration': e.get('duration'),
            'status': e.get('status'),
            'alive': e.get('alive'),
            'latency_ms': e.get('latency_ms'),
            'attrs': e.get('attrs', {}),
        }
        tidy.append(d)

    if args.output:
        save_output(tidy, args.output, args.format)
        print(f"Saved output to {args.output}", file=sys.stderr)
    else:
        # print to stdout as json
        print(json.dumps(tidy, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

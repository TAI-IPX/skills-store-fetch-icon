#!/usr/bin/env python3
"""Fetch real App Store app icons at a chosen resolution.

Picks N distinct apps from a curated pool, resolves them through Apple's
public lookup API, and downloads their original (uncropped) square artwork.

Standard library only. No credentials, no third-party packages.
"""

import argparse
import json
import random
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POOL = SKILL_ROOT / "data" / "app_pool.json"
LOOKUP_ENDPOINT = "https://itunes.apple.com/lookup"
USER_AGENT = "skills-store-fetch-icon/1.0 (+https://itunes.apple.com)"
SIZES = ("256", "512", "1024")
LOOKUP_CHUNK = 50
RETRIES = 1


class PoolError(Exception):
    pass


def http_get(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def load_pool(path):
    if not path.exists():
        raise PoolError("app pool not found: %s" % path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PoolError("app pool is not valid JSON: %s (%s)" % (path, exc))

    entries = raw.get("apps") if isinstance(raw, dict) else raw
    if not isinstance(entries, list) or not entries:
        raise PoolError("app pool must be a non-empty list, or an object with an 'apps' array: %s" % path)

    normalized = []
    seen_ids = set()
    for position, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise PoolError("app pool entry #%d is not an object" % position)
        missing = [key for key in ("id", "name") if not entry.get(key)]
        if missing:
            raise PoolError("app pool entry #%d is missing %s" % (position, ", ".join(missing)))
        app_id = str(entry["id"]).strip()
        if app_id in seen_ids:
            raise PoolError("duplicate app id in pool: %s" % app_id)
        seen_ids.add(app_id)
        normalized.append(
            {
                "id": app_id,
                "name": str(entry["name"]).strip(),
                "desc": str(entry.get("desc") or "").strip(),
                "category": str(entry.get("category") or "other").strip(),
                "country": str(entry.get("country") or "cn").strip().lower(),
            }
        )
    return normalized


def lookup_apps(apps):
    """Resolve apps through the lookup API. Returns (found, missing_ids)."""
    by_country = {}
    for app in apps:
        by_country.setdefault(app["country"], []).append(app["id"])

    found = {}
    for country, ids in sorted(by_country.items()):
        for start in range(0, len(ids), LOOKUP_CHUNK):
            chunk = ids[start : start + LOOKUP_CHUNK]
            query = urllib.parse.urlencode({"id": ",".join(chunk), "country": country})
            last_error = None
            payload = None
            for attempt in range(RETRIES + 1):
                try:
                    payload = json.loads(http_get("%s?%s" % (LOOKUP_ENDPOINT, query)))
                    break
                except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt < RETRIES:
                        time.sleep(1.5)
            if payload is None:
                raise PoolError(
                    "lookup failed for country=%s (%d ids): %s" % (country, len(chunk), last_error)
                )
            for result in payload.get("results", []):
                track_id = result.get("trackId")
                if track_id is not None:
                    found[str(track_id)] = result

    missing = [app["id"] for app in apps if app["id"] not in found]
    return found, missing


def icon_url_candidates(result, size):
    artwork = result.get("artworkUrl512") or result.get("artworkUrl100")
    if not artwork:
        return []
    base = artwork.rsplit("/", 1)[0]
    candidates = [
        "%s/%sx%sbb.png" % (base, size, size),
        "%s/%sx%sbb.jpg" % (base, size, size),
        artwork,
    ]
    deduped = []
    for url in candidates:
        if url not in deduped:
            deduped.append(url)
    return deduped


def download_icon(result, size, destination_stem):
    """Download the first working artwork variant. Returns (path, url)."""
    errors = []
    for url in icon_url_candidates(result, size):
        extension = url.rsplit(".", 1)[-1].lower()
        if extension not in ("png", "jpg", "jpeg", "webp"):
            extension = "png"
        path = destination_stem.with_suffix("." + extension)
        try:
            body = http_get(url, timeout=45)
        except (urllib.error.URLError, OSError) as exc:
            errors.append("%s -> %s" % (url, exc))
            continue
        if not body:
            errors.append("%s -> empty response" % url)
            continue
        path.write_bytes(body)
        return path, url
    raise PoolError("all artwork variants failed for %s: %s" % (destination_stem.name, "; ".join(errors)))


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Download N real App Store app icons from a curated pool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--count", "-n", type=int, required=True, help="how many icons to fetch")
    parser.add_argument("--size", choices=SIZES, default="512", help="icon edge length in px (default: 512)")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: a fresh temp directory)")
    parser.add_argument("--pool", type=Path, default=None, help="app pool JSON (default: the bundled data/app_pool.json)")
    parser.add_argument("--seed", type=int, default=None, help="seed the random pick for reproducible batches")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.count < 1:
        print("error: --count must be at least 1", file=sys.stderr)
        return 2

    pool_path = args.pool if args.pool is not None else DEFAULT_POOL
    try:
        pool = load_pool(pool_path)
        resolved, missing = lookup_apps(pool)
        if missing:
            raise PoolError(
                "these app ids did not resolve on the App Store lookup API: %s\n"
                "Fix or remove them in %s (the pool is never silently trimmed)."
                % (", ".join(missing), pool_path)
            )
        if args.count > len(pool):
            raise PoolError(
                "requested %d icons but the pool only has %d apps (%s)"
                % (args.count, len(pool), pool_path)
            )

        rng = random.Random(args.seed)
        picked = rng.sample(pool, args.count)

        out_dir = args.out if args.out is not None else Path(tempfile.mkdtemp(prefix="app-icons-"))
        out_dir.mkdir(parents=True, exist_ok=True)

        items = []
        for index, app in enumerate(picked, start=1):
            stem = out_dir / ("%02d" % index)
            path, url = download_icon(resolved[app["id"]], args.size, stem)
            result = resolved[app["id"]]
            items.append(
                {
                    "index": index,
                    "file": path.name,
                    "app_id": app["id"],
                    "name": app["name"],
                    "desc": app["desc"],
                    "category": app["category"],
                    "country": app["country"],
                    "store_title": result.get("trackName"),
                    "source_url": url,
                }
            )

        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "size": int(args.size),
            "source": "Apple App Store lookup artwork (original uncropped square)",
            "items": items,
        }
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except PoolError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130

    for item in items:
        print("%02d  %-18s %s" % (item["index"], item["name"], item["file"]))
    print("")
    print("icons_dir: %s" % out_dir.resolve())
    print("manifest:  %s" % manifest_path.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())

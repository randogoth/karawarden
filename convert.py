#!/usr/bin/env python3
"""
Convert a Hoarder export into a structure that Linkwarden can import.

Example:
    python convert_hoarder_to_linkwarden.py hoarder_export.json -o linkwarden_import.json
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class LinkRecord:
    title: str
    url: str
    description: str
    tags: List[str]
    created_dt: datetime


DEFAULT_COLLECTION_NAME = "Hoarder Import"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Hoarder export JSON into Linkwarden's import format."
    )
    parser.add_argument(
        "hoarder_export",
        type=Path,
        help="Path to the Hoarder export JSON file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Where to write the transformed Linkwarden JSON file.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="Linkwarden user identifier to attach to collections and links.",
    )
    parser.add_argument(
        "--collection-color",
        default=None,
        help="Optional hex color (e.g. #0ea5e9) to assign to generated collections.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        sys.exit(f"Input file not found: {exc.filename}")
    except json.JSONDecodeError as exc:
        sys.exit(f"Invalid JSON in {path}: {exc}")


def parse_timestamp(value, *, default_dt: Optional[datetime] = None) -> Tuple[str, datetime]:
    if default_dt is None:
        default_dt = datetime.now(timezone.utc)

    if value is None:
        dt = default_dt
    else:
        dt = None
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            try:
                dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
            except (OverflowError, ValueError):
                dt = None
        if dt is None and isinstance(value, str):
            raw = value.strip()
            if raw:
                if raw.endswith("Z"):
                    raw = raw[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(raw)
                except ValueError:
                    dt = None
        if dt is None:
            dt = default_dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

    iso_value = dt.isoformat().replace("+00:00", "Z")
    return iso_value, dt


def normalise_tags(tags: Iterable) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for tag in tags or []:
        if not isinstance(tag, str):
            continue
        cleaned_tag = tag.strip()
        if not cleaned_tag:
            continue
        cleaned_tag = cleaned_tag.strip()
        if not cleaned_tag or cleaned_tag in seen:
            continue
        cleaned.append(cleaned_tag)
        seen.add(cleaned_tag)
    return cleaned


def collect_links(hoarder_data: Dict) -> OrderedDict[str, List[LinkRecord]]:
    try:
        bookmarks = hoarder_data["bookmarks"]
    except KeyError:
        sys.exit("The Hoarder export does not contain a 'bookmarks' key.")
    if not isinstance(bookmarks, list):
        sys.exit("'bookmarks' should be a list in the Hoarder export.")

    grouped: OrderedDict[str, List[LinkRecord]] = OrderedDict()
    now_dt = datetime.now(timezone.utc)

    for entry in reversed(bookmarks):
        content = entry.get("content") or {}
        if content.get("type") != "link":
            continue
        url = content.get("url")
        if not url:
            continue

        title = entry.get("title") or url
        description = entry.get("note") or ""
        tags = normalise_tags(entry.get("tags") or [])
        _, created_dt = parse_timestamp(entry.get("createdAt"), default_dt=now_dt)

        collection_name = DEFAULT_COLLECTION_NAME

        grouped.setdefault(collection_name, [])
        grouped[collection_name].append(
            LinkRecord(
                title=title,
                url=url,
                description=description,
                tags=tags,
                created_dt=created_dt,
            )
        )

    return grouped


def load_base_payload(*, user_id: int) -> Dict:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "name": "",
        "username": "",
        "email": None,
        "emailVerified": None,
        "unverifiedNewEmail": None,
        "image": None,
        "locale": "en",
        "parentSubscriptionId": None,
        "collectionOrder": [],
        "linksRouteTo": "ORIGINAL",
        "aiTaggingMethod": "DISABLED",
        "aiPredefinedTags": [],
        "aiTagExistingLinks": False,
        "theme": "dark",
        "readableFontFamily": "sans-serif",
        "readableFontSize": "18px",
        "readableLineHeight": "1.6",
        "readableLineWidth": "normal",
        "preventDuplicateLinks": False,
        "archiveAsScreenshot": True,
        "archiveAsMonolith": True,
        "archiveAsPDF": True,
        "archiveAsReadable": True,
        "archiveAsWaybackMachine": False,
        "isPrivate": False,
        "referredBy": None,
        "lastPickedAt": now_iso,
        "acceptPromotionalEmails": False,
        "trialEndEmailSent": False,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "collections": [],
        "pinnedLinks": [],
        "whitelistedUsers": [],
    }


def build_linkwarden_payload(
    grouped_links: OrderedDict[str, List[LinkRecord]],
    *,
    user_id: int,
    collection_color: Optional[str],
    base_payload: Dict,
) -> Dict:
    payload = copy.deepcopy(base_payload)

    collections = []
    link_id = 1
    collection_id = 1

    for collection_name, link_records in grouped_links.items():
        if not link_records:
            continue

        earliest_dt = min(record.created_dt for record in link_records)
        collection_created_iso = earliest_dt.isoformat().replace("+00:00", "Z")

        links_payload = []
        for record in link_records:
            created_iso = record.created_dt.isoformat().replace("+00:00", "Z")
            link_payload = {
                "id": link_id,
                "name": record.title,
                "type": "url",
                "description": record.description,
                "createdById": user_id,
                "collectionId": collection_id,
                "icon": None,
                "iconWeight": None,
                "color": None,
                "url": record.url,
                "clientSide": False,
                "aiTagged": False,
                "indexVersion": None,
                "lastPreserved": None,
                "importDate": created_iso,
                "createdAt": created_iso,
                "updatedAt": created_iso,
                "tags": [{"name": tag} for tag in record.tags],
            }
            links_payload.append(link_payload)
            link_id += 1

        collection_payload = {
            "id": collection_id,
            "name": collection_name,
            "description": "",
            "icon": None,
            "iconWeight": None,
            "color": collection_color,
            "parentId": None,
            "isPublic": False,
            "ownerId": user_id,
            "createdById": user_id,
            "createdAt": collection_created_iso,
            "updatedAt": collection_created_iso,
            "rssSubscriptions": [],
            "links": links_payload,
        }
        collections.append(collection_payload)
        collection_id += 1

    payload["collections"] = collections
    payload.setdefault("pinnedLinks", [])
    payload.setdefault("whitelistedUsers", [])
    return payload


def main() -> None:
    args = parse_args()

    hoarder_data = load_json(args.hoarder_export)
    grouped_links = collect_links(hoarder_data)

    if not grouped_links:
        sys.exit("No link-type bookmarks were found in the Hoarder export.")

    base_payload = load_base_payload(user_id=args.user_id)

    payload = build_linkwarden_payload(
        grouped_links,
        user_id=args.user_id,
        collection_color=args.collection_color,
        base_payload=base_payload,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)

    total_links = sum(len(records) for records in grouped_links.values())
    print(
        f"Converted {total_links} bookmarks into {len(payload['collections'])} "
        f"Linkwarden collection(s) -> {args.output}"
    )


if __name__ == "__main__":
    main()

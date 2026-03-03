#!/usr/bin/env python3
"""Regression tests for catalog filter behavior used by the static site."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "site" / "catalog.json"


def load_catalog() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def flatten_items(catalog: dict) -> list[dict]:
    items: list[dict] = []
    for section in catalog["sections"]:
        for subsection in section["subsections"]:
            items.extend(subsection["items"])
    return items


def item_matches_filter(item: dict, source_filter: str) -> bool:
    badges = item.get("sourceBadges", [])
    has_official = "official" in badges
    has_community = "community" in badges

    if source_filter == "official":
        return has_official and not has_community
    if source_filter == "community":
        return has_community and not has_official
    if source_filter == "both":
        return has_official or has_community
    return True


def item_matches_query(item: dict, query: str) -> bool:
    if not query:
        return True

    haystack = " ".join(
        str(item.get(field, "")).lower()
        for field in ("name", "description", "author", "section", "subsection")
    )
    return query.lower() in haystack


def item_matches_categories(item: dict, categories: list[str]) -> bool:
    if not categories:
        return True
    return item.get("section") in categories


def search_names(
    *,
    query: str = "",
    source_filter: str = "all",
    categories: list[str] | None = None,
) -> list[str]:
    catalog = load_catalog()
    categories = categories or []

    results = []
    for item in flatten_items(catalog):
        if (
            item_matches_filter(item, source_filter)
            and item_matches_query(item, query)
            and item_matches_categories(item, categories)
        ):
            results.append(item["name"])
    return results


class SiteFilterRegressionTests(unittest.TestCase):
    def test_source_both_treats_both_as_union(self) -> None:
        names = search_names(query="123", source_filter="both", categories=["Games"])
        self.assertIn("123DiceDnD", names)

    def test_source_both_includes_official_only_items(self) -> None:
        names = search_names(query="2048", source_filter="both", categories=["Games"])
        self.assertIn("2048", names)

    def test_source_community_keeps_community_only_items(self) -> None:
        names = search_names(query="123", source_filter="community", categories=["Games"])
        self.assertIn("123DiceDnD", names)

    def test_source_community_excludes_official_only_items(self) -> None:
        names = search_names(query="2048", source_filter="community", categories=["Games"])
        self.assertNotIn("2048", names)


if __name__ == "__main__":
    unittest.main()

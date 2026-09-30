#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import os
import re
import time
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://it.wikipedia.org/w/api.php"
DEFAULT_USER_AGENT = (
    "ItalianColonialToponymyResearch/0.2 "
    "(academic research; set WIKIMEDIA_USER_AGENT to include contact information)"
)


def build_session(user_agent: str) -> requests.Session:
    retry = Retry(
        total=6,
        connect=3,
        read=3,
        status=6,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept": "application/json", "Accept-Encoding": "gzip, deflate"})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def api_get(session: requests.Session, params: dict[str, Any], *, max_attempts: int = 5) -> dict[str, Any]:
    request_params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
    for attempt in range(1, max_attempts + 1):
        response = session.get(API, params=request_params, timeout=(15, 60))
        if response.status_code != 200:
            preview = response.text[:500].replace("\n", " ").strip()
            raise RuntimeError(
                "Wikipedia API request failed after HTTP retries.\n"
                f"HTTP status: {response.status_code}\n"
                f"Content-Type: {response.headers.get('Content-Type', '<missing>')}\n"
                f"URL: {response.url}\n"
                f"Response preview: {preview!r}\n"
                "If the status is 403/429, set WIKIMEDIA_USER_AGENT to a descriptive value containing a contact URL or email."
            )
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            preview = response.text[:500].replace("\n", " ").strip()
            raise RuntimeError(
                "Wikipedia returned a non-JSON response.\n"
                f"HTTP status: {response.status_code}\n"
                f"Content-Type: {response.headers.get('Content-Type', '<missing>')}\n"
                f"URL: {response.url}\n"
                f"Response preview: {preview!r}"
            ) from exc
        error = data.get("error")
        if not error:
            return data
        if error.get("code") == "maxlag" and attempt < max_attempts:
            wait = min(2 ** (attempt - 1), 16)
            print(f"Wikipedia reports high server lag; retrying in {wait}s...")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Wikipedia API returned an error: {error.get('code', 'unknown')}: {error.get('info', error)}")
    raise RuntimeError("Wikipedia API request failed after repeated maxlag responses.")


def search_wikipedia(session: requests.Session, query: str, limit: int = 50) -> Iterator[dict[str, str]]:
    params = {"action": "query", "list": "search", "srsearch": query, "srnamespace": 0, "srlimit": limit}
    data = api_get(session, params)
    for item in data.get("query", {}).get("search", []):
        yield {
            "title": item["title"],
            "snippet": re.sub(r"<[^>]+>", "", html.unescape(item.get("snippet", ""))),
            "source_kind": "search",
            "source_query": query,
        }


def category_members(session: requests.Session, category: str, limit: int = 500) -> Iterator[dict[str, str]]:
    continuation: str | None = None
    n = 0
    while n < limit:
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Categoria:{category}",
            "cmnamespace": 0,
            "cmlimit": min(500, limit - n),
        }
        if continuation:
            params["cmcontinue"] = continuation
        data = api_get(session, params)
        members = data.get("query", {}).get("categorymembers", [])
        if not members:
            break
        for item in members:
            yield {"title": item["title"], "snippet": "", "source_kind": "category", "source_query": category}
            n += 1
        continuation = data.get("continue", {}).get("cmcontinue")
        if not continuation:
            break


def page_metadata(session: requests.Session, titles: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for start in range(0, len(titles), 40):
        batch = titles[start : start + 40]
        params = {"action": "query", "prop": "pageprops|extracts", "exintro": 1, "explaintext": 1, "titles": "|".join(batch)}
        data = api_get(session, params)
        for page in data.get("query", {}).get("pages", []):
            title = page.get("title", "")
            out[title] = {
                "wikidata_qid": page.get("pageprops", {}).get("wikibase_item", ""),
                "intro": page.get("extract", "")[:1200],
            }
        time.sleep(0.2)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover candidate people from Wikipedia. This produces candidates, not a verified registry.")
    parser.add_argument("--config", default="config/sources.yml")
    parser.add_argument("--output", default="data/candidates/wikipedia_candidates.csv")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("WIKIMEDIA_USER_AGENT", DEFAULT_USER_AGENT),
        help="HTTP User-Agent sent to Wikimedia. Prefer a descriptive value with contact information. Can also be set with WIKIMEDIA_USER_AGENT.",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    session = build_session(args.user_agent)
    rows: list[dict[str, str]] = []
    for query in cfg["wikipedia"].get("search_queries", []):
        print(f"Search: {query}")
        rows.extend(search_wikipedia(session, query))
        time.sleep(0.3)
    for category in cfg["wikipedia"].get("categories", []):
        print(f"Category: {category}")
        rows.extend(category_members(session, category))
        time.sleep(0.3)
    if not rows:
        print("No candidates found.")
        return
    df = pd.DataFrame(rows).drop_duplicates(["title", "source_kind", "source_query"])
    meta = page_metadata(session, sorted(df["title"].unique()))
    df["wikidata_qid"] = df["title"].map(lambda x: meta.get(x, {}).get("wikidata_qid", ""))
    df["intro"] = df["title"].map(lambda x: meta.get(x, {}).get("intro", ""))
    df["wikipedia_url"] = "https://it.wikipedia.org/wiki/" + df["title"].str.replace(" ", "_", regex=False)
    df["review_status"] = "candidate_unreviewed"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    print(f"Wrote {len(df)} candidate rows to {output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "typer",
#     "httpx",
# ]
# ///
"""Hacker News CLI - browse, search, and explore HN from the terminal."""

from __future__ import annotations

import html
import json as json_lib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Optional

import httpx
import typer

app = typer.Typer(help="Hacker News CLI", no_args_is_help=True)

HN_API = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_API = "https://hn.algolia.com/api/v1"


# --- Helpers ---


def relative_time(ts: int) -> str:
    """Convert unix timestamp to relative time string."""
    diff = int(time.time()) - ts
    if diff < 60:
        return f"{diff}s ago"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    if diff < 2592000:
        return f"{diff // 86400}d ago"
    if diff < 31536000:
        return f"{diff // 2592000}mo ago"
    return f"{diff // 31536000}y ago"


def html_to_text(s: str) -> str:
    """Convert HTML to plain text."""
    text = re.sub(r"<br\s*/?>", "\n", s)
    text = re.sub(r"<p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_item(item_id: int, client: httpx.Client | None = None) -> dict | None:
    """Fetch a single HN item by ID."""
    if client:
        r = client.get(f"{HN_API}/item/{item_id}.json")
    else:
        r = httpx.get(f"{HN_API}/item/{item_id}.json")
    if r.status_code == 200 and r.text != "null":
        return r.json()
    return None


def fetch_items_parallel(ids: list[int]) -> list[dict]:
    """Fetch multiple items in parallel."""
    results: dict[int, dict] = {}
    with httpx.Client() as client:
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(fetch_item, item_id, client): item_id for item_id in ids
            }
            for future in as_completed(futures):
                item_id = futures[future]
                result = future.result()
                if result:
                    results[item_id] = result
    return [results[i] for i in ids if i in results]


def fetch_story_ids(endpoint: str) -> list[int]:
    """Fetch story IDs from an HN endpoint."""
    r = httpx.get(f"{HN_API}/{endpoint}.json")
    r.raise_for_status()
    return r.json()


def print_stories(items: list[dict], as_json: bool = False) -> None:
    """Print a list of stories."""
    if as_json:
        typer.echo(json_lib.dumps(items, indent=2))
        return
    for idx, item in enumerate(items, 1):
        title = item.get("title", "untitled")
        score = item.get("score", 0)
        by = item.get("by", "unknown")
        comments = item.get("descendants", 0)
        url = item.get("url", "")
        ts = item.get("time", 0)
        item_type = item.get("type", "story")
        age = relative_time(ts)

        typer.echo(f"{idx:2d}. [{score} pts] {title}")
        if item_type == "job":
            typer.echo(f"    by {by} | {age}")
        else:
            typer.echo(f"    by {by} | {comments} comments | {age}")
        if url:
            typer.echo(f"    {url}")
        typer.echo()


def _stories_command(endpoint: str, limit: int, json: bool) -> None:
    """Shared logic for story list commands."""
    ids = fetch_story_ids(endpoint)[:limit]
    items = fetch_items_parallel(ids)
    print_stories(items, as_json=json)


# --- Commands ---

LimitOption = Annotated[int, typer.Option("--limit", "-n", help="Number of items")]
JsonOption = Annotated[bool, typer.Option("--json", help="Output raw JSON")]


@app.command()
def top(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Top/trending stories."""
    _stories_command("topstories", limit, json)


@app.command()
def new(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Newest stories."""
    _stories_command("newstories", limit, json)


@app.command()
def best(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Highest rated stories."""
    _stories_command("beststories", limit, json)


@app.command()
def ask(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Ask HN stories."""
    _stories_command("askstories", limit, json)


@app.command()
def show(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Show HN stories."""
    _stories_command("showstories", limit, json)


@app.command()
def jobs(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Job postings."""
    _stories_command("jobstories", limit, json)


@app.command()
def item(
    item_id: Annotated[int, typer.Argument(help="HN item ID")],
    json: JsonOption = False,
) -> None:
    """View full item details (story, comment, job, poll)."""
    data = fetch_item(item_id)
    if not data:
        typer.echo(f"Item {item_id} not found.")
        raise typer.Exit(1)

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    item_type = data.get("type", "unknown")
    title = data.get("title", "")
    score = data.get("score", 0)
    by = data.get("by", "unknown")
    ts = data.get("time", 0)
    url = data.get("url", "")
    text = data.get("text", "")
    descendants = data.get("descendants", 0)
    kids = data.get("kids", [])
    age = relative_time(ts)

    typer.echo(f"[{item_type}] {title or f'Item {item_id}'}")
    typer.echo(
        f"by {by} | {score} pts | {descendants} comments ({len(kids)} direct) | {age}"
    )
    if url:
        typer.echo(f"URL: {url}")
    if text:
        typer.echo()
        typer.echo(html_to_text(text))


@app.command()
def comments(
    item_id: Annotated[int, typer.Argument(help="HN item ID")],
    limit: LimitOption = 5,
    depth: Annotated[int, typer.Option("--depth", "-d", help="Reply depth")] = 1,
    json: JsonOption = False,
) -> None:
    """View top comments on a story."""
    data = fetch_item(item_id)
    if not data:
        typer.echo(f"Item {item_id} not found.")
        raise typer.Exit(1)

    kid_ids = data.get("kids", [])[:limit]
    if not kid_ids:
        typer.echo("No comments found.")
        return

    all_comments = fetch_items_parallel(kid_ids)

    if json:
        typer.echo(json_lib.dumps(all_comments, indent=2))
        return

    _print_comments(all_comments, limit, depth, current_depth=0)


def _print_comments(
    items: list[dict], limit: int, max_depth: int, current_depth: int
) -> None:
    """Recursively print comments with indentation."""
    indent = "  " * current_depth
    for c in items:
        if c.get("deleted") or c.get("dead"):
            continue
        by = c.get("by", "unknown")
        text = c.get("text", "")
        ts = c.get("time", 0)
        kids = c.get("kids", [])
        age = relative_time(ts)

        typer.echo(f"{indent}> {by} ({age}, {len(kids)} replies)")
        if text:
            for line in html_to_text(text).splitlines():
                typer.echo(f"{indent}  {line}")
        typer.echo()

        if current_depth + 1 < max_depth and kids:
            child_items = fetch_items_parallel(kids[:limit])
            _print_comments(child_items, limit, max_depth, current_depth + 1)


@app.command()
def user(
    username: Annotated[str, typer.Argument(help="HN username")],
    json: JsonOption = False,
) -> None:
    """View user profile."""
    r = httpx.get(f"{HN_API}/user/{username}.json")
    if r.status_code != 200 or r.text == "null":
        typer.echo(f"User '{username}' not found.")
        raise typer.Exit(1)

    data = r.json()

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    karma = data.get("karma", 0)
    created = data.get("created", 0)
    about = data.get("about", "")
    submitted = data.get("submitted", [])
    age = relative_time(created)

    typer.echo(f"User: {username}")
    typer.echo(f"Karma: {karma} | Joined: {age} | Submissions: {len(submitted)}")
    if about:
        typer.echo()
        typer.echo(html_to_text(about))

    if submitted:
        typer.echo()
        typer.echo("Recent activity:")
        recent = fetch_items_parallel(submitted[:5])
        for r_item in recent:
            r_type = r_item.get("type", "unknown")
            r_title = r_item.get("title", "")
            r_time = r_item.get("time", 0)
            r_age = relative_time(r_time)
            if r_title:
                typer.echo(f"  [{r_type}] {r_title} ({r_age})")
            else:
                typer.echo(f"  [{r_type}] id:{r_item.get('id')} ({r_age})")


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: LimitOption = 10,
    sort: Annotated[str, typer.Option(help="Sort: relevance or date")] = "relevance",
    type: Annotated[
        Optional[str], typer.Option(help="Filter: story or comment")
    ] = None,
    period: Annotated[
        Optional[str], typer.Option(help="Time period: day, week, month, year")
    ] = None,
    json: JsonOption = False,
) -> None:
    """Search HN stories and comments via Algolia."""
    endpoint = "search_by_date" if sort == "date" else "search"
    params: dict[str, str | int] = {"query": query, "hitsPerPage": limit}

    if type:
        params["tags"] = type

    if period:
        now = int(time.time())
        period_map = {
            "day": 86400,
            "week": 604800,
            "month": 2592000,
            "year": 31536000,
        }
        seconds = period_map.get(period)
        if seconds:
            params["numericFilters"] = f"created_at_i>{now - seconds}"

    r = httpx.get(f"{ALGOLIA_API}/{endpoint}", params=params)
    r.raise_for_status()
    data = r.json()

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    total = data.get("nbHits", 0)
    typer.echo(f'Search: "{query}" - {total} results\n')

    for hit in data.get("hits", []):
        title = hit.get("title") or hit.get("story_title") or ""
        author = hit.get("author", "unknown")
        points = hit.get("points", 0)
        num_comments = hit.get("num_comments", 0)
        url = hit.get("url", "")
        created_at = hit.get("created_at", "")
        date_str = created_at.split("T")[0] if created_at else ""

        if title:
            typer.echo(f"  [{points} pts] {title}")
            typer.echo(f"    by {author} | {num_comments} comments | {date_str}")
            if url:
                typer.echo(f"    {url}")
        else:
            comment_text = hit.get("comment_text") or hit.get("story_text") or ""
            snippet = html_to_text(comment_text)[:120]
            typer.echo(f"  {author}: {snippet}")
            typer.echo(f"    {date_str}")
        typer.echo()


@app.command()
def whoishiring(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Latest 'Who is hiring?' job postings."""
    r = httpx.get(
        f"{ALGOLIA_API}/search_by_date",
        params={
            "query": "who is hiring",
            "tags": "story,author_whoishiring",
            "hitsPerPage": 1,
        },
    )
    r.raise_for_status()
    hits = r.json().get("hits", [])
    if not hits:
        typer.echo("Could not find a 'Who is hiring?' thread.")
        raise typer.Exit(1)

    thread_id = int(hits[0]["objectID"])
    thread_title = hits[0].get("title", "Who is hiring?")

    thread = fetch_item(thread_id)
    if not thread:
        typer.echo("Could not fetch thread.")
        raise typer.Exit(1)

    kid_ids = thread.get("kids", [])[:limit]
    if not kid_ids:
        typer.echo("No job postings found.")
        return

    postings = fetch_items_parallel(kid_ids)

    if json:
        typer.echo(json_lib.dumps(postings, indent=2))
        return

    typer.echo(f"{thread_title}")
    typer.echo(f"https://news.ycombinator.com/item?id={thread_id}\n")

    for idx, posting in enumerate(postings, 1):
        if posting.get("deleted") or posting.get("dead"):
            continue
        by = posting.get("by", "unknown")
        text = posting.get("text", "")
        ts = posting.get("time", 0)
        age = relative_time(ts)
        first_line = html_to_text(text).split("\n")[0][:120] if text else ""

        typer.echo(f"{idx:2d}. {by} ({age})")
        typer.echo(f"    {first_line}")
        typer.echo()


if __name__ == "__main__":
    app()

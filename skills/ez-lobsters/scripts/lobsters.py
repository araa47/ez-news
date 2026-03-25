#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "typer",
#     "httpx",
# ]
# ///
"""Lobste.rs CLI - browse and search Lobsters from the terminal."""

from __future__ import annotations

import html
import json as json_lib
import re
from typing import Annotated

import httpx
import typer

app = typer.Typer(help="Lobste.rs CLI", no_args_is_help=True)

LOBSTERS_API = "https://lobste.rs"


# --- Helpers ---


def relative_time(ts_str: str) -> str:
    """Convert ISO 8601 timestamp to relative time string."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        diff = int((datetime.now(timezone.utc) - dt).total_seconds())
    except (ValueError, AttributeError):
        return ts_str
    if diff < 0:
        return "just now"
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


def fetch_stories(endpoint: str, limit: int) -> list[dict]:
    """Fetch stories from a Lobste.rs JSON endpoint."""
    r = httpx.get(f"{LOBSTERS_API}/{endpoint}", headers={"Accept": "application/json"})
    r.raise_for_status()
    stories = r.json()
    return stories[:limit]


def fetch_story(short_id: str) -> dict | None:
    """Fetch a single story by short ID."""
    r = httpx.get(f"{LOBSTERS_API}/s/{short_id}.json")
    if r.status_code == 200:
        return r.json()
    return None


def print_stories(items: list[dict], as_json: bool = False) -> None:
    """Print a list of stories."""
    if as_json:
        typer.echo(json_lib.dumps(items, indent=2))
        return
    for idx, item in enumerate(items, 1):
        title = item.get("title", "untitled")
        score = item.get("score", 0)
        by = item.get("submitter_user", {})
        username = by.get("username", "unknown") if isinstance(by, dict) else str(by)
        comments_count = item.get("comment_count", 0)
        url = item.get("url", "")
        tags = item.get("tags", [])
        created = item.get("created_at", "")
        age = relative_time(created)
        tag_str = ", ".join(tags) if tags else ""

        typer.echo(f"{idx:2d}. [{score} pts] {title}")
        typer.echo(f"    by {username} | {comments_count} comments | {age}")
        if tag_str:
            typer.echo(f"    tags: {tag_str}")
        if url:
            typer.echo(f"    {url}")
        typer.echo()


def print_comments(
    comments: list[dict], max_depth: int, current_depth: int = 0
) -> None:
    """Recursively print comments with indentation."""
    indent = "  " * current_depth
    for c in comments:
        by = c.get("commenting_user", {})
        username = by.get("username", "unknown") if isinstance(by, dict) else str(by)
        text = c.get("comment", c.get("comment_plain", ""))
        created = c.get("created_at", "")
        age = relative_time(created)
        score = c.get("score", 0)
        replies = c.get("comments", [])

        typer.echo(
            f"{indent}> {username} [{score} pts] ({age}, {len(replies)} replies)"
        )
        if text:
            plain = html_to_text(text)
            for line in plain.splitlines():
                typer.echo(f"{indent}  {line}")
        typer.echo()

        if current_depth + 1 < max_depth and replies:
            print_comments(replies, max_depth, current_depth + 1)


# --- Commands ---

LimitOption = Annotated[int, typer.Option("--limit", "-n", help="Number of items")]
JsonOption = Annotated[bool, typer.Option("--json", help="Output raw JSON")]


@app.command()
def hottest(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Hottest/trending stories."""
    items = fetch_stories("hottest.json", limit)
    print_stories(items, as_json=json)


@app.command()
def newest(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Newest stories."""
    items = fetch_stories("newest.json", limit)
    print_stories(items, as_json=json)


@app.command()
def tag(
    tag_name: Annotated[
        str, typer.Argument(help="Tag name (e.g. rust, python, security)")
    ],
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Stories by tag."""
    items = fetch_stories(f"t/{tag_name}.json", limit)
    print_stories(items, as_json=json)


@app.command()
def item(
    short_id: Annotated[str, typer.Argument(help="Story short ID")],
    json: JsonOption = False,
) -> None:
    """View full story details."""
    data = fetch_story(short_id)
    if not data:
        typer.echo(f"Story '{short_id}' not found.")
        raise typer.Exit(1)

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    title = data.get("title", "untitled")
    score = data.get("score", 0)
    by = data.get("submitter_user", {})
    username = by.get("username", "unknown") if isinstance(by, dict) else str(by)
    comments_count = data.get("comment_count", 0)
    url = data.get("url", "")
    tags = data.get("tags", [])
    created = data.get("created_at", "")
    description = data.get("description", "")
    age = relative_time(created)
    tag_str = ", ".join(tags) if tags else ""

    typer.echo(f"{title}")
    typer.echo(f"by {username} | {score} pts | {comments_count} comments | {age}")
    if tag_str:
        typer.echo(f"tags: {tag_str}")
    if url:
        typer.echo(f"URL: {url}")
    typer.echo(f"https://lobste.rs/s/{short_id}")
    if description:
        typer.echo()
        typer.echo(html_to_text(description))


@app.command()
def comments(
    short_id: Annotated[str, typer.Argument(help="Story short ID")],
    depth: Annotated[int, typer.Option("--depth", "-d", help="Reply depth")] = 2,
    json: JsonOption = False,
) -> None:
    """View comments on a story."""
    data = fetch_story(short_id)
    if not data:
        typer.echo(f"Story '{short_id}' not found.")
        raise typer.Exit(1)

    all_comments = data.get("comments", [])
    if not all_comments:
        typer.echo("No comments found.")
        return

    # Build tree: only show top-level comments (indent_level == 1 or no parent)
    top_level = [c for c in all_comments if c.get("indent_level", 1) == 1]

    if json:
        typer.echo(json_lib.dumps(all_comments, indent=2))
        return

    title = data.get("title", "")
    typer.echo(f"{title}")
    typer.echo(f"https://lobste.rs/s/{short_id}\n")
    print_comments(top_level, max_depth=depth)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Search stories."""
    params: dict[str, str | int] = {"q": query, "what": "stories", "order": "score"}
    r = httpx.get(f"{LOBSTERS_API}/search.json", params=params)
    r.raise_for_status()
    results = r.json()
    items = (
        results[:limit]
        if isinstance(results, list)
        else results.get("results", [])[:limit]
    )
    if not items:
        typer.echo(f'No results for "{query}".')
        return
    print_stories(items, as_json=json)


if __name__ == "__main__":
    app()

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "typer",
#     "httpx",
# ]
# ///
"""DEV.to CLI - browse and search DEV.to articles from the terminal."""

from __future__ import annotations

import json as json_lib
from typing import Annotated

import httpx
import typer

app = typer.Typer(help="DEV.to CLI", no_args_is_help=True)

DEVTO_API = "https://dev.to/api"


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


def devto_get(path: str, params: dict | None = None) -> httpx.Response:
    """Make a DEV.to API request."""
    r = httpx.get(f"{DEVTO_API}{path}", params=params, timeout=15)
    r.raise_for_status()
    return r


def print_articles(items: list[dict], as_json: bool = False) -> None:
    """Print a list of articles."""
    if as_json:
        typer.echo(json_lib.dumps(items, indent=2))
        return
    for idx, item in enumerate(items, 1):
        title = item.get("title", "untitled")
        user = item.get("user", {})
        username = (
            user.get("username", "unknown") if isinstance(user, dict) else "unknown"
        )
        reactions = item.get(
            "positive_reactions_count", item.get("public_reactions_count", 0)
        )
        comments_count = item.get("comments_count", 0)
        tags = item.get("tag_list", item.get("tags", []))
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        url = item.get("url", "")
        published = item.get("published_at", item.get("created_at", ""))
        reading_time = item.get("reading_time_minutes", 0)
        age = relative_time(published)
        tag_str = ", ".join(tags[:5]) if tags else ""

        typer.echo(f"{idx:2d}. [{reactions} reactions] {title}")
        typer.echo(
            f"    by {username} | {comments_count} comments | {reading_time} min read | {age}"
        )
        if tag_str:
            typer.echo(f"    tags: {tag_str}")
        if url:
            typer.echo(f"    {url}")
        typer.echo()


# --- Commands ---

LimitOption = Annotated[int, typer.Option("--limit", "-n", help="Number of items")]
JsonOption = Annotated[bool, typer.Option("--json", help="Output raw JSON")]


@app.command()
def top(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Top articles (by reactions)."""
    r = devto_get("/articles", params={"per_page": limit, "top": 7})
    print_articles(r.json(), as_json=json)


@app.command()
def latest(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Latest published articles."""
    r = devto_get("/articles/latest", params={"per_page": limit})
    print_articles(r.json(), as_json=json)


@app.command()
def rising(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Rising articles (recent with growing engagement)."""
    r = devto_get("/articles", params={"per_page": limit, "top": 1})
    print_articles(r.json(), as_json=json)


@app.command()
def tag(
    tag_name: Annotated[
        str, typer.Argument(help="Tag name (e.g. python, javascript, webdev)")
    ],
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Articles by tag."""
    r = devto_get("/articles", params={"tag": tag_name, "per_page": limit, "top": 7})
    print_articles(r.json(), as_json=json)


@app.command()
def article(
    article_id: Annotated[int, typer.Argument(help="Article ID")],
    json: JsonOption = False,
) -> None:
    """View full article details."""
    r = devto_get(f"/articles/{article_id}")
    data = r.json()

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    title = data.get("title", "untitled")
    user = data.get("user", {})
    username = user.get("username", "unknown") if isinstance(user, dict) else "unknown"
    reactions = data.get(
        "positive_reactions_count", data.get("public_reactions_count", 0)
    )
    comments_count = data.get("comments_count", 0)
    tags = data.get("tag_list", data.get("tags", []))
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    url = data.get("url", "")
    published = data.get("published_at", "")
    reading_time = data.get("reading_time_minutes", 0)
    body = data.get("body_markdown") or data.get("description") or ""
    age = relative_time(published)
    tag_str = ", ".join(tags[:5]) if tags else ""

    typer.echo(f"{title}")
    typer.echo(
        f"by {username} | {reactions} reactions | {comments_count} comments | {reading_time} min read | {age}"
    )
    if tag_str:
        typer.echo(f"tags: {tag_str}")
    if url:
        typer.echo(f"URL: {url}")
    if body:
        typer.echo()
        # Show first ~40 lines of body
        lines = body.strip().splitlines()[:40]
        for line in lines:
            typer.echo(line)
        if len(body.strip().splitlines()) > 40:
            typer.echo("\n... [truncated, view full article at URL above]")


@app.command()
def comments(
    article_id: Annotated[int, typer.Argument(help="Article ID")],
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """View comments on an article."""
    r = devto_get("/comments", params={"a_id": article_id, "per_page": limit})
    data = r.json()

    if not data:
        typer.echo("No comments found.")
        return

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    for _idx, comment in enumerate(data, 1):
        user = comment.get("user", {})
        username = (
            user.get("username", "unknown") if isinstance(user, dict) else "unknown"
        )
        body = comment.get("body_html", comment.get("body", ""))
        created = comment.get("created_at", "")
        age = relative_time(created)
        children = comment.get("children", [])

        # Strip HTML for plain text display
        import html as html_mod
        import re

        plain = re.sub(r"<[^>]+>", "", body)
        plain = html_mod.unescape(plain).strip()

        typer.echo(f"> {username} ({age}, {len(children)} replies)")
        for line in plain.splitlines()[:5]:
            typer.echo(f"  {line}")
        typer.echo()


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Search DEV.to articles."""
    r = devto_get("/articles", params={"per_page": limit, "tag": query})
    # DEV.to doesn't have a dedicated search endpoint in v0,
    # so we also try the Forem search approach
    results = r.json()
    if not results:
        # Fallback: try as general page param
        r = devto_get("/articles", params={"per_page": limit, "username": query})
        results = r.json()

    if not results:
        typer.echo(f'No results for "{query}".')
        return

    print_articles(results, as_json=json)


@app.command()
def tags(
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """List popular tags."""
    r = devto_get("/tags", params={"per_page": limit})
    data = r.json()

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    for idx, t in enumerate(data, 1):
        name = t.get("name", "unknown")
        count = (
            t.get("published_articles_count", 0)
            if "published_articles_count" in t
            else ""
        )
        typer.echo(f"{idx:2d}. #{name}" + (f" ({count} articles)" if count else ""))


if __name__ == "__main__":
    app()

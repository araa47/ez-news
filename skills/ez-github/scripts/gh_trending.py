#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "typer",
#     "httpx",
# ]
# ///
"""GitHub Trending CLI - discover trending repos, releases, and developers."""

from __future__ import annotations

import json as json_lib
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import httpx
import typer

app = typer.Typer(help="GitHub Trending CLI", no_args_is_help=True)

GH_API = "https://api.github.com"


# --- Helpers ---


def relative_time(ts_str: str) -> str:
    """Convert ISO 8601 timestamp to relative time string."""
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


def format_stars(n: int) -> str:
    """Format star count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def date_n_days_ago(days: int) -> str:
    """Return ISO date string N days ago."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def gh_get(path: str, params: dict | None = None) -> httpx.Response:
    """Make a GitHub API request with proper headers."""
    headers = {"Accept": "application/vnd.github+json"}
    r = httpx.get(f"{GH_API}{path}", params=params, headers=headers, timeout=15)
    r.raise_for_status()
    return r


def print_repos(items: list[dict], as_json: bool = False) -> None:
    """Print a list of repos."""
    if as_json:
        typer.echo(json_lib.dumps(items, indent=2))
        return
    for idx, repo in enumerate(items, 1):
        name = repo.get("full_name", "unknown")
        desc = repo.get("description") or ""
        stars = repo.get("stargazers_count", 0)
        lang = repo.get("language") or "unknown"
        forks = repo.get("forks_count", 0)
        created = repo.get("created_at", "")
        url = repo.get("html_url", "")
        topics = repo.get("topics", [])
        age = relative_time(created)

        typer.echo(f"{idx:2d}. [{format_stars(stars)} stars] {name}")
        if desc:
            typer.echo(f"    {desc[:120]}")
        typer.echo(f"    {lang} | {forks} forks | created {age}")
        if topics:
            typer.echo(f"    topics: {', '.join(topics[:8])}")
        if url:
            typer.echo(f"    {url}")
        typer.echo()


# --- Commands ---

LimitOption = Annotated[int, typer.Option("--limit", "-n", help="Number of items")]
JsonOption = Annotated[bool, typer.Option("--json", help="Output raw JSON")]


@app.command()
def trending(
    language: Annotated[
        Optional[str],
        typer.Option("--lang", "-l", help="Filter by language (e.g. python, rust)"),
    ] = None,
    period: Annotated[
        str, typer.Option("--period", "-p", help="Time period: daily, weekly, monthly")
    ] = "weekly",
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Trending repositories (most starred recently created repos)."""
    period_map = {"daily": 1, "weekly": 7, "monthly": 30}
    days = period_map.get(period, 7)
    date_cutoff = date_n_days_ago(days)

    q = f"created:>{date_cutoff}"
    if language:
        q += f" language:{language}"

    r = gh_get(
        "/search/repositories",
        params={
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        },
    )
    data = r.json()
    items = data.get("items", [])

    if not items:
        typer.echo("No trending repos found.")
        return

    if json:
        typer.echo(json_lib.dumps(items, indent=2))
        return

    typer.echo(f"Trending repos ({period}, since {date_cutoff})\n")
    print_repos(items)


@app.command()
def stars(
    language: Annotated[
        Optional[str], typer.Option("--lang", "-l", help="Filter by language")
    ] = None,
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Most starred repos gaining stars recently (star surge)."""
    date_cutoff = date_n_days_ago(7)
    q = f"pushed:>{date_cutoff} stars:>1000"
    if language:
        q += f" language:{language}"

    r = gh_get(
        "/search/repositories",
        params={
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        },
    )
    data = r.json()
    items = data.get("items", [])

    if not items:
        typer.echo("No results found.")
        return

    if json:
        typer.echo(json_lib.dumps(items, indent=2))
        return

    typer.echo("Popular repos with recent activity\n")
    print_repos(items)


@app.command()
def repo(
    name: Annotated[str, typer.Argument(help="Repo full name (e.g. astral-sh/uv)")],
    json: JsonOption = False,
) -> None:
    """View repository details."""
    r = gh_get(f"/repos/{name}")
    data = r.json()

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    full_name = data.get("full_name", name)
    desc = data.get("description") or ""
    stars = data.get("stargazers_count", 0)
    forks = data.get("forks_count", 0)
    lang = data.get("language") or "unknown"
    watchers = data.get("subscribers_count", 0)
    open_issues = data.get("open_issues_count", 0)
    license_info = data.get("license") or {}
    license_name = (
        license_info.get("spdx_id", "none")
        if isinstance(license_info, dict)
        else "none"
    )
    created = data.get("created_at", "")
    updated = data.get("updated_at", "")
    topics = data.get("topics", [])
    homepage = data.get("homepage") or ""

    typer.echo(f"{full_name}")
    if desc:
        typer.echo(f"  {desc}")
    typer.echo()
    typer.echo(
        f"  {format_stars(stars)} stars | {forks} forks | {watchers} watchers | {open_issues} issues"
    )
    typer.echo(f"  {lang} | license: {license_name}")
    typer.echo(f"  created {relative_time(created)} | updated {relative_time(updated)}")
    if topics:
        typer.echo(f"  topics: {', '.join(topics[:10])}")
    if homepage:
        typer.echo(f"  homepage: {homepage}")
    typer.echo(f"  {data.get('html_url', '')}")


@app.command()
def releases(
    name: Annotated[str, typer.Argument(help="Repo full name (e.g. astral-sh/uv)")],
    limit: LimitOption = 5,
    json: JsonOption = False,
) -> None:
    """View recent releases for a repository."""
    r = gh_get(f"/repos/{name}/releases", params={"per_page": limit})
    data = r.json()

    if not data:
        typer.echo(f"No releases found for {name}.")
        return

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    typer.echo(f"Releases for {name}\n")
    for idx, release in enumerate(data, 1):
        tag = release.get("tag_name", "")
        rel_name = release.get("name") or tag
        published = release.get("published_at", "")
        prerelease = release.get("prerelease", False)
        body = release.get("body") or ""
        age = relative_time(published)
        pre_tag = " [pre-release]" if prerelease else ""

        typer.echo(f"{idx:2d}. {rel_name} ({tag}){pre_tag} - {age}")
        if body:
            # Show first 3 lines of release notes
            lines = body.strip().splitlines()[:3]
            for line in lines:
                typer.echo(f"    {line[:120]}")
        typer.echo()


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    language: Annotated[
        Optional[str], typer.Option("--lang", "-l", help="Filter by language")
    ] = None,
    sort: Annotated[
        str, typer.Option(help="Sort: stars, forks, updated, best-match")
    ] = "stars",
    limit: LimitOption = 10,
    json: JsonOption = False,
) -> None:
    """Search GitHub repositories."""
    q = query
    if language:
        q += f" language:{language}"

    r = gh_get(
        "/search/repositories",
        params={
            "q": q,
            "sort": sort if sort != "best-match" else None,
            "order": "desc",
            "per_page": limit,
        },
    )
    data = r.json()
    total = data.get("total_count", 0)
    items = data.get("items", [])

    if not items:
        typer.echo(f'No results for "{query}".')
        return

    if json:
        typer.echo(json_lib.dumps(data, indent=2))
        return

    typer.echo(f'Search: "{query}" - {total} results\n')
    print_repos(items)


if __name__ == "__main__":
    app()

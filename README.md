# ez-news

AI skills to browse and search news from the terminal for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Skills

| Skill | Description |
|-------|-------------|
| **ez-hn** | Browse and search Hacker News - top/new/best stories, comments, user profiles, Algolia search, "Who is hiring?" |

No API keys or authentication required.

## Installation

```bash
npx skills add araa47/ez-news
```

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)

## Quick Start

```bash
# Top stories
uv run skills/ez-hn/scripts/hn.py top

# Search
uv run skills/ez-hn/scripts/hn.py search "LLM"

# Item details and comments
uv run skills/ez-hn/scripts/hn.py item 12345678
uv run skills/ez-hn/scripts/hn.py comments 12345678

# User profile
uv run skills/ez-hn/scripts/hn.py user dang

# Who is hiring?
uv run skills/ez-hn/scripts/hn.py whoishiring
```

All commands support `--json` for raw JSON output and `--limit` to control result count.

See the skill's [SKILL.md](skills/ez-hn/SKILL.md) for full usage details.

## Contributing

1. Install dependencies: `uv sync --all-extras`
2. Make your changes
3. Ensure pre-commit hooks pass: `prek run --all-files`
4. Ensure tests pass: `uv run -m pytest`
5. Submit a PR

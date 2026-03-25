import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "ez-github" / "scripts"),
)
gh_trending = importlib.import_module("gh_trending")

runner = CliRunner()


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(data) if data is not None else "null"
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


FAKE_REPO = {
    "full_name": "astral-sh/uv",
    "description": "A fast Python package manager",
    "stargazers_count": 50000,
    "forks_count": 1200,
    "language": "Rust",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-06-01T00:00:00Z",
    "html_url": "https://github.com/astral-sh/uv",
    "topics": ["python", "package-manager"],
    "subscribers_count": 500,
    "open_issues_count": 100,
    "license": {"spdx_id": "MIT"},
    "homepage": "https://docs.astral.sh/uv",
}

FAKE_RELEASE = {
    "tag_name": "v1.0.0",
    "name": "v1.0.0 - Stable Release",
    "published_at": "2024-06-01T00:00:00Z",
    "prerelease": False,
    "body": "## What's Changed\n- Major improvement\n- Bug fixes",
}

FAKE_SEARCH_RESPONSE = {
    "total_count": 1,
    "items": [FAKE_REPO],
}


class TestRelativeTime:
    def test_recent(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = gh_trending.relative_time(now)
        assert "s ago" in result or "just now" in result

    def test_invalid(self):
        assert gh_trending.relative_time("bad") == "bad"


class TestFormatStars:
    def test_small(self):
        assert gh_trending.format_stars(500) == "500"

    def test_thousands(self):
        assert gh_trending.format_stars(1500) == "1.5k"

    def test_millions(self):
        assert gh_trending.format_stars(1_500_000) == "1.5M"


class TestTrendingCommand:
    @patch("gh_trending.gh_get")
    def test_trending_text(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_SEARCH_RESPONSE)
        result = runner.invoke(gh_trending.app, ["trending", "--limit", "1"])
        assert result.exit_code == 0
        assert "astral-sh/uv" in result.output
        assert "50.0k stars" in result.output

    @patch("gh_trending.gh_get")
    def test_trending_json(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_SEARCH_RESPONSE)
        result = runner.invoke(gh_trending.app, ["trending", "--limit", "1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["full_name"] == "astral-sh/uv"

    @patch("gh_trending.gh_get")
    def test_trending_no_results(self, mock_get):
        mock_get.return_value = _mock_response({"total_count": 0, "items": []})
        result = runner.invoke(gh_trending.app, ["trending"])
        assert result.exit_code == 0
        assert "No trending" in result.output

    @patch("gh_trending.gh_get")
    def test_trending_with_language(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_SEARCH_RESPONSE)
        result = runner.invoke(
            gh_trending.app, ["trending", "--lang", "rust", "--limit", "1"]
        )
        assert result.exit_code == 0
        assert "astral-sh/uv" in result.output


class TestStarsCommand:
    @patch("gh_trending.gh_get")
    def test_stars_text(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_SEARCH_RESPONSE)
        result = runner.invoke(gh_trending.app, ["stars", "--limit", "1"])
        assert result.exit_code == 0
        assert "astral-sh/uv" in result.output


class TestRepoCommand:
    @patch("gh_trending.gh_get")
    def test_repo_text(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_REPO)
        result = runner.invoke(gh_trending.app, ["repo", "astral-sh/uv"])
        assert result.exit_code == 0
        assert "astral-sh/uv" in result.output
        assert "50.0k stars" in result.output
        assert "MIT" in result.output

    @patch("gh_trending.gh_get")
    def test_repo_json(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_REPO)
        result = runner.invoke(gh_trending.app, ["repo", "astral-sh/uv", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["full_name"] == "astral-sh/uv"


class TestReleasesCommand:
    @patch("gh_trending.gh_get")
    def test_releases_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_RELEASE])
        result = runner.invoke(gh_trending.app, ["releases", "astral-sh/uv"])
        assert result.exit_code == 0
        assert "v1.0.0" in result.output
        assert "Stable Release" in result.output

    @patch("gh_trending.gh_get")
    def test_releases_json(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_RELEASE])
        result = runner.invoke(gh_trending.app, ["releases", "astral-sh/uv", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["tag_name"] == "v1.0.0"

    @patch("gh_trending.gh_get")
    def test_releases_empty(self, mock_get):
        mock_get.return_value = _mock_response([])
        result = runner.invoke(gh_trending.app, ["releases", "owner/repo"])
        assert result.exit_code == 0
        assert "No releases" in result.output


class TestSearchCommand:
    @patch("gh_trending.gh_get")
    def test_search_text(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_SEARCH_RESPONSE)
        result = runner.invoke(gh_trending.app, ["search", "python package manager"])
        assert result.exit_code == 0
        assert "astral-sh/uv" in result.output
        assert "1 results" in result.output

    @patch("gh_trending.gh_get")
    def test_search_no_results(self, mock_get):
        mock_get.return_value = _mock_response({"total_count": 0, "items": []})
        result = runner.invoke(gh_trending.app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "No results" in result.output


class TestPrintRepos:
    def test_print_repos_text(self, capsys):
        gh_trending.print_repos([FAKE_REPO])
        captured = capsys.readouterr()
        assert "astral-sh/uv" in captured.out
        assert "50.0k stars" in captured.out
        assert "Rust" in captured.out

    def test_print_repos_json(self, capsys):
        gh_trending.print_repos([FAKE_REPO], as_json=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data[0]["full_name"] == "astral-sh/uv"

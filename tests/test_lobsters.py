import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "ez-lobsters" / "scripts"),
)
lobsters = importlib.import_module("lobsters")

runner = CliRunner()


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(data) if data is not None else "null"
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


FAKE_STORY = {
    "short_id": "abc123",
    "title": "Test Lobsters Story",
    "score": 42,
    "submitter_user": {"username": "testuser"},
    "comment_count": 5,
    "url": "https://example.com",
    "tags": ["rust", "programming"],
    "created_at": "2024-01-01T00:00:00Z",
    "description": "",
    "comments": [],
}

FAKE_STORY_WITH_COMMENTS = {
    **FAKE_STORY,
    "comments": [
        {
            "commenting_user": {"username": "commenter"},
            "comment": "Great <b>post</b>!",
            "score": 3,
            "created_at": "2024-01-01T01:00:00Z",
            "indent_level": 1,
            "comments": [],
        }
    ],
}


class TestRelativeTime:
    def test_recent(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = lobsters.relative_time(now)
        assert "s ago" in result or "just now" in result

    def test_invalid(self):
        assert lobsters.relative_time("not-a-date") == "not-a-date"


class TestHtmlToText:
    def test_br_tags(self):
        assert lobsters.html_to_text("hello<br>world") == "hello\nworld"

    def test_strips_tags(self):
        assert lobsters.html_to_text("<b>bold</b>") == "bold"

    def test_empty(self):
        assert lobsters.html_to_text("") == ""


class TestHottestCommand:
    @patch("lobsters.fetch_stories", return_value=[FAKE_STORY])
    def test_hottest_text(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["hottest", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test Lobsters Story" in result.output
        assert "42 pts" in result.output
        assert "testuser" in result.output

    @patch("lobsters.fetch_stories", return_value=[FAKE_STORY])
    def test_hottest_json(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["hottest", "--limit", "1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["title"] == "Test Lobsters Story"


class TestNewestCommand:
    @patch("lobsters.fetch_stories", return_value=[FAKE_STORY])
    def test_newest_text(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["newest", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test Lobsters Story" in result.output


class TestTagCommand:
    @patch("lobsters.fetch_stories", return_value=[FAKE_STORY])
    def test_tag_text(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["tag", "rust", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test Lobsters Story" in result.output
        mock_fetch.assert_called_once_with("t/rust.json", 1)


class TestItemCommand:
    @patch("lobsters.fetch_story", return_value=FAKE_STORY)
    def test_item_text(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["item", "abc123"])
        assert result.exit_code == 0
        assert "Test Lobsters Story" in result.output
        assert "42 pts" in result.output

    @patch("lobsters.fetch_story", return_value=FAKE_STORY)
    def test_item_json(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["item", "abc123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "Test Lobsters Story"

    @patch("lobsters.fetch_story", return_value=None)
    def test_item_not_found(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["item", "zzz"])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestCommentsCommand:
    @patch("lobsters.fetch_story", return_value=FAKE_STORY_WITH_COMMENTS)
    def test_comments_text(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["comments", "abc123"])
        assert result.exit_code == 0
        assert "commenter" in result.output
        assert "Great post!" in result.output

    @patch("lobsters.fetch_story", return_value=FAKE_STORY_WITH_COMMENTS)
    def test_comments_json(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["comments", "abc123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    @patch("lobsters.fetch_story", return_value=FAKE_STORY)
    def test_no_comments(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["comments", "abc123"])
        assert result.exit_code == 0
        assert "No comments" in result.output

    @patch("lobsters.fetch_story", return_value=None)
    def test_comments_not_found(self, mock_fetch):
        result = runner.invoke(lobsters.app, ["comments", "zzz"])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestSearchCommand:
    @patch("httpx.get")
    def test_search_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_STORY])
        result = runner.invoke(lobsters.app, ["search", "rust"])
        assert result.exit_code == 0
        assert "Test Lobsters Story" in result.output

    @patch("httpx.get")
    def test_search_no_results(self, mock_get):
        mock_get.return_value = _mock_response([])
        result = runner.invoke(lobsters.app, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "No results" in result.output


class TestPrintStories:
    def test_print_stories_text(self, capsys):
        lobsters.print_stories([FAKE_STORY])
        captured = capsys.readouterr()
        assert "Test Lobsters Story" in captured.out
        assert "42 pts" in captured.out
        assert "rust, programming" in captured.out

    def test_print_stories_json(self, capsys):
        lobsters.print_stories([FAKE_STORY], as_json=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data[0]["title"] == "Test Lobsters Story"

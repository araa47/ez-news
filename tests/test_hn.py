import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

# Make the skill importable
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "skills" / "ez-hn" / "scripts")
)
hn = importlib.import_module("hn")

runner = CliRunner()


# --- Helper fixtures ---


def _mock_response(data, status_code=200):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(data) if data is not None else "null"
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


# --- Unit tests for helpers ---


class TestRelativeTime:
    def test_seconds(self):
        import time

        ts = int(time.time()) - 30
        assert hn.relative_time(ts) == "30s ago"

    def test_minutes(self):
        import time

        ts = int(time.time()) - 300
        assert hn.relative_time(ts) == "5m ago"

    def test_hours(self):
        import time

        ts = int(time.time()) - 7200
        assert hn.relative_time(ts) == "2h ago"

    def test_days(self):
        import time

        ts = int(time.time()) - 172800
        assert hn.relative_time(ts) == "2d ago"

    def test_months(self):
        import time

        ts = int(time.time()) - 5184000
        assert hn.relative_time(ts) == "2mo ago"

    def test_years(self):
        import time

        ts = int(time.time()) - 63072000
        assert hn.relative_time(ts) == "2y ago"


class TestHtmlToText:
    def test_br_tags(self):
        assert hn.html_to_text("hello<br>world") == "hello\nworld"

    def test_p_tags(self):
        result = hn.html_to_text("hello<p>world")
        assert "hello" in result
        assert "world" in result

    def test_strips_tags(self):
        assert hn.html_to_text("<b>bold</b>") == "bold"

    def test_unescapes_entities(self):
        assert hn.html_to_text("&amp; &lt; &gt;") == "& < >"

    def test_empty(self):
        assert hn.html_to_text("") == ""


# --- CLI command tests ---

FAKE_STORY = {
    "id": 123,
    "type": "story",
    "title": "Test Story",
    "score": 42,
    "by": "testuser",
    "descendants": 5,
    "url": "https://example.com",
    "time": 1700000000,
    "kids": [201, 202],
}

FAKE_JOB = {
    "id": 456,
    "type": "job",
    "title": "Test Job",
    "score": 1,
    "by": "employer",
    "time": 1700000000,
    "url": "https://jobs.example.com",
}

FAKE_COMMENT = {
    "id": 201,
    "type": "comment",
    "by": "commenter",
    "text": "Great <b>post</b>!",
    "time": 1700000000,
    "kids": [],
}

FAKE_USER = {
    "id": "dang",
    "karma": 12345,
    "created": 1200000000,
    "about": "HN moderator",
    "submitted": [123],
}


class TestTopCommand:
    @patch("hn.fetch_items_parallel", return_value=[FAKE_STORY])
    @patch("hn.fetch_story_ids", return_value=[123])
    def test_top_text(self, mock_ids, mock_items):
        result = runner.invoke(hn.app, ["top", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test Story" in result.output
        assert "42 pts" in result.output
        assert "testuser" in result.output

    @patch("hn.fetch_items_parallel", return_value=[FAKE_STORY])
    @patch("hn.fetch_story_ids", return_value=[123])
    def test_top_json(self, mock_ids, mock_items):
        result = runner.invoke(hn.app, ["top", "--limit", "1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["title"] == "Test Story"

    @patch("hn.fetch_items_parallel", return_value=[FAKE_JOB])
    @patch("hn.fetch_story_ids", return_value=[456])
    def test_jobs_text(self, mock_ids, mock_items):
        result = runner.invoke(hn.app, ["jobs", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test Job" in result.output
        assert "comments" not in result.output


class TestItemCommand:
    @patch("hn.fetch_item", return_value=FAKE_STORY)
    def test_item_text(self, mock_fetch):
        result = runner.invoke(hn.app, ["item", "123"])
        assert result.exit_code == 0
        assert "Test Story" in result.output
        assert "42 pts" in result.output

    @patch("hn.fetch_item", return_value=FAKE_STORY)
    def test_item_json(self, mock_fetch):
        result = runner.invoke(hn.app, ["item", "123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "Test Story"

    @patch("hn.fetch_item", return_value=None)
    def test_item_not_found(self, mock_fetch):
        result = runner.invoke(hn.app, ["item", "999"])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestCommentsCommand:
    @patch("hn.fetch_items_parallel", return_value=[FAKE_COMMENT])
    @patch("hn.fetch_item", return_value=FAKE_STORY)
    def test_comments_text(self, mock_item, mock_parallel):
        result = runner.invoke(hn.app, ["comments", "123"])
        assert result.exit_code == 0
        assert "commenter" in result.output
        assert "Great post!" in result.output

    @patch("hn.fetch_items_parallel", return_value=[FAKE_COMMENT])
    @patch("hn.fetch_item", return_value=FAKE_STORY)
    def test_comments_json(self, mock_item, mock_parallel):
        result = runner.invoke(hn.app, ["comments", "123", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    @patch("hn.fetch_item", return_value={"id": 123, "kids": []})
    def test_no_comments(self, mock_item):
        result = runner.invoke(hn.app, ["comments", "123"])
        assert result.exit_code == 0
        assert "No comments" in result.output


class TestUserCommand:
    @patch("hn.fetch_items_parallel", return_value=[FAKE_STORY])
    @patch("httpx.get")
    def test_user_text(self, mock_get, mock_parallel):
        mock_get.return_value = _mock_response(FAKE_USER)
        result = runner.invoke(hn.app, ["user", "dang"])
        assert result.exit_code == 0
        assert "dang" in result.output
        assert "12345" in result.output

    @patch("httpx.get")
    def test_user_not_found(self, mock_get):
        mock_get.return_value = _mock_response(None)
        mock_get.return_value.text = "null"
        result = runner.invoke(hn.app, ["user", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestSearchCommand:
    @patch("httpx.get")
    def test_search_text(self, mock_get):
        mock_get.return_value = _mock_response(
            {
                "nbHits": 1,
                "hits": [
                    {
                        "title": "Rust is great",
                        "author": "rustfan",
                        "points": 100,
                        "num_comments": 50,
                        "url": "https://rust.example.com",
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                ],
            }
        )
        result = runner.invoke(hn.app, ["search", "rust"])
        assert result.exit_code == 0
        assert "Rust is great" in result.output
        assert "100 pts" in result.output

    @patch("httpx.get")
    def test_search_json(self, mock_get):
        mock_get.return_value = _mock_response({"nbHits": 0, "hits": []})
        result = runner.invoke(hn.app, ["search", "nonexistent", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["nbHits"] == 0


class TestWhoIsHiringCommand:
    @patch("hn.fetch_items_parallel", return_value=[FAKE_COMMENT])
    @patch(
        "hn.fetch_item",
        return_value={"id": 999, "title": "Who is hiring?", "kids": [201]},
    )
    @patch("httpx.get")
    def test_whoishiring_text(self, mock_get, mock_item, mock_parallel):
        mock_get.return_value = _mock_response(
            {
                "hits": [
                    {"objectID": "999", "title": "Ask HN: Who is hiring? (March 2024)"}
                ]
            }
        )
        result = runner.invoke(hn.app, ["whoishiring"])
        assert result.exit_code == 0
        assert "Who is hiring?" in result.output

    @patch("httpx.get")
    def test_whoishiring_no_thread(self, mock_get):
        mock_get.return_value = _mock_response({"hits": []})
        result = runner.invoke(hn.app, ["whoishiring"])
        assert result.exit_code == 1
        assert "Could not find" in result.output


class TestFetchItem:
    @patch("httpx.get")
    def test_fetch_item_success(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_STORY)
        result = hn.fetch_item(123)
        assert result is not None
        assert result["title"] == "Test Story"

    @patch("httpx.get")
    def test_fetch_item_not_found(self, mock_get):
        resp = _mock_response(None, status_code=200)
        resp.text = "null"
        mock_get.return_value = resp
        result = hn.fetch_item(999)
        assert result is None


class TestPrintStories:
    def test_print_stories_text(self, capsys):
        hn.print_stories([FAKE_STORY])
        captured = capsys.readouterr()
        assert "Test Story" in captured.out
        assert "42 pts" in captured.out

    def test_print_stories_json(self, capsys):
        hn.print_stories([FAKE_STORY], as_json=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data[0]["title"] == "Test Story"

    def test_print_jobs(self, capsys):
        hn.print_stories([FAKE_JOB])
        captured = capsys.readouterr()
        assert "Test Job" in captured.out
        assert "comments" not in captured.out

import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "skills" / "ez-devto" / "scripts"),
)
devto = importlib.import_module("devto")

runner = CliRunner()


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = json.dumps(data) if data is not None else "null"
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


FAKE_ARTICLE = {
    "id": 12345,
    "title": "Test DEV.to Article",
    "user": {"username": "devuser"},
    "positive_reactions_count": 100,
    "comments_count": 20,
    "tag_list": ["python", "tutorial"],
    "url": "https://dev.to/devuser/test-article",
    "published_at": "2024-01-01T00:00:00Z",
    "reading_time_minutes": 5,
    "description": "A test article about Python.",
    "body_markdown": "# Hello\n\nThis is a test article.",
}

FAKE_COMMENT = {
    "user": {"username": "commenter"},
    "body_html": "<p>Great article!</p>",
    "created_at": "2024-01-02T00:00:00Z",
    "children": [],
}

FAKE_TAG = {
    "name": "python",
    "published_articles_count": 50000,
}


class TestRelativeTime:
    def test_recent(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        result = devto.relative_time(now)
        assert "s ago" in result or "just now" in result

    def test_invalid(self):
        assert devto.relative_time("bad") == "bad"


class TestTopCommand:
    @patch("devto.devto_get")
    def test_top_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_ARTICLE])
        result = runner.invoke(devto.app, ["top", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test DEV.to Article" in result.output
        assert "100 reactions" in result.output
        assert "devuser" in result.output

    @patch("devto.devto_get")
    def test_top_json(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_ARTICLE])
        result = runner.invoke(devto.app, ["top", "--limit", "1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["title"] == "Test DEV.to Article"


class TestLatestCommand:
    @patch("devto.devto_get")
    def test_latest_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_ARTICLE])
        result = runner.invoke(devto.app, ["latest", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test DEV.to Article" in result.output


class TestRisingCommand:
    @patch("devto.devto_get")
    def test_rising_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_ARTICLE])
        result = runner.invoke(devto.app, ["rising", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test DEV.to Article" in result.output


class TestTagCommand:
    @patch("devto.devto_get")
    def test_tag_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_ARTICLE])
        result = runner.invoke(devto.app, ["tag", "python", "--limit", "1"])
        assert result.exit_code == 0
        assert "Test DEV.to Article" in result.output


class TestArticleCommand:
    @patch("devto.devto_get")
    def test_article_text(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_ARTICLE)
        result = runner.invoke(devto.app, ["article", "12345"])
        assert result.exit_code == 0
        assert "Test DEV.to Article" in result.output
        assert "100 reactions" in result.output
        assert "5 min read" in result.output

    @patch("devto.devto_get")
    def test_article_json(self, mock_get):
        mock_get.return_value = _mock_response(FAKE_ARTICLE)
        result = runner.invoke(devto.app, ["article", "12345", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "Test DEV.to Article"


class TestCommentsCommand:
    @patch("devto.devto_get")
    def test_comments_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_COMMENT])
        result = runner.invoke(devto.app, ["comments", "12345"])
        assert result.exit_code == 0
        assert "commenter" in result.output
        assert "Great article!" in result.output

    @patch("devto.devto_get")
    def test_comments_json(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_COMMENT])
        result = runner.invoke(devto.app, ["comments", "12345", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1

    @patch("devto.devto_get")
    def test_no_comments(self, mock_get):
        mock_get.return_value = _mock_response([])
        result = runner.invoke(devto.app, ["comments", "12345"])
        assert result.exit_code == 0
        assert "No comments" in result.output


class TestSearchCommand:
    @patch("devto.devto_get")
    def test_search_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_ARTICLE])
        result = runner.invoke(devto.app, ["search", "python"])
        assert result.exit_code == 0
        assert "Test DEV.to Article" in result.output


class TestTagsCommand:
    @patch("devto.devto_get")
    def test_tags_text(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_TAG])
        result = runner.invoke(devto.app, ["tags"])
        assert result.exit_code == 0
        assert "#python" in result.output
        assert "50000 articles" in result.output

    @patch("devto.devto_get")
    def test_tags_json(self, mock_get):
        mock_get.return_value = _mock_response([FAKE_TAG])
        result = runner.invoke(devto.app, ["tags", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["name"] == "python"


class TestPrintArticles:
    def test_print_articles_text(self, capsys):
        devto.print_articles([FAKE_ARTICLE])
        captured = capsys.readouterr()
        assert "Test DEV.to Article" in captured.out
        assert "100 reactions" in captured.out
        assert "python, tutorial" in captured.out

    def test_print_articles_json(self, capsys):
        devto.print_articles([FAKE_ARTICLE], as_json=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data[0]["title"] == "Test DEV.to Article"

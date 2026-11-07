"""Offline regression checks for contribution discovery and static rendering."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import sync_activity as activity

NOW = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)


def record(name="org/example", date="2026-11-06T12:00:00Z", label="Code push"):
    return {"name": name, "date": date, "activity": label,
            "description": "Safe <text>", "language": "Python"}


class ContributionTests(unittest.TestCase):
    def test_merging_deduplicates_and_sorts_by_personal_contribution(self):
        merged = activity.merge([record("Org/A", "2026-10-01T00:00:00Z"),
                                 record("Org/B", "2026-11-01T00:00:00Z")],
                                [record("org/a", "2026-11-06T00:00:00Z", "Pull request")], now=NOW)
        self.assertEqual([x["name"].lower() for x in merged], ["org/a", "org/b"])
        self.assertEqual(merged[0]["activity"], "Pull request")

    def test_older_than_year_future_and_self_repositories_are_excluded(self):
        rows = activity.merge([record("FuTseYi/futseyi.github.io"),
                               record("FuTseYi/FuTseYi"),
                               record("org/old", "2025-10-01T12:00:00Z"),
                               record("org/future", "2026-11-08T12:00:00Z"),
                               record()], now=NOW)
        self.assertEqual([row["name"] for row in rows], ["org/example"])

    def test_graphql_reads_personal_date_not_repo_updated_at(self):
        payload = {"data": {"user": {"contributionsCollection": {
            "commitContributionsByRepository": [
                {"repository": {"nameWithOwner": "org/code", "isPrivate": False,
                                "isArchived": False, "isDisabled": False,
                                "description": "text", "primaryLanguage": {"name": "Python"}},
                 "contributions": {"nodes": [{"occurredAt": "2026-11-03T00:00:00Z"}]}},
                {"repository": {"nameWithOwner": "org/private", "isPrivate": True,
                                "isArchived": False, "isDisabled": False},
                 "contributions": {"nodes": [{"occurredAt": "2026-11-05T00:00:00Z"}]}}
            ]}}}}
        with patch.object(activity, "fetch", return_value=payload):
            result = activity.graphql_commits(NOW)
        self.assertEqual([(x["name"], x["date"]) for x in result],
                         [("org/code", "2026-11-03T00:00:00Z")])

    def test_rest_discovery_separates_commit_author_and_pr_author(self):
        commits = [{"author": {"login": "FuTseYi"}, "repository": {"full_name": "org/code"},
                    "commit": {"committer": {"date": "2026-10-01T10:00:00Z"}}},
                   {"author": {"login": "other"}, "repository": {"full_name": "org/other"},
                    "commit": {"committer": {"date": "2026-10-03T10:00:00Z"}}}]
        prs = [{"user": {"login": "FuTseYi"}, "repository_url": activity.API + "/repos/org/review",
                "created_at": "2026-11-01T00:00:00Z"},
               {"user": {"login": "other"}, "repository_url": activity.API + "/repos/org/other",
                "created_at": "2026-11-02T00:00:00Z"}]
        with patch.object(activity, "search", side_effect=[commits, prs]):
            self.assertEqual([x["name"] for x in activity.search_commits(NOW)], ["org/code"])
            self.assertEqual([x["name"] for x in activity.search_prs(NOW)], ["org/review"])

    def test_search_paginates_without_silent_truncation(self):
        responses = [{"items": [{"id": i} for i in range(100)], "incomplete_results": False},
                     {"items": [{"id": 101}], "incomplete_results": False}]
        with patch.object(activity, "fetch", side_effect=responses) as fetch:
            self.assertEqual(len(activity.search("prs", NOW)), 101)
            self.assertEqual(fetch.call_count, 2)

    def test_visibility_revalidation_and_html_escape(self):
        def fetch(url):
            return {"full_name": url.rsplit("/repos/", 1)[1],
                    "private": url.endswith("/private"), "archived": url.endswith("/archived"),
                    "disabled": False, "description": "<unsafe>", "language": "JavaScript"}
        with patch.object(activity, "fetch", side_effect=fetch):
            rows = activity.repository_metadata([record("org/public"), record("org/private"),
                                                 record("org/archived")])
        self.assertEqual([x["name"] for x in rows], ["org/public"])
        self.assertIn("&lt;unsafe&gt;", activity.render({"updated_at": NOW.isoformat(), "entries": rows}))

    def test_collect_combines_old_verified_history_with_new_discovery(self):
        old = {"entries": [record("org/previous", "2026-09-01T00:00:00Z")]}
        with patch.dict("os.environ", {}, clear=True), \
             patch.object(activity, "search_commits", return_value=[record("org/new")]), \
             patch.object(activity, "search_prs", return_value=[]), \
             patch.object(activity, "repository_metadata", side_effect=lambda rows: rows):
            result = activity.collect(old, NOW)
        self.assertEqual([x["name"] for x in result["entries"]], ["org/new", "org/previous"])

    def test_build_failure_preserves_original_snapshot_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            page = root / "_site/index.html"
            page.write_text(activity.START + "fallback" + activity.END, encoding="utf-8")
            cache = root / "_site/contributions.json"
            original = {"updated_at": "2026-11-01T00:00:00Z",
                        "entries": [record()]}
            cache.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(activity, "ROOT", root), patch.object(activity, "SNAPSHOT", cache), \
                 patch.object(activity, "collect", side_effect=URLError("offline")), \
                 patch("sys.argv", ["sync_activity.py", "--refresh"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                activity.main()
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), original)
            self.assertIn("org/example", page.read_text(encoding="utf-8"))

    def test_no_snapshot_and_offline_does_not_overwrite_source_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            page = root / "_site/index.html"
            source = activity.START + "fallback" + activity.END
            page.write_text(source, encoding="utf-8")
            with patch.object(activity, "ROOT", root), \
                 patch.object(activity, "SNAPSHOT", root / "_site/contributions.json"), \
                 patch.object(activity, "fetch", side_effect=URLError("offline")), \
                 patch.object(activity, "collect", side_effect=URLError("offline")), \
                 patch("sys.argv", ["sync_activity.py", "--refresh"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                activity.main()
            self.assertEqual(page.read_text(encoding="utf-8"), source)


if __name__ == "__main__":
    unittest.main()

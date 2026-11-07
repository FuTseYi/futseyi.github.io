"""Offline regression tests for full-history GitHub contribution discovery."""
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


def record(name="org/example", date="2020-01-01T12:00:00Z", label="Commit"):
    return {"name": name, "date": date, "activity": label,
            "description": "Safe <text>", "language": "Python"}


def group(name, date):
    return {"repository": {"nameWithOwner": name, "isPrivate": False,
                           "isArchived": False, "isDisabled": False},
            "contributions": {"nodes": [{"occurredAt": date}]}}


def graphql(groups=None, totals=None):
    groups = groups or {}
    totals = totals or {}
    collection = {}
    for field, total, _ in activity.KINDS:
        collection[field] = groups.get(field, [])
        collection[total] = totals.get(total, len(collection[field]))
    return {"data": {"user": {"contributionsCollection": collection}}}


class ContributionTests(unittest.TestCase):
    def test_merge_preserves_old_history_with_no_repository_cap(self):
        entries = [record(f"org/project-{i}", f"2020-01-{i+1:02d}T12:00:00Z")
                   for i in range(20)]
        entries += [record("ORG/PROJECT-0", "2026-11-06T12:00:00Z", "Pull request"),
                    record("FuTseYi/FuTseYi"), record("FuTseYi/futseyi.github.io")]
        rows = activity.merge(entries, now=NOW)
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["name"], "ORG/PROJECT-0")
        self.assertEqual(rows[0]["activity"], "Pull request")
        self.assertEqual(rows[-1]["date"][:4], "2020")

    def test_annual_windows_cover_all_years_without_overlap(self):
        start = datetime(2018, 7, 3, tzinfo=timezone.utc)
        windows = list(activity.annual_windows(start, NOW))
        self.assertEqual(len(windows), 9)
        self.assertEqual(windows[0][0], start)
        self.assertEqual(windows[-1][1], NOW)
        for (_, right), (left, _) in zip(windows, windows[1:]):
            self.assertEqual(left - right, timedelta(seconds=1))

    def test_graphql_covers_commit_pr_issue_and_review(self):
        keys = [field for field, _, _ in activity.KINDS]
        result = graphql({key: [group(f"org/repo-{i}", "2021-03-01T00:00:00Z")]
                          for i, key in enumerate(keys)})
        with patch.object(activity, "fetch", return_value=result):
            rows = activity.graphql_window(NOW - timedelta(days=2), NOW)
        self.assertEqual({r["activity"] for r in rows},
                         {"Commit", "Pull request", "Issue", "Review"})

    def test_graphql_splits_incomplete_repo_coverage(self):
        field, count, _ = activity.KINDS[0]
        bad = graphql(totals={count: 101})
        okay = graphql({field: [group("org/old", "2026-11-01T00:00:00Z")]})
        with patch.object(activity, "fetch", side_effect=[bad, okay, okay]) as fetch:
            rows = activity.graphql_window(NOW - timedelta(days=30), NOW)
        self.assertEqual(len(rows), 2)
        self.assertEqual(fetch.call_count, 3)

    def test_search_splits_more_than_one_thousand_in_a_day(self):
        too_many = {"total_count": 1001, "items": [], "incomplete_results": False}
        with patch.object(activity, "fetch", return_value=too_many):
            with self.assertRaisesRegex(ValueError, "one day"):
                activity.search("prs", NOW, NOW)

    def test_search_paginated_without_losing_old_prs(self):
        first = {"total_count": 101, "items": [{"number": i} for i in range(100)],
                 "incomplete_results": False}
        second = {"total_count": 101, "items": [{"number": 100}], "incomplete_results": False}
        with patch.object(activity, "fetch", side_effect=[first, second]) as fetch:
            rows = activity.search("prs", NOW - timedelta(days=1), NOW)
        self.assertEqual(len(rows), 101)
        self.assertEqual(fetch.call_count, 2)

    def test_limited_token_falls_back_to_throttled_public_search(self):
        from urllib.error import HTTPError
        denied = HTTPError(activity.API + "/search/issues", 422, "Validation Failed", {}, None)
        with patch.object(activity, "ANONYMOUS_SEARCH", False), \
             patch.object(activity, "NEXT_ANONYMOUS_SEARCH", 0.0), \
             patch.object(activity, "fetch", side_effect=[denied, {"items": []}, {"items": []}]) as fetch, \
             patch.object(activity.time, "sleep") as sleep, \
             contextlib.redirect_stdout(io.StringIO()):
            activity.search_fetch(activity.API + "/search/issues?q=first")
            activity.search_fetch(activity.API + "/search/issues?q=second")
            self.assertTrue(activity.ANONYMOUS_SEARCH)
        self.assertEqual(fetch.call_args_list[0].kwargs, {})
        self.assertEqual(fetch.call_args_list[1].kwargs, {"authenticated": False})
        self.assertEqual(fetch.call_args_list[2].kwargs, {"authenticated": False})
        sleep.assert_called_once()

    def test_authored_old_pr_commit_is_personal_activity(self):
        pr = {"repository_url": activity.API + "/repos/upstream/repo", "number": 7}
        commits = [
            {"author": {"login": "Other"}, "commit": {"author": {"date": "2026-11-06T00:00:00Z"}}},
            {"author": {"login": "FuTseYi"}, "commit": {"author": {"date": "2026-11-05T00:00:00Z"}}},
        ]
        with patch.object(activity, "fetch", return_value=commits) as fetch:
            rows = activity.inspect_pr_commits(pr)
        self.assertEqual([(r["activity"], r["date"]) for r in rows],
                         [("Commit", "2026-11-05T00:00:00Z")])
        self.assertEqual(fetch.call_args.kwargs["authenticated"], False)

    def test_other_peoples_comments_do_not_refresh_personal_date(self):
        issue = {"repository_url": activity.API + "/repos/upstream/repo", "number": 2}
        comments = [
            {"user": {"login": "Other"}, "created_at": "2026-11-06T00:00:00Z"},
            {"user": {"login": "FuTseYi"}, "created_at": "2023-03-01T00:00:00Z"},
        ]
        with patch.object(activity, "fetch", return_value=comments):
            rows = activity.comment_contributions(issue)
        self.assertEqual([r["date"] for r in rows], ["2023-03-01T00:00:00Z"])

    def test_discover_account_lifetime_not_recent_event_window(self):
        user = {"created_at": "2020-04-01T00:00:00Z"}
        old = record("org/old", "2020-06-01T00:00:00Z")
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}), \
             patch.object(activity, "fetch", return_value=user), \
             patch.object(activity, "graphql_window", return_value=[old]) as graph, \
             patch.object(activity, "search", return_value=[]):
            rows = activity.discover(NOW)
        self.assertEqual(graph.call_count, 7)
        self.assertEqual(len(rows), 7)

    def test_public_metadata_is_verified_without_organization_token(self):
        repo = {"full_name": "upstream/public", "private": False,
                "archived": False, "disabled": False, "description": "<unsafe>",
                "language": "Python"}
        with patch.object(activity, "fetch", return_value=repo) as fetch:
            rows = activity.repository_metadata([record("upstream/public")])
        self.assertEqual(len(rows), 1)
        self.assertFalse(fetch.call_args.kwargs["authenticated"])
        self.assertIn("&lt;unsafe&gt;", activity.render({"updated_at": NOW.isoformat(),
                                                       "entries": rows}))

    def test_archived_public_repository_is_still_part_of_history(self):
        repo = {"full_name": "upstream/archived", "private": False, "archived": True,
                "disabled": False, "visibility": "public"}
        with patch.object(activity, "fetch", return_value=repo):
            rows = activity.repository_metadata([record("upstream/archived")])
        self.assertEqual([row["name"] for row in rows], ["upstream/archived"])

    def test_local_snapshot_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contributions.json"
            data = {"updated_at": NOW.isoformat(), "entries": [record()]}
            with patch.object(activity, "SNAPSHOT", path):
                self.assertIsNone(activity.load_snapshot())
                path.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(activity.load_snapshot(), data)

    def test_failed_refresh_keeps_original_timestamp_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            page = root / "_site/index.html"
            page.write_text(activity.START + "fallback" + activity.END, encoding="utf-8")
            cache = root / "_site/contributions.json"
            original = {"updated_at": "2026-11-01T00:00:00Z", "entries": [record()]}
            cache.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(activity, "ROOT", root), patch.object(activity, "SNAPSHOT", cache), \
                 patch.object(activity, "collect", side_effect=URLError("offline")), \
                 patch("sys.argv", ["sync_activity.py", "--refresh"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                activity.main()
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), original)
            self.assertIn("org/example", page.read_text(encoding="utf-8"))

    def test_no_snapshot_offline_retains_homepage_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            page = root / "_site/index.html"
            source = activity.START + "fallback" + activity.END
            page.write_text(source, encoding="utf-8")
            with patch.object(activity, "ROOT", root), \
                 patch.object(activity, "SNAPSHOT", root / "_site/contributions.json"), \
                 patch.object(activity, "collect", side_effect=URLError("offline")), \
                 patch("sys.argv", ["sync_activity.py", "--refresh"]), \
                 contextlib.redirect_stdout(io.StringIO()):
                activity.main()
            self.assertEqual(page.read_text(encoding="utf-8"), source)


if __name__ == "__main__":
    unittest.main()

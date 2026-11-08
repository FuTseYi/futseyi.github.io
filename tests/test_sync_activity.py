"""Offline regression tests for the official all-time GitHub contribution collector."""

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


def repo(name="upstream/project", visibility="PUBLIC", is_fork=False):
    return {"nameWithOwner": name, "visibility": visibility, "isFork": is_fork,
            "description": "<Safe project>", "primaryLanguage": {"name": "Python"}}


def record(name="upstream/project", date="2020-01-01T12:00:00Z", label="Commit"):
    return {"name": name, "date": date, "activity": label,
            "description": "Example", "language": "Python"}


def collection_result(overrides=None):
    rows = {"repositoryContributions": {"nodes": []}, "totalRepositoryContributions": 0}
    for field, total, _ in activity.KINDS:
        rows[field] = []
        rows[total] = 0
    rows.update(overrides or {})
    return {"contributionsCollection": rows}


def group(date="2026-11-01T00:00:00Z", repository=None):
    return {"repository": repository or repo(), "contributions": {"nodes": [{"occurredAt": date}]}}


class ContributionTests(unittest.TestCase):
    def test_merge_keeps_every_year_and_repository_without_artificial_limit(self):
        rows = [record(f"org/project-{i}", f"2020-01-{i + 1:02d}T12:00:00Z")
                for i in range(20)]
        rows += [record("ORG/PROJECT-0", "2026-11-06T12:00:00Z", "Review"),
                 record("FuTseYi/futseyi.github.io"), record("FuTseYi/FuTseYi")]
        merged = activity.merge(rows, NOW)
        self.assertEqual(len(merged), 20)
        self.assertEqual(merged[0]["name"], "ORG/PROJECT-0")
        self.assertEqual(merged[0]["activity"], "Review")
        self.assertEqual(merged[-1]["date"][:4], "2020")

    def test_leap_year_is_covered_without_one_year_query_overflow(self):
        periods = list(activity.windows(2024, NOW))
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0][0], datetime(2024, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(periods[-1][1], datetime(2024, 12, 31, 23, 59, 59,
                                                  tzinfo=timezone.utc))
        self.assertEqual(periods[1][0] - periods[0][1], timedelta(seconds=1))
        self.assertTrue(all(end - start < timedelta(days=365) for start, end in periods))

    def test_official_categories_include_repository_creation(self):
        fields = [field for field, _, _ in activity.KINDS]
        payload = {field: [group(repository=repo(f"org/repo-{i}"))]
                   for i, field in enumerate(fields)}
        for field, total, _ in activity.KINDS:
            payload[total] = 1
        payload["totalRepositoryContributions"] = 1
        payload["repositoryContributions"] = {"nodes": [{
            "occurredAt": "2022-05-01T00:00:00Z", "repository": repo("org/new")
        }]}
        with patch.object(activity, "query", return_value=collection_result(payload)):
            rows = activity.collection(NOW - timedelta(days=5), NOW)
        self.assertEqual({entry["activity"] for entry in rows},
                         {"Commit", "Pull request", "Issue", "Review", "Repository"})
        self.assertEqual(len(rows), 5)

    def test_fork_only_creation_does_not_count_as_a_contribution(self):
        fork_names = ("FuTseYi/jailbreaks", "FuTseYi/Shadowrocket", "FuTseYi/edit")
        creations = [{"occurredAt": "2026-11-07T00:00:00Z",
                      "repository": repo(name, is_fork=True)} for name in fork_names]
        creations.append({"occurredAt": "2025-05-01T00:00:00Z",
                          "repository": repo("FuTseYi/original")})
        payload = collection_result({
            "totalRepositoryContributions": len(creations),
            "repositoryContributions": {"nodes": creations},
        })
        with patch.object(activity, "query", return_value=payload):
            rows = activity.collection(NOW - timedelta(days=10), NOW)
        self.assertEqual([entry["name"] for entry in rows], ["FuTseYi/original"])
        self.assertEqual(rows[0]["activity"], "Repository")

    def test_fork_with_a_real_official_contribution_is_retained(self):
        fork = repo("FuTseYi/edit", is_fork=True)
        field, total, _ = activity.KINDS[0]
        payload = collection_result({
            field: [group(repository=fork)],
            total: 1,
            "totalRepositoryContributions": 1,
            "repositoryContributions": {"nodes": [{
                "occurredAt": "2026-11-07T00:00:00Z", "repository": fork
            }]},
        })
        with patch.object(activity, "query", return_value=payload):
            rows = activity.collection(NOW - timedelta(days=10), NOW)
        self.assertEqual([(entry["name"], entry["activity"]) for entry in rows],
                         [("FuTseYi/edit", "Commit")])

    def test_nonpublic_and_excluded_repositories_never_render(self):
        self.assertIsNone(activity.contribution(repo(visibility="PRIVATE"),
                                                "2026-11-01T00:00:00Z", "Commit"))
        self.assertIsNone(activity.contribution(repo("FuTseYi/FuTseYi"),
                                                "2026-11-01T00:00:00Z", "Commit"))
        self.assertIsNone(activity.contribution(repo("FuTseYi/futseyi.github.io"),
                                                "2026-11-01T00:00:00Z", "Commit"))
        self.assertIsNotNone(activity.contribution(repo("org/archived"),
                                                  "2020-01-01T00:00:00Z", "Commit"))

    def test_graphql_incomplete_repositories_split_instead_of_truncate(self):
        field, total, _ = activity.KINDS[0]
        oversized = collection_result({total: 101})
        leaf = collection_result({field: [group()], total: 1})
        with patch.object(activity, "query", side_effect=[oversized, leaf, leaf]) as query:
            rows = activity.collection(NOW - timedelta(days=10), NOW)
        self.assertEqual(len(rows), 2)
        self.assertEqual(query.call_count, 3)

    def test_daily_oversized_result_is_an_explicit_failure(self):
        _, total, _ = activity.KINDS[0]
        with patch.object(activity, "query", return_value=collection_result({total: 101})):
            with self.assertRaisesRegex(ValueError, "within one day"):
                activity.collection(NOW, NOW)

    def test_repository_creation_overflow_is_not_silently_truncated(self):
        oversized = collection_result({"totalRepositoryContributions": 101})
        with patch.object(activity, "query", return_value=oversized):
            with self.assertRaisesRegex(ValueError, "within one day"):
                activity.collection(NOW, NOW)

    def test_contribution_years_govern_full_history(self):
        with patch.object(activity, "query", side_effect=[
                {"contributionsCollection": {"contributionYears": [2026, 2024, 2020, 2024]}},
                collection_result(), collection_result(), collection_result(),
                collection_result(), collection_result()]) as query:
            result = activity.collect(NOW)
        self.assertEqual(result["entries"], [])
        periods = [call.kwargs for call in query.call_args_list[1:]]
        self.assertEqual(len(periods), 5)  # 2020 and 2024 are leap years.
        self.assertEqual({datetime.fromisoformat(p["from"]).year for p in periods},
                         {2020, 2024, 2026})
        self.assertEqual(result["updated_at"], NOW.isoformat())

    def test_snapshot_output_escapes_repository_metadata(self):
        html = activity.render({"updated_at": NOW.isoformat(),
                                "entries": [record(label="Code push")]})
        self.assertIn("Commit · Python", html)
        self.assertNotIn("Code push", html)
        row = activity.contribution(repo(), "2026-11-01T00:00:00Z", "Issue")
        html = activity.render({"updated_at": NOW.isoformat(), "entries": [row]})
        self.assertIn("&lt;Safe project&gt;", html)
        self.assertNotIn("<Safe project>", html)

    def test_graphql_error_is_not_published_as_incomplete_success(self):
        with patch.object(activity, "urlopen") as urlopen, \
             patch.dict("os.environ", {"GITHUB_TOKEN": "dummy"}):
            from unittest.mock import MagicMock
            response = MagicMock()
            response.__enter__.return_value = response
            response.read.return_value = json.dumps({"errors": [{"message": "Access denied"}]}).encode()
            urlopen.return_value = response
            with self.assertRaisesRegex(ValueError, "Access denied"):
                activity.query(activity.YEARS_QUERY, login=activity.USER)

    def test_snapshot_load_is_local_and_keeps_older_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "contributions.json"
            data = {"updated_at": NOW.isoformat(), "entries": [record()]}
            with patch.object(activity, "SNAPSHOT", path):
                self.assertIsNone(activity.load_snapshot())
                path.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(activity.load_snapshot(), data)

    def test_failed_explicit_refresh_does_not_overwrite_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            page = root / "_site/index.html"
            source = activity.START + "fallback" + activity.END
            page.write_text(source, encoding="utf-8")
            cache = root / "_site/contributions.json"
            original = {"updated_at": "2026-11-01T00:00:00Z",
                        "entries": [record()]}
            cache.write_text(json.dumps(original), encoding="utf-8")
            with patch.object(activity, "ROOT", root), \
                 patch.object(activity, "SNAPSHOT", cache), \
                 patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}), \
                 patch.object(activity, "collect", side_effect=URLError("offline")), \
                 patch("sys.argv", ["sync_activity.py", "--refresh"]):
                with self.assertRaisesRegex(RuntimeError, "refresh failed"):
                    activity.main()
            self.assertEqual(json.loads(cache.read_text(encoding="utf-8")), original)
            self.assertEqual(page.read_text(encoding="utf-8"), source)

    def test_missing_token_keeps_homepage_fallback_for_local_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            page = root / "_site/index.html"
            source = activity.START + "fallback" + activity.END
            page.write_text(source, encoding="utf-8")
            with patch.object(activity, "ROOT", root), \
                 patch.object(activity, "SNAPSHOT", root / "_site/contributions.json"), \
                 patch.dict("os.environ", {}, clear=True), \
                 patch("sys.argv", ["sync_activity.py"]):
                activity.main()
            self.assertEqual(page.read_text(encoding="utf-8"), source)

    def test_explicit_refresh_requires_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_site").mkdir()
            (root / "_site/index.html").write_text(
                activity.START + "fallback" + activity.END, encoding="utf-8")
            with patch.object(activity, "ROOT", root), \
                 patch.object(activity, "SNAPSHOT", root / "_site/contributions.json"), \
                 patch.dict("os.environ", {}, clear=True), \
                 patch("sys.argv", ["sync_activity.py", "--refresh"]):
                with self.assertRaisesRegex(ValueError, "GITHUB_TOKEN"):
                    activity.main()


if __name__ == "__main__":
    unittest.main()

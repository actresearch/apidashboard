import pathlib
import unittest

import app as dashboard_app


class UsageStatsSnapshotTests(unittest.TestCase):
    def test_build_usage_snapshot_payload_groups_dimensions(self):
        payload = dashboard_app.build_usage_snapshot_payload(
            [
                {
                    "dimension": "api_name",
                    "name": "Freight Forecast",
                    "call_count": 12,
                    "window_start": "2026-05-27T00:00:00Z",
                    "window_end": "2026-06-26T00:00:00Z",
                    "refreshed_at": "2026-06-26T06:05:00Z",
                },
                {
                    "dimension": "product_id",
                    "name": "internal",
                    "call_count": 7,
                    "window_start": "2026-05-27T00:00:00Z",
                    "window_end": "2026-06-26T00:00:00Z",
                    "refreshed_at": "2026-06-26T06:05:00Z",
                },
            ]
        )

        self.assertEqual(payload["api_name_calls"], [{"name": "Freight Forecast", "count": 12}])
        self.assertEqual(payload["product_id_calls"], [{"name": "internal", "count": 7}])
        self.assertEqual(payload["refreshed_at"], "2026-06-26T06:05:00Z")

    def test_usage_stats_response_is_cacheable(self):
        original_url = dashboard_app.SUPABASE_URL
        original_key = dashboard_app.SUPABASE_SERVICE_ROLE_KEY
        original_fetch = dashboard_app.fetch_supabase_usage_snapshot

        dashboard_app.SUPABASE_URL = "https://example.supabase.co"
        dashboard_app.SUPABASE_SERVICE_ROLE_KEY = "test-key"
        dashboard_app.fetch_supabase_usage_snapshot = lambda: [
            {
                "dimension": "api_name",
                "name": "Freight Forecast",
                "call_count": 12,
                "window_start": "2026-05-27T00:00:00Z",
                "window_end": "2026-06-26T00:00:00Z",
                "refreshed_at": "2026-06-26T06:05:00Z",
            }
        ]

        try:
            client = dashboard_app.app.test_client()
            response = client.get("/api/usage_stats")
        finally:
            dashboard_app.SUPABASE_URL = original_url
            dashboard_app.SUPABASE_SERVICE_ROLE_KEY = original_key
            dashboard_app.fetch_supabase_usage_snapshot = original_fetch

        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=86400", response.headers["Cache-Control"])

    def test_dashboard_no_longer_queries_raw_log_table(self):
        app_source = pathlib.Path(__file__).with_name("app.py").read_text(encoding="utf-8")

        self.assertNotIn("/rest/v1/api_request_logs", app_source)
        self.assertNotIn("offset", app_source)
        self.assertNotIn("limit", app_source)


if __name__ == "__main__":
    unittest.main()

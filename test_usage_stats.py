import json
import pathlib
import tempfile
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

    def test_port_data_status_reads_status_file(self):
        original_path = dashboard_app.PORT_MONITOR_STATUS_PATH
        original_url = dashboard_app.PORT_MONITOR_STATUS_URL
        payload = {
            "generated_at_utc": "2026-08-25T12:00:00+00:00",
            "port_count": 1,
            "counts": {"ok": 1, "warning": 0, "error": 0, "other": 0},
            "ports": [{"port": "Savannah", "status": "ok"}],
        }

        with tempfile.TemporaryDirectory() as directory:
            status_path = pathlib.Path(directory) / "port_status.json"
            status_path.write_text(json.dumps(payload), encoding="utf-8")
            dashboard_app.PORT_MONITOR_STATUS_PATH = str(status_path)
            dashboard_app.PORT_MONITOR_STATUS_URL = ""

            try:
                client = dashboard_app.app.test_client()
                response = client.get("/api/port_data_status")
            finally:
                dashboard_app.PORT_MONITOR_STATUS_PATH = original_path
                dashboard_app.PORT_MONITOR_STATUS_URL = original_url

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["ports"][0]["port"], "Savannah")

    def test_port_data_status_post_requires_token(self):
        original_token = dashboard_app.PORT_MONITOR_STATUS_TOKEN
        dashboard_app.PORT_MONITOR_STATUS_TOKEN = ""

        try:
            client = dashboard_app.app.test_client()
            response = client.post("/api/port_data_status", json={"ports": []})
        finally:
            dashboard_app.PORT_MONITOR_STATUS_TOKEN = original_token

        self.assertEqual(response.status_code, 503)

    def test_port_data_status_post_saves_status_file(self):
        original_path = dashboard_app.PORT_MONITOR_STATUS_PATH
        original_token = dashboard_app.PORT_MONITOR_STATUS_TOKEN
        payload = {
            "generated_at_utc": "2026-08-25T12:00:00+00:00",
            "port_count": 1,
            "counts": {"ok": 1, "warning": 0, "error": 0, "other": 0},
            "ports": [{"port": "Houston", "status": "ok"}],
        }

        with tempfile.TemporaryDirectory() as directory:
            status_path = pathlib.Path(directory) / "port_status.json"
            dashboard_app.PORT_MONITOR_STATUS_PATH = str(status_path)
            dashboard_app.PORT_MONITOR_STATUS_TOKEN = "test-token"

            try:
                client = dashboard_app.app.test_client()
                unauthorized = client.post(
                    "/api/port_data_status",
                    json=payload,
                    headers={"X-Port-Monitor-Token": "wrong-token"},
                )
                response = client.post(
                    "/api/port_data_status",
                    json=payload,
                    headers={"X-Port-Monitor-Token": "test-token"},
                )
            finally:
                dashboard_app.PORT_MONITOR_STATUS_PATH = original_path
                dashboard_app.PORT_MONITOR_STATUS_TOKEN = original_token

            saved = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved["ports"][0]["port"], "Houston")


if __name__ == "__main__":
    unittest.main()

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

    def test_automation_status_lists_expected_missing_rows(self):
        original_dir = dashboard_app.AUTOMATION_STATUS_DIR
        original_paths = dashboard_app.AUTOMATION_STATUS_PATHS
        original_load_port = dashboard_app.load_port_monitor_status

        with tempfile.TemporaryDirectory() as directory:
            dashboard_app.AUTOMATION_STATUS_DIR = directory
            dashboard_app.AUTOMATION_STATUS_PATHS = ""
            dashboard_app.load_port_monitor_status = lambda: {
                "generated_at_utc": "2026-08-25T12:00:00Z",
                "counts": {"ok": 2, "warning": 1, "error": 0, "other": 0},
                "ports": [
                    {"port": "Savannah", "status": "ok", "last_successful_data_month": "2026-06", "last_data_pull_utc": "2026-08-25T12:00:00Z"}
                ],
            }

            try:
                client = dashboard_app.app.test_client()
                response = client.get("/api/automation_status")
            finally:
                dashboard_app.AUTOMATION_STATUS_DIR = original_dir
                dashboard_app.AUTOMATION_STATUS_PATHS = original_paths
                dashboard_app.load_port_monitor_status = original_load_port

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["counts"]["warning"], 1)
        self.assertTrue(any(item["automation_id"] == "diesel_prices" and item["status"] == "missing" for item in payload["automations"]))
        self.assertTrue(any(item["automation_id"] == "port_data_monitor" and item["status"] == "warning" for item in payload["automations"]))

    def test_automation_status_post_saves_status_file(self):
        original_dir = dashboard_app.AUTOMATION_STATUS_DIR
        original_token = dashboard_app.AUTOMATION_STATUS_TOKEN

        with tempfile.TemporaryDirectory() as directory:
            dashboard_app.AUTOMATION_STATUS_DIR = directory
            dashboard_app.AUTOMATION_STATUS_TOKEN = "test-token"

            try:
                client = dashboard_app.app.test_client()
                unauthorized = client.post(
                    "/api/automation_status",
                    json={"automation_id": "diesel_prices", "automation": "Diesel Prices", "status": "ok"},
                    headers={"Authorization": "Bearer wrong-token"},
                )
                response = client.post(
                    "/api/automation_status",
                    json={"automation_id": "diesel_prices", "automation": "Diesel Prices", "status": "ok"},
                    headers={"Authorization": "Bearer test-token"},
                )
            finally:
                dashboard_app.AUTOMATION_STATUS_DIR = original_dir
                dashboard_app.AUTOMATION_STATUS_TOKEN = original_token

            saved = json.loads((pathlib.Path(directory) / "diesel_prices.json").read_text(encoding="utf-8"))

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved["automation_id"], "diesel_prices")

    def test_automation_status_detail_reads_posted_payload(self):
        original_dir = dashboard_app.AUTOMATION_STATUS_DIR
        original_paths = dashboard_app.AUTOMATION_STATUS_PATHS
        original_load_port = dashboard_app.load_port_monitor_status

        with tempfile.TemporaryDirectory() as directory:
            status_path = pathlib.Path(directory) / "freightwaves_sonar.json"
            status_path.write_text(json.dumps({
                "automation_id": "freightwaves_sonar",
                "automation": "FreightWaves SONAR API",
                "status": "ok",
                "cadence": "weekly",
                "latest_data_period": "2026-08-25",
            }), encoding="utf-8")
            dashboard_app.AUTOMATION_STATUS_DIR = directory
            dashboard_app.AUTOMATION_STATUS_PATHS = ""
            dashboard_app.load_port_monitor_status = lambda: {"counts": {"ok": 0, "warning": 0, "error": 0, "other": 0}, "ports": []}

            try:
                client = dashboard_app.app.test_client()
                response = client.get("/api/automation_status/freightwaves_sonar")
            finally:
                dashboard_app.AUTOMATION_STATUS_DIR = original_dir
                dashboard_app.AUTOMATION_STATUS_PATHS = original_paths
                dashboard_app.load_port_monitor_status = original_load_port

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["latest_data_period"], "2026-08-25")

    def test_automation_control_fails_closed_when_not_configured(self):
        original_url = dashboard_app.AUTOMATION_CONTROL_URL
        original_control_token = dashboard_app.AUTOMATION_CONTROL_TOKEN
        original_operator_token = dashboard_app.AUTOMATION_OPERATOR_TOKEN
        dashboard_app.AUTOMATION_CONTROL_URL = ""
        dashboard_app.AUTOMATION_CONTROL_TOKEN = ""
        dashboard_app.AUTOMATION_OPERATOR_TOKEN = ""

        try:
            client = dashboard_app.app.test_client()
            response = client.post("/api/automation_control/diesel_prices/run")
        finally:
            dashboard_app.AUTOMATION_CONTROL_URL = original_url
            dashboard_app.AUTOMATION_CONTROL_TOKEN = original_control_token
            dashboard_app.AUTOMATION_OPERATOR_TOKEN = original_operator_token

        self.assertEqual(response.status_code, 503)

    def test_automation_control_requires_operator_token(self):
        original_url = dashboard_app.AUTOMATION_CONTROL_URL
        original_control_token = dashboard_app.AUTOMATION_CONTROL_TOKEN
        original_operator_token = dashboard_app.AUTOMATION_OPERATOR_TOKEN
        dashboard_app.AUTOMATION_CONTROL_URL = "http://127.0.0.1:5015"
        dashboard_app.AUTOMATION_CONTROL_TOKEN = "control-token"
        dashboard_app.AUTOMATION_OPERATOR_TOKEN = "operator-token"

        try:
            client = dashboard_app.app.test_client()
            response = client.post(
                "/api/automation_control/diesel_prices/run",
                headers={"X-Automation-Operator-Token": "wrong-token"},
            )
        finally:
            dashboard_app.AUTOMATION_CONTROL_URL = original_url
            dashboard_app.AUTOMATION_CONTROL_TOKEN = original_control_token
            dashboard_app.AUTOMATION_OPERATOR_TOKEN = original_operator_token

        self.assertEqual(response.status_code, 401)

    def test_stream_failure_classification_by_component(self):
        self.assertIsNone(dashboard_app.classify_stream_failure("api_testing", {"status": "HTTP 200"}))
        self.assertIsNone(dashboard_app.classify_stream_failure("api_testing", {"status": "PASS", "statusCode": 200}))
        self.assertIsNone(dashboard_app.classify_stream_failure("api_testing", {"ok": True, "status": "PASS"}))
        self.assertEqual(
            dashboard_app.classify_stream_failure("api_testing", {"status": "HTTP 500"}),
            "api_non_200",
        )
        self.assertEqual(
            dashboard_app.classify_stream_failure("api_testing", {"status": "FAIL", "statusCode": 404}),
            "api_non_200",
        )
        self.assertEqual(
            dashboard_app.classify_stream_failure("folder_monitor", {"status": "worker_health_failed"}),
            "folder_monitor_failure",
        )
        self.assertIsNone(dashboard_app.classify_stream_failure("folder_monitor", {"status": "modified_file"}))
        self.assertEqual(
            dashboard_app.classify_stream_failure("ftp_transfer", {"status": "not_authenticated"}),
            "ftp_failure",
        )
        self.assertIsNone(dashboard_app.classify_stream_failure("ftp_transfer", {"status": "script_ran"}))

    def test_zoom_notification_uses_low_detail_payload_and_dedupes(self):
        original_url = dashboard_app.DASHBOARD_ZOOM_WEBHOOK_URL
        original_token = dashboard_app.DASHBOARD_ZOOM_WEBHOOK_TOKEN
        original_cache = dashboard_app.ZOOM_NOTIFICATION_CACHE
        original_send = dashboard_app.send_zoom_fields_message
        sent = []

        dashboard_app.DASHBOARD_ZOOM_WEBHOOK_URL = "https://zoom.example/webhook"
        dashboard_app.DASHBOARD_ZOOM_WEBHOOK_TOKEN = "test-token"
        dashboard_app.ZOOM_NOTIFICATION_CACHE = {}
        dashboard_app.send_zoom_fields_message = lambda url, token, fields: sent.append(fields)

        try:
            first = dashboard_app.notify_dashboard_failure("api_non_200", "api_testing")
            second = dashboard_app.notify_dashboard_failure("api_non_200", "api_testing")
        finally:
            dashboard_app.DASHBOARD_ZOOM_WEBHOOK_URL = original_url
            dashboard_app.DASHBOARD_ZOOM_WEBHOOK_TOKEN = original_token
            dashboard_app.ZOOM_NOTIFICATION_CACHE = original_cache
            dashboard_app.send_zoom_fields_message = original_send

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["Alert"], "API Dashboard failure")
        self.assertEqual(sent[0]["Component"], "api_testing")
        self.assertEqual(sent[0]["Reason"], "api_non_200")
        self.assertEqual(sent[0]["Detail"], "Check the API dashboard for details.")
        self.assertNotIn("url", sent[0])
        self.assertNotIn("path", sent[0])
        self.assertNotIn("file", sent[0])

    def test_zoom_alert_test_requires_operator_token_and_allow_list(self):
        original_operator_token = dashboard_app.AUTOMATION_OPERATOR_TOKEN
        original_url = dashboard_app.DASHBOARD_ZOOM_WEBHOOK_URL
        original_token = dashboard_app.DASHBOARD_ZOOM_WEBHOOK_TOKEN
        original_send = dashboard_app.send_zoom_fields_message
        sent = []

        dashboard_app.AUTOMATION_OPERATOR_TOKEN = "operator-token"
        dashboard_app.DASHBOARD_ZOOM_WEBHOOK_URL = "https://zoom.example/webhook"
        dashboard_app.DASHBOARD_ZOOM_WEBHOOK_TOKEN = "test-token"
        dashboard_app.send_zoom_fields_message = lambda url, token, fields: sent.append(fields)

        try:
            client = dashboard_app.app.test_client()
            unauthorized = client.post("/api/zoom_alert_test/api_testing")
            unsupported = client.post(
                "/api/zoom_alert_test/raw_path",
                headers={"X-Automation-Operator-Token": "operator-token"},
            )
            response = client.post(
                "/api/zoom_alert_test/api_testing",
                headers={"X-Automation-Operator-Token": "operator-token"},
            )
        finally:
            dashboard_app.AUTOMATION_OPERATOR_TOKEN = original_operator_token
            dashboard_app.DASHBOARD_ZOOM_WEBHOOK_URL = original_url
            dashboard_app.DASHBOARD_ZOOM_WEBHOOK_TOKEN = original_token
            dashboard_app.send_zoom_fields_message = original_send

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unsupported.status_code, 400)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "sent")
        self.assertEqual(sent[0]["Component"], "api_testing")
        self.assertEqual(sent[0]["Reason"], "api_non_200_test")


if __name__ == "__main__":
    unittest.main()

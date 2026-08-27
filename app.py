import os
import json
import glob
import re
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, render_template, jsonify, make_response, request, stream_with_context

app = Flask(__name__)
API_HEALTH_STREAM_URL = os.getenv(
    "API_HEALTH_STREAM_URL",
    "http://192.168.1.17:5002/stream",
)
WATCHDOG_STREAM_URL = os.getenv(
    "WATCHDOG_STREAM_URL",
    "http://192.168.1.17:8001/stream",
)
FTP_STREAM_URL = os.getenv(
    "FTP_STREAM_URL",
    "http://192.168.1.17:5000/stream",
)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_USAGE_SNAPSHOT_TABLE = os.getenv(
    "SUPABASE_USAGE_SNAPSHOT_TABLE",
    "api_usage_stats_snapshot",
)
USAGE_STATS_CACHE_SECONDS = int(os.getenv("USAGE_STATS_CACHE_SECONDS", "86400"))
PORT_MONITOR_STATUS_PATH = os.getenv(
    "PORT_MONITOR_STATUS_PATH",
    "/app/logs/Major US Port Data Monitor.status.json",
)
PORT_MONITOR_STATUS_URL = os.getenv("PORT_MONITOR_STATUS_URL")
PORT_MONITOR_STATUS_TOKEN = os.getenv("PORT_MONITOR_STATUS_TOKEN", "")
AUTOMATION_STATUS_DIR = os.getenv("AUTOMATION_STATUS_DIR", "/app/logs/automations")
AUTOMATION_STATUS_PATHS = os.getenv("AUTOMATION_STATUS_PATHS", "")
AUTOMATION_STATUS_TOKEN = os.getenv("AUTOMATION_STATUS_TOKEN", "")
AUTOMATION_CONTROL_URL = os.getenv("AUTOMATION_CONTROL_URL", "")
AUTOMATION_CONTROL_TOKEN = os.getenv("AUTOMATION_CONTROL_TOKEN", "")
AUTOMATION_OPERATOR_TOKEN = os.getenv("AUTOMATION_OPERATOR_TOKEN", "")
EXPECTED_AUTOMATIONS = [
    {"automation_id": "port_data_monitor", "automation": "Major Port Data Monitor", "cadence": "daily", "detail_url": "/ports"},
    {"automation_id": "aar_weekly_rail", "automation": "AAR Weekly Rail Feed", "cadence": "weekly"},
    {"automation_id": "diesel_prices", "automation": "Diesel Prices EIA Collection", "cadence": "daily"},
    {"automation_id": "ata_reports", "automation": "ATA Reports", "cadence": "daily"},
    {"automation_id": "bts_transborder", "automation": "BTS TransBorder Raw Data", "cadence": "daily"},
    {"automation_id": "freightwaves_sonar", "automation": "FreightWaves SONAR API", "cadence": "weekly"},
]

@app.route('/')
def dashboard():
    return render_template('index.html')


@app.route('/ports')
def ports_dashboard():
    return render_template('ports.html')


@app.route('/automations/<automation_id>')
def automation_detail(automation_id):
    return render_template('automation_detail.html', automation_id=automation_id)


@app.route('/api/automation_control/<automation_id>/<action>', methods=['POST'])
def automation_control(automation_id, action):
    if action not in {"open-location", "run"}:
        return jsonify({"error": "Unsupported automation control action"}), 400
    if not AUTOMATION_CONTROL_URL or not AUTOMATION_CONTROL_TOKEN or not AUTOMATION_OPERATOR_TOKEN:
        return jsonify({
            "error": "Automation control is not configured",
            "setup_hint": (
                "Set AUTOMATION_CONTROL_URL, AUTOMATION_CONTROL_TOKEN, and "
                "AUTOMATION_OPERATOR_TOKEN for the dashboard service."
            ),
        }), 503

    provided = request.headers.get("X-Automation-Operator-Token", "")
    if provided != AUTOMATION_OPERATOR_TOKEN:
        return jsonify({"error": "Invalid automation operator token"}), 401

    target_url = (
        f"{AUTOMATION_CONTROL_URL.rstrip('/')}/automations/"
        f"{urllib.parse.quote(automation_id)}/{action}"
    )
    proxy_request = urllib.request.Request(
        target_url,
        method="POST",
        data=b"{}",
        headers={
            "Authorization": f"Bearer {AUTOMATION_CONTROL_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ACT-API-Dashboard/1.0",
        },
    )
    try:
        with urllib.request.urlopen(proxy_request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
            return jsonify(payload), response.status
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8") or "{}")
        except Exception:
            payload = {"error": str(e)}
        return jsonify(payload), e.code
    except Exception as e:
        return jsonify({
            "error": "Unable to reach automation control agent",
            "detail": str(e),
        }), 502


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/api-health/stream')
def api_health_stream():
    return stream_proxy(API_HEALTH_STREAM_URL)


@app.route('/watchdog/stream')
def watchdog_stream():
    return stream_proxy(WATCHDOG_STREAM_URL)


@app.route('/ftp/stream')
def ftp_stream():
    return stream_proxy(FTP_STREAM_URL)


def stream_proxy(upstream_url):
    def relay_stream():
        while True:
            try:
                with urllib.request.urlopen(upstream_url, timeout=70) as upstream:
                    for line in upstream:
                        yield line
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                message = str(e).replace("\n", " ")
                yield f"event: error\ndata: {message}\n\n".encode("utf-8")

    return Response(
        stream_with_context(relay_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

@app.route('/api/usage_stats')
def api_usage_stats():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return jsonify({
            "error": "Supabase environment variables are not configured",
            "setup_hint": "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for the dashboard service.",
        }), 500

    try:
        rows = fetch_supabase_usage_snapshot()
    except Exception as e:
        return jsonify({
            "error": "Unable to load Supabase usage stats",
            "detail": str(e),
            "snapshot_table": SUPABASE_USAGE_SNAPSHOT_TABLE,
            "setup_hint": (
                "Apply api_usage_stats_snapshot.sql in Supabase, run "
                "select public.refresh_api_usage_stats_snapshot();, then restart the dashboard."
            ),
        }), 502

    payload = build_usage_snapshot_payload(rows)
    response = make_response(jsonify(payload))
    response.headers["Cache-Control"] = (
        f"private, max-age={USAGE_STATS_CACHE_SECONDS}, "
        f"stale-while-revalidate={USAGE_STATS_CACHE_SECONDS}"
    )
    return response


@app.route('/api/port_data_status', methods=['GET', 'POST'])
def port_data_status():
    if request.method == 'POST':
        return receive_port_monitor_status()
    try:
        return jsonify(load_port_monitor_status())
    except FileNotFoundError:
        return jsonify({
            "error": "Port monitor status file not found",
            "status_path": PORT_MONITOR_STATUS_PATH,
            "setup_hint": "Set PORT_MONITOR_STATUS_PATH to the mounted Major US Port Data Monitor.status.json path.",
            "ports": [],
            "counts": {"ok": 0, "warning": 0, "error": 0, "other": 0},
        }), 404
    except Exception as e:
        return jsonify({
            "error": "Unable to load port monitor status",
            "detail": str(e),
            "status_path": PORT_MONITOR_STATUS_PATH,
            "ports": [],
            "counts": {"ok": 0, "warning": 0, "error": 0, "other": 0},
        }), 502


@app.route('/api/automation_status', methods=['GET', 'POST'])
def automation_status():
    if request.method == 'POST':
        return receive_automation_status()
    try:
        return jsonify(load_automation_statuses())
    except Exception as e:
        return jsonify({
            "error": "Unable to load automation statuses",
            "detail": str(e),
            "automation_status_dir": AUTOMATION_STATUS_DIR,
            "automations": [],
            "counts": {"ok": 0, "warning": 0, "error": 0, "missing": 0, "other": 0},
        }), 502


@app.route('/api/automation_status/<automation_id>')
def automation_status_detail(automation_id):
    payload = load_automation_statuses(include_raw=True)
    for automation in payload.get("automations", []):
        if automation.get("automation_id") == automation_id:
            return jsonify(automation)
    return jsonify({
        "error": "Automation status not found",
        "automation_id": automation_id,
        "setup_hint": "Confirm the automation has posted status JSON or that AUTOMATION_STATUS_PATHS includes its status file.",
    }), 404


def receive_port_monitor_status():
    if not PORT_MONITOR_STATUS_TOKEN:
        return jsonify({
            "error": "Port monitor status posting is not configured",
            "setup_hint": "Set PORT_MONITOR_STATUS_TOKEN in the dashboard environment before accepting posted status updates.",
        }), 503
    provided_token = request.headers.get("X-Port-Monitor-Token", "")
    if provided_token != PORT_MONITOR_STATUS_TOKEN:
        return jsonify({"error": "Invalid port monitor status token"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object payload"}), 400
    payload = normalize_port_monitor_status(payload)

    directory = os.path.dirname(PORT_MONITOR_STATUS_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(PORT_MONITOR_STATUS_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return jsonify({
        "status": "saved",
        "status_path": PORT_MONITOR_STATUS_PATH,
        "port_count": len(payload.get("ports", [])),
    })


def receive_automation_status():
    if not AUTOMATION_STATUS_TOKEN:
        return jsonify({
            "error": "Automation status posting is not configured",
            "setup_hint": "Set AUTOMATION_STATUS_TOKEN in the dashboard environment before accepting posted automation updates.",
        }), 503

    provided_token = request.headers.get("Authorization", "")
    expected_token = f"Bearer {AUTOMATION_STATUS_TOKEN}"
    if provided_token != expected_token and request.headers.get("X-Automation-Status-Token", "") != AUTOMATION_STATUS_TOKEN:
        return jsonify({"error": "Invalid automation status token"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object payload"}), 400

    automation_id = payload.get("automation_id")
    if not automation_id:
        return jsonify({"error": "automation_id is required"}), 400

    normalized = normalize_automation_status(payload)
    os.makedirs(AUTOMATION_STATUS_DIR, exist_ok=True)
    status_path = os.path.join(AUTOMATION_STATUS_DIR, f"{safe_status_filename(automation_id)}.json")
    with open(status_path, "w", encoding="utf-8") as handle:
        json.dump(normalized.get("raw", payload), handle, indent=2, ensure_ascii=False)

    return jsonify({
        "status": "saved",
        "automation_id": automation_id,
        "status_path": status_path,
    })


def load_port_monitor_status():
    if PORT_MONITOR_STATUS_URL:
        request = urllib.request.Request(
            PORT_MONITOR_STATUS_URL,
            headers={"Accept": "application/json", "User-Agent": "ACT-API-Dashboard/1.0"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return normalize_port_monitor_status(json.loads(response.read().decode("utf-8")))
    with open(PORT_MONITOR_STATUS_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return normalize_port_monitor_status(payload)


def normalize_port_monitor_status(payload):
    payload.setdefault("ports", [])
    payload.setdefault("counts", {"ok": 0, "warning": 0, "error": 0, "other": 0})
    return payload


def load_automation_statuses(include_raw=False):
    statuses = {}
    load_errors = []

    try:
        port_payload = load_port_monitor_status()
        statuses["port_data_monitor"] = normalize_port_status_as_automation(port_payload, include_raw=include_raw)
    except Exception as e:
        load_errors.append({"path": PORT_MONITOR_STATUS_PATH, "error": str(e)})

    for status_path in automation_status_paths():
        try:
            with open(status_path, "r", encoding="utf-8") as handle:
                normalized = normalize_automation_status(json.load(handle), include_raw=include_raw)
                automation_id = normalized.get("automation_id")
                if automation_id:
                    statuses[automation_id] = normalized
        except FileNotFoundError:
            continue
        except Exception as e:
            load_errors.append({"path": status_path, "error": str(e)})

    for expected in EXPECTED_AUTOMATIONS:
        automation_id = expected["automation_id"]
        if automation_id not in statuses:
            statuses[automation_id] = normalize_missing_automation(expected)

    automations = sorted(
        statuses.values(),
        key=lambda item: (status_sort_order(item.get("status")), item.get("automation", "")),
    )
    counts = {"ok": 0, "warning": 0, "error": 0, "missing": 0, "other": 0}
    for item in automations:
        status = item.get("status", "other")
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1

    return {
        "generated_at_utc": dashboard_utc_now(),
        "automation_count": len(automations),
        "counts": counts,
        "load_errors": load_errors,
        "automations": automations,
    }


def automation_status_paths():
    paths = []
    if AUTOMATION_STATUS_DIR:
        paths.extend(glob.glob(os.path.join(AUTOMATION_STATUS_DIR, "*.json")))
    if AUTOMATION_STATUS_PATHS:
        paths.extend(path for path in AUTOMATION_STATUS_PATHS.split(os.pathsep) if path)
    return list(dict.fromkeys(paths))


def normalize_automation_status(payload, include_raw=False):
    automation_id = payload.get("automation_id") or payload.get("id") or "unknown"
    status = normalize_status_value(payload.get("status"))
    failure_count = int(payload.get("failure_count") or 0)
    warning_count = int(payload.get("warning_count") or 0)
    if failure_count > 0:
        status = "error"
    elif warning_count > 0 and status == "ok":
        status = "warning"

    raw_indicators = [
        payload.get("failure_detail"),
        payload.get("warning_detail"),
        payload.get("pending_detail"),
        payload.get("latest_data_period"),
        payload.get("last_success_utc"),
        payload.get("new_rows"),
        payload.get("new_files"),
    ]
    indicators = [str(value) for value in raw_indicators if value not in (None, "")]

    normalized = {
        "automation_id": automation_id,
        "automation": payload.get("automation") or title_from_id(automation_id),
        "cadence": payload.get("cadence") or "unknown",
        "status": status,
        "last_run_utc": payload.get("last_run_utc") or payload.get("finished_utc") or payload.get("generated_at_utc"),
        "last_success_utc": payload.get("last_success_utc"),
        "latest_data_period": payload.get("latest_data_period"),
        "failure_count": failure_count,
        "failure_detail": payload.get("failure_detail") or "",
        "warning_count": warning_count,
        "warning_detail": payload.get("warning_detail") or "",
        "new_rows": payload.get("new_rows"),
        "new_files": payload.get("new_files"),
        "output_path": payload.get("output_path"),
        "detail_url": payload.get("detail_url") or f"/automations/{automation_id}",
        "control_enabled": automation_control_configured(),
        "indicators": indicators[:3],
        "raw": payload if include_raw else None,
    }
    if not include_raw:
        normalized.pop("raw", None)
    return normalized


def normalize_missing_automation(expected):
    return {
        "automation_id": expected["automation_id"],
        "automation": expected["automation"],
        "cadence": expected.get("cadence", "unknown"),
        "status": "missing",
        "last_run_utc": None,
        "last_success_utc": None,
        "latest_data_period": None,
        "failure_count": 0,
        "failure_detail": "",
        "warning_count": 0,
        "warning_detail": "No status JSON has been received.",
        "new_rows": None,
        "new_files": None,
        "output_path": None,
        "detail_url": expected.get("detail_url") or f"/automations/{expected['automation_id']}",
        "control_enabled": automation_control_configured(),
        "indicators": ["No status JSON has been received."],
    }


def normalize_port_status_as_automation(payload, include_raw=False):
    counts = payload.get("counts", {})
    error_count = int(counts.get("error") or 0)
    warning_count = int(counts.get("warning") or 0)
    if error_count:
        status = "error"
    elif warning_count:
        status = "warning"
    else:
        status = "ok"

    ports = payload.get("ports", [])
    latest_months = [port.get("last_successful_data_month") for port in ports if port.get("last_successful_data_month")]
    last_pulls = [port.get("last_data_pull_utc") for port in ports if port.get("last_data_pull_utc")]
    failure_details = [f"{port.get('port')}: {port.get('failure_detail')}" for port in ports if port.get("failure_detail")]
    latest_period = max(latest_months) if latest_months else None
    last_run = max(last_pulls) if last_pulls else payload.get("generated_at_utc")
    indicators = [
        f"{counts.get('ok', 0)} ports OK",
        f"{warning_count} warnings",
        f"{error_count} failures",
    ]

    normalized = {
        "automation_id": "port_data_monitor",
        "automation": "Major Port Data Monitor",
        "cadence": "daily",
        "status": status,
        "last_run_utc": last_run,
        "last_success_utc": last_run if status == "ok" else None,
        "latest_data_period": latest_period,
        "failure_count": error_count,
        "failure_detail": "; ".join(failure_details),
        "warning_count": warning_count,
        "warning_detail": "",
        "new_rows": None,
        "new_files": None,
        "output_path": payload.get("output_path"),
        "detail_url": "/ports",
        "control_enabled": automation_control_configured(),
        "indicators": indicators,
        "raw": payload if include_raw else None,
    }
    if not include_raw:
        normalized.pop("raw", None)
    return normalized


def normalize_status_value(status):
    status = str(status or "unknown").lower()
    if status in {"ok", "success", "healthy"}:
        return "ok"
    if status in {"warning", "partial"}:
        return "warning"
    if status in {"error", "failed", "failure"}:
        return "error"
    if status == "missing":
        return "missing"
    return "other"


def automation_control_configured():
    return bool(AUTOMATION_CONTROL_URL and AUTOMATION_CONTROL_TOKEN and AUTOMATION_OPERATOR_TOKEN)


def status_sort_order(status):
    return {"error": 0, "missing": 1, "warning": 2, "other": 3, "ok": 4}.get(status, 5)


def safe_status_filename(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._") or "unknown"


def title_from_id(value):
    return str(value).replace("_", " ").title()


def dashboard_utc_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_supabase_usage_snapshot():
    query = urllib.parse.urlencode(
        {
            "select": "dimension,name,call_count,window_start,window_end,refreshed_at",
            "order": "call_count.desc,name.asc",
        }
    )
    snapshot_table = urllib.parse.quote(SUPABASE_USAGE_SNAPSHOT_TABLE.strip("/"), safe="")
    request = urllib.request.Request(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/{snapshot_table}?{query}",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase REST returned HTTP {e.code}: {body}") from e


def build_usage_snapshot_payload(rows):
    api_name_calls = []
    product_id_calls = []
    refreshed_at = None
    window_start = None
    window_end = None

    for row in rows:
        item = {
            "name": row.get("name"),
            "count": row.get("call_count", 0),
        }

        dimension = row.get("dimension")
        if dimension == "api_name":
            api_name_calls.append(item)
        elif dimension == "product_id":
            product_id_calls.append(item)

        refreshed_at = refreshed_at or row.get("refreshed_at")
        window_start = window_start or row.get("window_start")
        window_end = window_end or row.get("window_end")

    return {
        "api_name_calls": api_name_calls,
        "product_id_calls": product_id_calls,
        "refreshed_at": refreshed_at,
        "window_start": window_start,
        "window_end": window_end,
    }

if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        threaded=True,
        port=int(os.getenv("APP_PORT", "5005")),
    )

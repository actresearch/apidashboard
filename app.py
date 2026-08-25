import os
import json
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, render_template, jsonify, make_response, stream_with_context

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

@app.route('/')
def dashboard():
    return render_template('index.html')


@app.route('/ports')
def ports_dashboard():
    return render_template('ports.html')


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


@app.route('/api/port_data_status')
def port_data_status():
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

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

@app.route('/')
def dashboard():
    return render_template('index.html')


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
        return jsonify({"error": "Supabase environment variables are not configured"}), 500

    try:
        rows = fetch_supabase_usage_snapshot()
    except Exception as e:
        return jsonify({"error": f"Unable to load Supabase usage stats: {e}"}), 502

    payload = build_usage_snapshot_payload(rows)
    response = make_response(jsonify(payload))
    response.headers["Cache-Control"] = (
        f"private, max-age={USAGE_STATS_CACHE_SECONDS}, "
        f"stale-while-revalidate={USAGE_STATS_CACHE_SECONDS}"
    )
    return response


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

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


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

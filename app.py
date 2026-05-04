import os
import json
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, render_template, jsonify, stream_with_context
from datetime import datetime, timedelta

app = Flask(__name__)
API_HEALTH_STREAM_URL = os.getenv(
    "API_HEALTH_STREAM_URL",
    "http://192.168.1.17:5002/stream",
)
WATCHDOG_STREAM_URL = os.getenv(
    "WATCHDOG_STREAM_URL",
    "http://192.168.1.17:8001/stream",
)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_LOG_TIMESTAMP_COLUMN = os.getenv("SUPABASE_LOG_TIMESTAMP_COLUMN", "created_at")
SUPABASE_PAGE_SIZE = int(os.getenv("SUPABASE_PAGE_SIZE", "1000"))

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

    start_date = (datetime.utcnow() - timedelta(days=30)).isoformat(timespec="seconds") + "Z"

    try:
        rows = fetch_supabase_usage_rows(start_date)
    except Exception as e:
        return jsonify({"error": f"Unable to load Supabase usage stats: {e}"}), 502

    return jsonify({
        "api_name_calls": rank_counts(rows, "api_name", "(missing api_name)"),
        "product_id_calls": rank_counts(rows, "product_id", "(missing product_id)"),
    })


def fetch_supabase_usage_rows(start_date):
    rows = []
    offset = 0

    while True:
        batch = fetch_supabase_usage_page(start_date, offset, SUPABASE_PAGE_SIZE)
        rows.extend(batch)

        if len(batch) < SUPABASE_PAGE_SIZE:
            return rows

        offset += SUPABASE_PAGE_SIZE


def fetch_supabase_usage_page(start_date, offset, limit):
    query = urllib.parse.urlencode({
        "select": "api_name,product_id",
        SUPABASE_LOG_TIMESTAMP_COLUMN: f"gte.{start_date}",
        "order": f"{SUPABASE_LOG_TIMESTAMP_COLUMN}.desc",
        "offset": str(offset),
        "limit": str(limit),
    })
    request = urllib.request.Request(
        f"{SUPABASE_URL.rstrip('/')}/rest/v1/api_request_logs?{query}",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def rank_counts(rows, field, missing_label):
    counts = {}
    for row in rows:
        key = row.get(field) or missing_label
        counts[key] = counts.get(key, 0) + 1

    return [
        {"name": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]

if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        threaded=True,
        port=int(os.getenv("APP_PORT", "5005")),
    )

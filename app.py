import os

from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# Dummy in-memory log for demonstration (replace with your real data source)
api_call_log = [
    # Example: {"timestamp": datetime(2025, 7, 1, 12, 0), "api_key": "abc123", "product": "ProductA"}
]

@app.route('/')
def dashboard():
    return render_template('index.html')


@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/usage_stats')
def api_usage_stats():
    """
    Returns API usage stats for the last 30 days, grouped by day and API key/product.
    Example output:
    {
      "stats": [
        {"date": "2025-07-01", "api_key": "abc123", "product": "ProductA", "count": 42},
        ...
      ]
    }
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=30)
    # Filter log for last 30 days
    filtered = [entry for entry in api_call_log if entry["timestamp"] >= start_date]
    # Aggregate
    stats = {}
    for entry in filtered:
        day = entry["timestamp"].strftime("%Y-%m-%d")
        key = (day, entry["api_key"], entry.get("product", ""))
        stats.setdefault(key, 0)
        stats[key] += 1
    # Format for output
    result = [
        {"date": k[0], "api_key": k[1], "product": k[2], "count": v}
        for k, v in stats.items()
    ]
    return jsonify({"stats": result})

if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
        threaded=True,
        port=int(os.getenv("APP_PORT", "5005")),
    )
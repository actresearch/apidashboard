# API Monitoring Dashboard

A real-time API monitoring dashboard built with Flask and modern web technologies.

## Features

- **Real-time API Analytics**: Monitor API calls, error rates, and performance metrics
- **Interactive Charts**: Visualize hourly API calls and traffic sources using Chart.js
- **Live Streaming Data**: Real-time updates for API health, watchdog activity, and FTP automations
- **Responsive Design**: Modern UI built with Tailwind CSS
- **24-hour and 30-day Analytics**: Comprehensive usage statistics and trends
- **Efficient API Usage Snapshot**: 30-day Supabase usage rankings are read from a small daily aggregate instead of raw log rows

## Dashboard Components

### Summary Cards
- Total API Calls (24h)
- API Error Rate (24h) 
- Average Response Time (24h)
- Hourly Calls Chart (Last 12h)
- Traffic Source Distribution (24h)

### Live Streaming Sections
- **📡 API Health**: Real-time endpoint status monitoring
- **👁 Watchdog Activity**: File system monitoring and heartbeat tracking
- **📤 FTP Automations**: FTP authentication and script execution monitoring

### Analytics
- **📊 API Usage Stats**: Top API consumers over the last 30 days

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, JavaScript (ES6+), Tailwind CSS
- **Charts**: Chart.js
- **Real-time Communication**: Server-Sent Events (SSE)
- **Dependencies**: Flask-SSE, Flask-Cors, Redis

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd API_Dashboard
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open your browser and navigate to `http://localhost:5005`

## Configuration

The dashboard connects to various API endpoints for data:
- API insights: `http://192.168.1.17:5003/api/insights`
- Error monitoring: `http://192.168.1.17:5003/api/error_rate`
- Performance metrics: `http://192.168.1.17:5003/api/performance`
- Traffic analytics: `http://192.168.1.17:5003/api/traffic`
- Usage statistics: local `/api/usage_stats`, backed by Supabase `api_usage_stats_snapshot`

Update these endpoints in `templates/index.html` to match your API configuration.

### Supabase usage snapshot setup

The usage rankings should update no more than once per day. Do not point the dashboard at raw `api_request_logs` rows; that causes high Supabase egress as the table grows.

1. Apply [api_usage_stats_snapshot.sql](api_usage_stats_snapshot.sql) in the Supabase SQL Editor or your normal migration process.
2. Run the initial refresh:
   ```sql
   select public.refresh_api_usage_stats_snapshot();
   ```
3. Schedule the same refresh once daily. The SQL file includes an optional `pg_cron` snippet for `06:05 UTC`.
4. Configure the dashboard with:
   ```bash
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   SUPABASE_USAGE_SNAPSHOT_TABLE=api_usage_stats_snapshot
   USAGE_STATS_CACHE_SECONDS=86400
   ```

## Features Overview

- **Auto-refresh**: Data refreshes every 10 minutes automatically
- **Usage stats caching**: 30-day usage rankings load from the daily Supabase snapshot once per page load
- **Manual refresh**: Click the refresh button for immediate updates
- **Responsive design**: Works on desktop and mobile devices
- **Real-time streaming**: Live updates without page refresh
- **Error handling**: Graceful handling of API failures

## License

This project is part of ACT Research's API monitoring infrastructure.

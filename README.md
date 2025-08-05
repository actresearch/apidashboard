# API Monitoring Dashboard

A real-time API monitoring dashboard built with Flask and modern web technologies.

## Features

- **Real-time API Analytics**: Monitor API calls, error rates, and performance metrics
- **Interactive Charts**: Visualize hourly API calls and traffic sources using Chart.js
- **Live Streaming Data**: Real-time updates for API health, watchdog activity, and FTP automations
- **Responsive Design**: Modern UI built with Tailwind CSS
- **24-hour and 30-day Analytics**: Comprehensive usage statistics and trends

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
- Usage statistics: `http://192.168.1.17:5003/api/usage_stats`

Update these endpoints in `templates/index.html` to match your API configuration.

## Features Overview

- **Auto-refresh**: Data refreshes every 10 minutes automatically
- **Manual refresh**: Click the refresh button for immediate updates
- **Responsive design**: Works on desktop and mobile devices
- **Real-time streaming**: Live updates without page refresh
- **Error handling**: Graceful handling of API failures

## License

This project is part of ACT Research's API monitoring infrastructure.

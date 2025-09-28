"""
Web-based dashboard server for real-time monitoring.

This module provides a Flask-based web server for real-time instrument
and test monitoring with WebSocket support for live updates.
"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
from pydantic import BaseModel, Field

from hal.logging_config import get_logger
from .metrics_collector import MetricsCollector


class DashboardConfig(BaseModel):
    """Configuration for dashboard server."""

    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=5000, description="Server port")
    debug: bool = Field(default=False, description="Enable debug mode")
    update_interval_ms: int = Field(default=1000, description="Update interval in milliseconds")
    max_data_points: int = Field(default=100, description="Maximum data points to display")
    enable_cors: bool = Field(default=True, description="Enable CORS for API access")


class DashboardServer:
    """Real-time monitoring dashboard server."""

    def __init__(self, metrics_collector: MetricsCollector, config: DashboardConfig):
        """Initialize dashboard server."""
        self.metrics_collector = metrics_collector
        self.config = config
        self.logger = get_logger(__name__)

        # Flask app setup
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'hal-monitoring-dashboard'

        # SocketIO setup
        cors_allowed_origins = "*" if config.enable_cors else None
        self.socketio = SocketIO(self.app, cors_allowed_origins=cors_allowed_origins)

        # Setup routes
        self._setup_routes()
        self._setup_socketio_handlers()

        # Background update thread
        self._update_thread = None
        self._stop_updates = threading.Event()

    def _setup_routes(self) -> None:
        """Setup Flask routes."""

        @self.app.route('/')
        def dashboard():
            """Main dashboard page."""
            return render_template_string(self._get_dashboard_template())

        @self.app.route('/api/metrics')
        def get_metrics():
            """Get recent metrics."""
            count = request.args.get('count', self.config.max_data_points, type=int)
            source = request.args.get('source')
            name = request.args.get('name')

            metrics = self.metrics_collector.get_metrics(
                name=name,
                source=source,
                count=count
            )

            return jsonify({
                "metrics": [m.to_dict() for m in metrics],
                "count": len(metrics),
                "timestamp": datetime.utcnow().isoformat()
            })

        @self.app.route('/api/instruments')
        def get_instruments():
            """Get list of active instruments."""
            recent_metrics = self.metrics_collector.get_metrics(count=1000)

            # Extract unique instrument sources
            instruments = set()
            for metric in recent_metrics:
                if metric.tags.get("type") == "instrument":
                    instruments.add(metric.source)

            instrument_status = {}
            for instrument_id in instruments:
                instrument_status[instrument_id] = self.metrics_collector.get_instrument_status(instrument_id)

            return jsonify({
                "instruments": list(instruments),
                "status": instrument_status,
                "timestamp": datetime.utcnow().isoformat()
            })

        @self.app.route('/api/system/health')
        def get_system_health():
            """Get system health metrics."""
            health = self.metrics_collector.get_system_health()
            return jsonify(health)

        @self.app.route('/api/metrics/<metric_name>/summary')
        def get_metric_summary(metric_name: str):
            """Get statistical summary for a metric."""
            duration = request.args.get('duration', 60, type=int)
            summary = self.metrics_collector.get_metric_summary(metric_name, duration)
            return jsonify(summary)

    def _setup_socketio_handlers(self) -> None:
        """Setup SocketIO event handlers."""

        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            self.logger.info(f"Dashboard client connected: {request.sid}")
            emit('status', {'connected': True, 'timestamp': datetime.utcnow().isoformat()})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            self.logger.info(f"Dashboard client disconnected: {request.sid}")

        @self.socketio.on('subscribe_metrics')
        def handle_subscribe_metrics(data):
            """Handle metric subscription request."""
            metric_names = data.get('metrics', [])
            self.logger.info(f"Client {request.sid} subscribed to metrics: {metric_names}")

        @self.socketio.on('get_instrument_status')
        def handle_get_instrument_status(data):
            """Handle instrument status request."""
            instrument_id = data.get('instrument_id')
            if instrument_id:
                status = self.metrics_collector.get_instrument_status(instrument_id)
                emit('instrument_status', {
                    'instrument_id': instrument_id,
                    'status': status
                })

    def start(self) -> None:
        """Start the dashboard server."""
        self.logger.info(f"Starting dashboard server on {self.config.host}:{self.config.port}")

        # Start background update thread
        self._start_update_thread()

        # Start Flask-SocketIO server
        self.socketio.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            debug=self.config.debug
        )

    def stop(self) -> None:
        """Stop the dashboard server."""
        self._stop_updates.set()
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=5)

        self.logger.info("Dashboard server stopped")

    def _start_update_thread(self) -> None:
        """Start background thread for real-time updates."""
        self._update_thread = threading.Thread(
            target=self._update_worker,
            daemon=True,
            name="DashboardUpdates"
        )
        self._update_thread.start()

    def _update_worker(self) -> None:
        """Background worker for pushing real-time updates."""
        while not self._stop_updates.wait(self.config.update_interval_ms / 1000.0):
            try:
                # Get recent metrics
                recent_metrics = self.metrics_collector.get_metrics(count=10)

                if recent_metrics:
                    # Emit metrics update
                    self.socketio.emit('metrics_update', {
                        'metrics': [m.to_dict() for m in recent_metrics],
                        'timestamp': datetime.utcnow().isoformat()
                    })

                # Get system health
                health = self.metrics_collector.get_system_health()
                self.socketio.emit('system_health', health)

            except Exception as e:
                self.logger.error(f"Error in dashboard update worker: {e}")

    def _get_dashboard_template(self) -> str:
        """Get HTML template for dashboard."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Electronics HAL - Real-time Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .card h3 {
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
        }

        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-connected { background-color: #4CAF50; }
        .status-disconnected { background-color: #f44336; }
        .status-warning { background-color: #ff9800; }

        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #2196F3;
            text-align: center;
            margin: 10px 0;
        }

        .metric-unit {
            font-size: 0.8em;
            color: #666;
        }

        .chart-container {
            height: 300px;
            margin-top: 15px;
        }

        .instrument-list {
            list-style: none;
            padding: 0;
        }

        .instrument-item {
            display: flex;
            align-items: center;
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
        }

        .log-messages {
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.9em;
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
        }

        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
        }

        .connected { background-color: #4CAF50; }
        .disconnected { background-color: #f44336; }
    </style>
</head>
<body>
    <div id="connectionStatus" class="connection-status disconnected">Connecting...</div>

    <div class="header">
        <h1>📊 Electronics HAL Dashboard</h1>
        <p>Real-time Instrument and Test Monitoring</p>
    </div>

    <div class="grid">
        <div class="card">
            <h3>📈 System Health</h3>
            <div id="systemHealth">Loading...</div>
        </div>

        <div class="card">
            <h3>🔧 Active Instruments</h3>
            <ul id="instrumentList" class="instrument-list">
                <li>Loading instruments...</li>
            </ul>
        </div>

        <div class="card">
            <h3>📊 Metrics Overview</h3>
            <div id="metricsChart" class="chart-container"></div>
        </div>

        <div class="card">
            <h3>📝 Live Activity Log</h3>
            <div id="activityLog" class="log-messages">Connecting to live feed...</div>
        </div>
    </div>

    <script>
        // Initialize Socket.IO connection
        const socket = io();

        // Connection status
        const statusElement = document.getElementById('connectionStatus');

        socket.on('connect', () => {
            statusElement.textContent = 'Connected';
            statusElement.className = 'connection-status connected';
            addLogMessage('Connected to HAL monitoring system');
        });

        socket.on('disconnect', () => {
            statusElement.textContent = 'Disconnected';
            statusElement.className = 'connection-status disconnected';
            addLogMessage('Disconnected from monitoring system');
        });

        // System health updates
        socket.on('system_health', (data) => {
            updateSystemHealth(data);
        });

        // Metrics updates
        socket.on('metrics_update', (data) => {
            updateMetricsChart(data.metrics);
            addLogMessage(`Received ${data.metrics.length} new metrics`);
        });

        // Functions
        function updateSystemHealth(health) {
            const container = document.getElementById('systemHealth');
            container.innerHTML = `
                <div class="metric-value">
                    ${health.active_sources} <span class="metric-unit">sources</span>
                </div>
                <p>📊 ${health.total_metrics_5min} metrics in last 5 minutes</p>
                <p>💾 Buffer: ${(health.buffer_utilization * 100).toFixed(1)}% full</p>
                <p>🕒 Last update: ${new Date(health.timestamp).toLocaleTimeString()}</p>
            `;
        }

        function updateInstruments() {
            fetch('/api/instruments')
                .then(response => response.json())
                .then(data => {
                    const list = document.getElementById('instrumentList');
                    list.innerHTML = '';

                    if (data.instruments.length === 0) {
                        list.innerHTML = '<li>No active instruments</li>';
                        return;
                    }

                    data.instruments.forEach(instrument => {
                        const status = data.status[instrument];
                        const li = document.createElement('li');
                        li.className = 'instrument-item';
                        li.innerHTML = `
                            <span class="status-indicator status-connected"></span>
                            <strong>${instrument}</strong>
                            <div style="margin-left: auto; font-size: 0.9em; color: #666;">
                                ${status.last_activity ? new Date(status.last_activity).toLocaleTimeString() : 'No data'}
                            </div>
                        `;
                        list.appendChild(li);
                    });
                });
        }

        let metricsData = [];

        function updateMetricsChart(newMetrics) {
            // Add new metrics to data
            newMetrics.forEach(metric => {
                if (typeof metric.value === 'number') {
                    metricsData.push({
                        x: new Date(metric.timestamp),
                        y: metric.value,
                        name: metric.name,
                        source: metric.source
                    });
                }
            });

            // Keep only recent data (last 100 points)
            if (metricsData.length > 100) {
                metricsData = metricsData.slice(-100);
            }

            // Group by metric name
            const traces = {};
            metricsData.forEach(point => {
                if (!traces[point.name]) {
                    traces[point.name] = {
                        x: [],
                        y: [],
                        name: point.name,
                        type: 'scatter',
                        mode: 'lines+markers',
                        line: { width: 2 }
                    };
                }
                traces[point.name].x.push(point.x);
                traces[point.name].y.push(point.y);
            });

            const layout = {
                title: 'Real-time Metrics',
                xaxis: { title: 'Time' },
                yaxis: { title: 'Value' },
                height: 250,
                margin: { t: 30, r: 30, b: 40, l: 50 }
            };

            Plotly.newPlot('metricsChart', Object.values(traces), layout, {responsive: true});
        }

        function addLogMessage(message) {
            const log = document.getElementById('activityLog');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = `[${timestamp}] ${message}\\n`;
            log.textContent += logEntry;
            log.scrollTop = log.scrollHeight;

            // Keep only last 50 lines
            const lines = log.textContent.split('\\n');
            if (lines.length > 50) {
                log.textContent = lines.slice(-50).join('\\n');
            }
        }

        // Initialize
        updateInstruments();
        setInterval(updateInstruments, 5000); // Update every 5 seconds

        // Subscribe to metrics
        socket.emit('subscribe_metrics', {
            metrics: ['instrument.*', 'test.*', 'system.*']
        });
    </script>
</body>
</html>
        '''
#!/usr/bin/env python3
"""
TP357S Bluetooth Dashboard
Polls sensors every 30 seconds and serves web dashboard
"""

import asyncio
import struct
import json
import time
from datetime import datetime, timedelta
from bleak import BleakClient
from flask import Flask, render_template, jsonify
import threading
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TP357SMonitor:
    def __init__(self):
        # Configuration
        self.config = {
            'polling_interval_seconds': 30,
            'connection_timeout': 10,
            'web_port': 5000
        }
        
        self.sensors = {
            "Colonisation Box": "E5:35:C4:81:8D:8C",
            "Fruiting Bucket": "C1:92:D2:5A:72:3E"
        }
        
        # Data storage
        self.latest_data = {}
        self.last_updated = {}
        
        # Web app
        self.app = Flask(__name__)
        self.setup_routes()
        
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')
        
        @self.app.route('/api/data')
        def get_data():
            response_data = {}
            for name in self.sensors:
                if name in self.latest_data:
                    response_data[name] = {
                        **self.latest_data[name],
                        'last_updated': self.last_updated[name].isoformat() if name in self.last_updated else None,
                        'status': 'online' if name in self.last_updated and 
                                 (datetime.now() - self.last_updated[name]).seconds < 60 else 'offline'
                    }
                else:
                    response_data[name] = {
                        'temperature_c': None,
                        'temperature_f': None,
                        'humidity': None,
                        'status': 'offline',
                        'last_updated': None
                    }
            return jsonify(response_data)
    
    def parse_tp357s_data(self, data):
        """Parse TP357S data format: Byte 3 = temp*10, Byte 5 = humidity"""
        if len(data) >= 6:
            # Temperature in Celsius (byte 3 divided by 10)
            temp_c = data[3] / 10.0
            # Convert to Fahrenheit
            temp_f = (temp_c * 9/5) + 32
            # Humidity percentage (byte 5)
            humidity = data[5]
            
            return {
                'temperature_c': round(temp_c, 1),
                'temperature_f': round(temp_f, 1),
                'humidity': humidity,
                'raw_data': data.hex()
            }
        return None
    
    async def read_sensor_once(self, name, mac_address):
        """Read data from a single sensor and disconnect immediately"""
        try:
            logger.info(f"Connecting to {name}...")
            async with BleakClient(mac_address, timeout=self.config['connection_timeout']) as client:
                if not client.is_connected:
                    logger.warning(f"Failed to connect to {name}")
                    return False
                
                logger.info(f"Connected to {name}, reading data...")
                
                # Try to read from the real-time characteristic
                realtime_uuid = "00010203-0405-0607-0809-0a0b0c0d2b10"
                
                try:
                    data = await client.read_gatt_char(realtime_uuid)
                    if data and len(data) >= 6:
                        parsed = self.parse_tp357s_data(data)
                        if parsed:
                            self.latest_data[name] = parsed
                            self.last_updated[name] = datetime.now()
                            logger.info(f"{name}: {parsed['temperature_c']}°C, {parsed['humidity']}%")
                            return True
                except Exception as e:
                    logger.warning(f"Failed to read from {name} realtime characteristic: {e}")
                
                # Try notification approach if direct read didn't work
                notification_uuid = "8ec90001-f315-4f60-9fb8-838830daea50"
                data_received = False
                
                def notification_handler(sender, data):
                    nonlocal data_received
                    parsed = self.parse_tp357s_data(data)
                    if parsed:
                        self.latest_data[name] = parsed
                        self.last_updated[name] = datetime.now()
                        logger.info(f"{name}: {parsed['temperature_c']}°C, {parsed['humidity']}%")
                        data_received = True
                
                try:
                    await client.start_notify(notification_uuid, notification_handler)
                    # Wait briefly for notifications
                    for _ in range(10):
                        if data_received:
                            break
                        await asyncio.sleep(0.5)
                    await client.stop_notify(notification_uuid)
                    
                    if data_received:
                        return True
                        
                except Exception as e:
                    logger.warning(f"Failed to get notifications from {name}: {e}")
                
                logger.warning(f"No data received from {name}")
                return False
                
        except Exception as e:
            logger.error(f"Error reading {name}: {e}")
            return False
    
    async def poll_sensors(self):
        """Poll all sensors sequentially"""
        while True:
            start_time = time.time()
            logger.info("Starting sensor polling cycle...")
            
            for name, mac_address in self.sensors.items():
                success = await self.read_sensor_once(name, mac_address)
                if not success:
                    logger.warning(f"Failed to read from {name}")
                
                # Brief pause between sensors
                await asyncio.sleep(2)
            
            # Calculate how long to wait before next cycle
            elapsed = time.time() - start_time
            wait_time = max(0, self.config['polling_interval_seconds'] - elapsed)
            
            if wait_time > 0:
                logger.info(f"Polling cycle complete, waiting {wait_time:.1f}s until next cycle...")
                await asyncio.sleep(wait_time)
            else:
                logger.info("Polling cycle took longer than interval, starting next cycle immediately")
    
    def run_web_server(self):
        """Run the Flask web server"""
        self.app.run(host='0.0.0.0', port=self.config['web_port'], debug=False)
    
    def start_monitoring(self):
        """Start the monitoring system"""
        # Create templates directory and file
        import os
        os.makedirs('templates', exist_ok=True)
        
        # Create HTML template with new design
        html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Environmental Monitoring Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
        :root {
            /* Material Design Dark Theme */
            --bg-primary: #121212;
            --bg-secondary: #1e1e1e;
            --bg-elevated: #242424;
            --bg-surface: #2d2d2d;
            --text-primary: #ffffff;
            --text-secondary: #b3b3b3;
            --text-muted: #808080;
            --border-light: #333333;
            --border-medium: #404040;
            --accent-blue: #2196f3;
            --accent-blue-light: #64b5f6;
            --accent-green: #00e676;
            --accent-green-light: #4caf50;
            --accent-teal: #00acc1;
            --accent-cyan: #00bcd4;
            --accent-orange: #ff9800;
            --accent-red: #f44336;
            --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
            --elevation-1: 0 1px 3px rgba(0, 0, 0, 0.2);
            --elevation-2: 0 2px 6px rgba(0, 0, 0, 0.3);
            --elevation-3: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: var(--bg-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            font-weight: 400;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 24px;
        }
        
        .header {
            background: var(--bg-elevated);
            border-bottom: 1px solid var(--border-light);
            padding: 24px 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--elevation-2);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 22px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .logo::before {
            content: '●';
            color: var(--accent-blue);
            font-size: 24px;
        }
        
        .status-pill {
            background: linear-gradient(135deg, var(--accent-green), var(--accent-teal));
            color: #000000;
            padding: 8px 16px;
            border-radius: 24px;
            font-size: 13px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: var(--elevation-1);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            background: #000000;
            border-radius: 50%;
            animation: pulse-status 2s infinite;
        }
        
        @keyframes pulse-status {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .main {
            padding: 32px 0;
        }
        
        .sensor-group {
            margin-bottom: 48px;
        }
        
        .sensor-group-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid;
            border-image: linear-gradient(90deg, var(--accent-blue), var(--accent-green)) 1;
        }
        
        .sensor-group-title {
            font-size: 24px;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0;
        }
        
        .device-info-compact {
            display: flex;
            align-items: center;
            gap: 20px;
            font-size: 12px;
        }
        
        .device-info-item {
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--text-secondary);
        }
        
        .device-mac {
            font-family: 'Courier New', monospace;
            background: var(--bg-surface);
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid var(--border-light);
            color: var(--text-muted);
        }
        
        .device-status {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .device-status-dot {
            width: 6px;
            height: 6px;
            background: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 4px var(--accent-green);
        }
        
        .current-readings {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .current-card {
            background: linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-surface) 100%);
            border: 2px solid var(--accent-blue);
            border-radius: 20px;
            padding: 28px;
            text-align: center;
            box-shadow: var(--elevation-3), 0 0 20px rgba(33, 150, 243, 0.15);
            position: relative;
            overflow: hidden;
        }
        
        .current-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
            animation: pulse-gradient 3s ease-in-out infinite;
        }
        
        @keyframes pulse-gradient {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .current-value {
            font-size: 42px;
            font-weight: 300;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }
        
        .current-label {
            font-size: 12px;
            color: var(--text-primary);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        
        .current-sublabel {
            font-size: 10px;
            color: var(--accent-blue);
            font-weight: 500;
        }
        
        .offline {
            opacity: 0.5;
        }
        
        .offline .current-value {
            background: var(--text-muted);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 0 16px;
            }
            
            .header {
                padding: 16px 0;
            }
            
            .logo {
                font-size: 18px;
            }
            
            .status-pill {
                font-size: 11px;
                padding: 6px 12px;
            }
            
            .current-readings {
                grid-template-columns: 1fr;
                gap: 16px;
            }
            
            .current-value {
                font-size: 36px;
            }
            
            .sensor-group-title {
                font-size: 20px;
            }
            
            .sensor-group-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }
            
            .device-info-compact {
                flex-wrap: wrap;
                gap: 12px;
            }
            
            .main {
                padding: 24px 0;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div class="logo">Environmental Monitoring</div>
                <div class="status-pill">
                    <div class="status-dot"></div>
                    <span id="connection-status">Loading...</span>
                </div>
            </div>
        </div>
    </header>

    <main class="main">
        <div class="container" id="sensor-container">
            <!-- Sensor groups will be loaded here -->
        </div>
    </main>

    <script>
        function getStatusInfo(sensor) {
            if (sensor.status === 'offline') {
                return {
                    color: 'var(--accent-red)',
                    text: 'Offline'
                };
            }
            
            // Determine status based on humidity
            if (sensor.humidity !== null) {
                if (sensor.humidity < 50) {
                    return {
                        color: 'var(--accent-orange)',
                        text: 'Low Humidity'
                    };
                } else if (sensor.humidity > 80) {
                    return {
                        color: 'var(--accent-orange)',
                        text: 'High Humidity'
                    };
                } else {
                    return {
                        color: 'var(--accent-green)',
                        text: 'Normal Range'
                    };
                }
            }
            
            return {
                color: 'var(--accent-green)',
                text: 'Online'
            };
        }
        
        function getLastUpdatedText(lastUpdated) {
            if (!lastUpdated) return 'Never';
            
            const now = new Date();
            const updated = new Date(lastUpdated);
            const diffSeconds = Math.floor((now - updated) / 1000);
            
            if (diffSeconds < 60) {
                return `Updated ${diffSeconds}s ago`;
            } else if (diffSeconds < 3600) {
                return `Updated ${Math.floor(diffSeconds / 60)}m ago`;
            } else {
                return `Updated ${Math.floor(diffSeconds / 3600)}h ago`;
            }
        }
        
        async function updateData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                const container = document.getElementById('sensor-container');
                container.innerHTML = '';
                
                let onlineCount = 0;
                let totalCount = Object.keys(data).length;
                
                for (const [name, sensor] of Object.entries(data)) {
                    if (sensor.status === 'online') onlineCount++;
                    
                    const statusInfo = getStatusInfo(sensor);
                    const lastUpdatedText = getLastUpdatedText(sensor.last_updated);
                    
                    const sensorGroup = document.createElement('div');
                    sensorGroup.className = 'sensor-group';
                    
                    sensorGroup.innerHTML = `
                        <div class="sensor-group-header">
                            <h2 class="sensor-group-title">${name}</h2>
                            <div class="device-info-compact">
                                <div class="device-info-item">
                                    <span class="device-mac">${name === 'Colonisation Box' ? 'E5:35:C4:81:8D:8C' : 'C1:92:D2:5A:72:3E'}</span>
                                </div>
                                <div class="device-info-item">
                                    <div class="device-status">
                                        <div class="device-status-dot" style="background: ${statusInfo.color}; box-shadow: 0 0 4px ${statusInfo.color};"></div>
                                        <span style="color: ${statusInfo.color};">${statusInfo.text}</span>
                                    </div>
                                </div>
                                <div class="device-info-item">
                                    <span>${lastUpdatedText}</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="current-readings">
                            <div class="current-card ${sensor.status === 'offline' ? 'offline' : ''}">
                                <div class="current-label">LIVE TEMPERATURE</div>
                                <div class="current-value">${sensor.temperature_c ? sensor.temperature_c : '--'}°C</div>
                                <div class="current-sublabel">Real-time reading</div>
                            </div>
                            <div class="current-card ${sensor.status === 'offline' ? 'offline' : ''}">
                                <div class="current-label">LIVE HUMIDITY</div>
                                <div class="current-value">${sensor.humidity !== null ? sensor.humidity : '--'}%</div>
                                <div class="current-sublabel">Real-time reading</div>
                            </div>
                        </div>
                    `;
                    
                    container.appendChild(sensorGroup);
                }
                
                // Update connection status
                const connectionStatus = document.getElementById('connection-status');
                connectionStatus.textContent = `Connected • ${onlineCount}/${totalCount} Sensors • ${getUptimeText()}`;
                
            } catch (error) {
                console.error('Failed to update data:', error);
                const connectionStatus = document.getElementById('connection-status');
                connectionStatus.textContent = 'Connection Error';
            }
        }
        
        function getUptimeText() {
            // Simple uptime calculation (this would be better calculated server-side)
            const uptimeMs = performance.now();
            const uptimeSeconds = Math.floor(uptimeMs / 1000);
            const hours = Math.floor(uptimeSeconds / 3600);
            const minutes = Math.floor((uptimeSeconds % 3600) / 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            } else if (minutes > 0) {
                return `${minutes}m`;
            } else {
                return '<1m';
            }
        }
        
        // Update immediately and then every 10 seconds
        updateData();
        setInterval(updateData, 10000);
    </script>
</body>
</html>'''
        
        with open('templates/dashboard.html', 'w') as f:
            f.write(html_template)
        
        print("🌡️ TP357S Monitor Starting...")
        print(f"📊 Web dashboard: http://192.168.5.40:{self.config['web_port']}")
        print(f"⏰ Polling interval: {self.config['polling_interval_seconds']} seconds")
        print("📱 Phone app can be used between polling cycles")
        print("Press Ctrl+C to stop\n")
        
        # Start sensor polling in background
        def run_polling():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.poll_sensors())
        
        polling_thread = threading.Thread(target=run_polling, daemon=True)
        polling_thread.start()
        
        # Start web server (blocking)
        try:
            self.run_web_server()
        except KeyboardInterrupt:
            print("\n🛑 Monitor stopped by user")

def main():
    monitor = TP357SMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main()
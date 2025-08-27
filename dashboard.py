#!/usr/bin/env python3
"""
TP357S Bluetooth Dashboard
Polls sensors every 30 seconds and serves a web dashboard.
"""

import asyncio
import struct
from datetime import datetime
import threading
import logging
from flask import Flask, render_template_string, jsonify
from bleak import BleakClient

# --- Configuration ---
POLLING_INTERVAL_SECONDS = 30
CONNECTION_TIMEOUT = 15
WEB_PORT = 5000
SENSORS = {
    "Colonisation Bin": "E5:35:C4:81:8D:8C",
    "Fruiting Bucket": "C1:92:D2:5A:72:3E"
}
DATA_CHAR_UUID = "00010203-0405-0607-0809-0a0b0c0d2b10"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Data Storage ---
global_sensor_data = {}
historical_data = {}

# --- Flask App ---
app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    return jsonify(global_sensor_data)

@app.route('/api/history/<sensor_name>')
def get_history(sensor_name):
    """Get historical data for a specific sensor."""
    if sensor_name in historical_data:
        # Return last 24 hours of data (max 288 points at 5min intervals)
        recent_data = historical_data[sensor_name][-288:]
        return jsonify({
            'timestamps': [entry['timestamp'] for entry in recent_data],
            'temperatures': [entry['temperature_c'] for entry in recent_data],
            'humidity': [entry['humidity'] for entry in recent_data]
        })
    return jsonify({'timestamps': [], 'temperatures': [], 'humidity': []})

# --- Bluetooth Logic ---
def parse_tp357s_data(data):
    """Parses the 7-byte data from a TP357S sensor."""
    if not data or len(data) != 7:
        logger.warning(f"Invalid data received: {data.hex() if data else 'None'}")
        return None
    
    try:
        temp_c = data[3] / 10.0
        humidity = data[5]
        
        if -40 <= temp_c <= 85 and 0 <= humidity <= 100:
            return {
                'temperature_c': round(temp_c, 1),
                'temperature_f': round((temp_c * 9/5) + 32, 1),
                'humidity': round(humidity),
            }
        else:
            logger.warning(f"Parsed values out of range: temp={temp_c}, humidity={humidity}")
    except Exception as e:
        logger.error(f"Parse error: {e}")
    return None

async def read_sensor_once(name, address):
    """Connects to a sensor, gets one reading, and disconnects."""
    logger.info(f"Attempting to read from {name}...")
    client = None
    notification_started = False
    
    try:
        data_received = asyncio.Event()
        
        def notification_handler(sender, data):
            logger.info(f"Raw data from {name}: {data.hex()} (length: {len(data)})")
            parsed_data = parse_tp357s_data(data)
            if parsed_data:
                timestamp = datetime.now().isoformat()
                global_sensor_data[name] = {
                    **parsed_data,
                    'last_updated': timestamp,
                    'status': 'online'
                }
                
                # Store historical data
                if name not in historical_data:
                    historical_data[name] = []
                
                historical_data[name].append({
                    'timestamp': timestamp,
                    'temperature_c': parsed_data['temperature_c'],
                    'humidity': parsed_data['humidity']
                })
                
                # Keep only last 1000 readings (~8 hours at 30s intervals)
                if len(historical_data[name]) > 1000:
                    historical_data[name] = historical_data[name][-1000:]
                
                logger.info(f"SUCCESS: {name} - {parsed_data['temperature_c']}°C, {parsed_data['humidity']}% ")
                data_received.set()

        # Explicit connection management
        client = BleakClient(address, timeout=CONNECTION_TIMEOUT)
        logger.info(f"Connecting to {name}...")
        await client.connect()
        
        if not client.is_connected:
            logger.warning(f"Could not connect to {name}.")
            global_sensor_data[name] = {'status': 'offline', 'last_updated': datetime.now().isoformat()}
            return

        logger.info(f"Connected to {name}, starting notifications...")
        await client.start_notify(DATA_CHAR_UUID, notification_handler)
        notification_started = True
        
        try:
            await asyncio.wait_for(data_received.wait(), timeout=10)
            logger.info(f"Data received from {name}, disconnecting...")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for notification from {name}.")
            global_sensor_data[name] = {'status': 'timeout', 'last_updated': datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Error reading {name}: {e}")
        global_sensor_data[name] = {'status': 'error', 'last_updated': datetime.now().isoformat()}
    
    finally:
        # Ensure proper cleanup
        if client and client.is_connected:
            try:
                if notification_started:
                    logger.info(f"Stopping notifications for {name}...")
                    await client.stop_notify(DATA_CHAR_UUID)
                    await asyncio.sleep(0.5)  # Give time for cleanup
                
                logger.info(f"Disconnecting from {name}...")
                await client.disconnect()
                await asyncio.sleep(1)  # Force disconnect delay
                logger.info(f"Disconnected from {name}")
                
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup for {name}: {cleanup_error}")
        
        # Additional cleanup - try to clear any lingering connections
        try:
            if client:
                del client
        except:
            pass

async def polling_loop():
    """The main sensor polling loop."""
    while True:
        logger.info("--- Starting new polling cycle ---")
        for name, address in SENSORS.items():
            await read_sensor_once(name, address)
            await asyncio.sleep(2) # Stagger connections
        
        logger.info(f"--- Cycle complete, waiting {POLLING_INTERVAL_SECONDS} seconds ---")
        await asyncio.sleep(POLLING_INTERVAL_SECONDS)

# --- HTML Template ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Environmental Monitoring Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <style>
        :root {
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
            --accent-green: #00e676;
            --accent-teal: #00acc1;
            --accent-orange: #ff9800;
            --accent-red: #f44336;
            --elevation-1: 0 1px 3px rgba(0, 0, 0, 0.2);
            --elevation-2: 0 2px 6px rgba(0, 0, 0, 0.3);
            --elevation-3: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: var(--bg-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            font-weight: 400;
        }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 0 24px; }
        
        .header {
            background: var(--bg-elevated);
            border-bottom: 1px solid var(--border-light);
            padding: 24px 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--elevation-2);
        }
        
        .header-content { display: flex; justify-content: space-between; align-items: center; }
        
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
        
        @keyframes pulse-status { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        
        .main { padding: 32px 0; }
        
        .sensor-group { margin-bottom: 48px; }
        
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
            border-radius: 50%;
            box-shadow: 0 0 4px;
        }
        
        .device-status-dot.online {
            background: var(--accent-green);
            box-shadow: 0 0 4px var(--accent-green);
        }
        
        .device-status-dot.offline {
            background: var(--text-muted);
            box-shadow: 0 0 4px var(--text-muted);
        }
        
        .device-status-dot.error {
            background: var(--accent-red);
            box-shadow: 0 0 4px var(--accent-red);
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
        
        @keyframes pulse-gradient { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        
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
        
        .section-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--border-medium), transparent);
            margin: 32px 0;
            position: relative;
        }
        
        .section-divider::before {
            content: 'HISTORICAL DATA';
            position: absolute;
            top: -8px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--bg-primary);
            padding: 0 16px;
            font-size: 10px;
            color: var(--text-muted);
            font-weight: 600;
            letter-spacing: 1px;
        }
        
        .card {
            background: var(--bg-elevated);
            border: 1px solid var(--border-light);
            border-radius: 16px;
            padding: 28px;
            box-shadow: var(--elevation-2);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            margin-bottom: 24px;
        }
        
        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-light);
        }
        
        .card-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }
        
        .chart-container {
            height: 200px;
            position: relative;
        }
        
        @media (max-width: 768px) {
            .container { padding: 0 16px; }
            .header { padding: 16px 0; }
            .logo { font-size: 18px; }
            .status-pill { font-size: 11px; padding: 6px 12px; }
            .current-readings { grid-template-columns: 1fr; gap: 16px; }
            .current-value { font-size: 36px; }
            .sensor-group-title { font-size: 20px; }
            .sensor-group-header { flex-direction: column; align-items: flex-start; gap: 12px; }
            .device-info-compact { flex-wrap: wrap; gap: 12px; }
            .main { padding: 24px 0; }
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
                    <span id="header-status">Connected • Loading...</span>
                </div>
            </div>
        </div>
    </header>

    <main class="main">
        <div class="container" id="sensor-container">
            <!-- Sensor data will be loaded here -->
        </div>
    </main>

    <script>
        let sensorAddresses = {};
        
        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                const container = document.getElementById('sensor-container');
                const headerStatus = document.getElementById('header-status');
                
                container.innerHTML = '';
                
                const sensorCount = Object.keys(data).length;
                const onlineCount = Object.values(data).filter(s => s.status === 'online').length;
                headerStatus.textContent = `Connected • ${sensorCount} Sensors • ${onlineCount} Online`;
                
                for (const [name, sensor] of Object.entries(data)) {
                    const sensorGroup = document.createElement('div');
                    sensorGroup.className = 'sensor-group';
                    
                    let temp_c = (sensor.temperature_c !== null && sensor.temperature_c !== undefined) ? sensor.temperature_c.toFixed(1) : '--';
                    let humidity = (sensor.humidity !== null && sensor.humidity !== undefined) ? sensor.humidity.toFixed(0) : '--';
                    let last_updated = sensor.last_updated ? new Date(sensor.last_updated).toLocaleTimeString() : 'Never';
                    
                    let statusText = 'Offline';
                    let statusClass = 'offline';
                    if (sensor.status === 'online') {
                        statusText = 'Online';
                        statusClass = 'online';
                    } else if (sensor.status === 'error') {
                        statusText = 'Error';
                        statusClass = 'error';
                    } else if (sensor.status === 'timeout') {
                        statusText = 'Timeout';
                        statusClass = 'error';
                    }
                    
                    // Get MAC address from SENSORS config
                    let macAddress = 'Unknown';
                    if (name === 'Colonisation Bin') macAddress = 'E5:35:C4:81:8D:8C';
                    if (name === 'Fruiting Bucket') macAddress = 'C1:92:D2:5A:72:3E';
                    
                    sensorGroup.innerHTML = `
                        <div class="sensor-group-header">
                            <h2 class="sensor-group-title">${name}</h2>
                            <div class="device-info-compact">
                                <div class="device-info-item">
                                    <span class="device-mac">${macAddress}</span>
                                </div>
                                <div class="device-info-item">
                                    <div class="device-status">
                                        <div class="device-status-dot ${statusClass}"></div>
                                        <span style="color: var(--accent-${statusClass === 'online' ? 'green' : statusClass === 'error' ? 'red' : 'text-muted'});">${statusText}</span>
                                    </div>
                                </div>
                                <div class="device-info-item">
                                    <span>Updated ${last_updated}</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="current-readings">
                            <div class="current-card">
                                <div class="current-label">LIVE TEMPERATURE</div>
                                <div class="current-value">${temp_c}°C</div>
                                <div class="current-sublabel">Real-time reading</div>
                            </div>
                            <div class="current-card">
                                <div class="current-label">LIVE HUMIDITY</div>
                                <div class="current-value">${humidity}%</div>
                                <div class="current-sublabel">Real-time reading</div>
                            </div>
                        </div>
                        
                        <div class="section-divider"></div>
                        
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">Temperature History</div>
                            </div>
                            <div class="chart-container">
                                <canvas id="temp-chart-${name.replace(' ', '-').toLowerCase()}"></canvas>
                            </div>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                <div class="card-title">Humidity History</div>
                            </div>
                            <div class="chart-container">
                                <canvas id="humidity-chart-${name.replace(' ', '-').toLowerCase()}"></canvas>
                            </div>
                        </div>
                    `;
                    
                    container.appendChild(sensorGroup);
                    
                    // Create charts for this sensor
                    setTimeout(() => {
                        createCharts(name);
                    }, 100);
                }
            } catch (error) {
                console.error("Failed to fetch sensor data:", error);
                document.getElementById('header-status').textContent = 'Connection Error';
            }
        }
        
        async function createCharts(sensorName) {
            try {
                const response = await fetch(`/api/history/${encodeURIComponent(sensorName)}`);
                const historyData = await response.json();
                
                if (!historyData.timestamps || historyData.timestamps.length === 0) {
                    return; // No historical data yet
                }
                
                const chartId = sensorName.replace(' ', '-').toLowerCase();
                const tempCtx = document.getElementById(`temp-chart-${chartId}`);
                const humidCtx = document.getElementById(`humidity-chart-${chartId}`);
                
                if (!tempCtx || !humidCtx) return;
                
                const labels = historyData.timestamps.map(ts => {
                    const date = new Date(ts);
                    return date.toLocaleTimeString('en-US', { 
                        hour: '2-digit', 
                        minute: '2-digit' 
                    });
                });
                
                const chartOptions = {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            border: { display: false },
                            grid: { color: '#404040', drawTicks: false },
                            ticks: { 
                                color: '#b3b3b3', 
                                font: { size: 10 },
                                maxTicksLimit: 6
                            }
                        },
                        y: {
                            beginAtZero: false,
                            border: { display: false },
                            grid: { color: '#404040', drawTicks: false },
                            ticks: { 
                                color: '#b3b3b3', 
                                font: { size: 10 }
                            }
                        }
                    },
                    elements: {
                        point: { radius: 0, hoverRadius: 4 }
                    }
                };
                
                // Temperature Chart
                new Chart(tempCtx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: historyData.temperatures,
                            borderColor: '#2196f3',
                            backgroundColor: 'rgba(33, 150, 243, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: chartOptions
                });
                
                // Humidity Chart  
                new Chart(humidCtx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: historyData.humidity,
                            borderColor: '#00acc1',
                            backgroundColor: 'rgba(0, 172, 193, 0.1)', 
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: chartOptions
                });
                
            } catch (error) {
                console.error(`Failed to create charts for ${sensorName}:`, error);
            }
        }

        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
</body>
</html>
"""

# --- Main Execution ---
def run_async_loop():
    """Runs the asyncio event loop in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(polling_loop())

if __name__ == "__main__":
    logger.info("Starting ThermoPro Dashboard...")
    
    # Start the Bluetooth polling in a background thread
    polling_thread = threading.Thread(target=run_async_loop, daemon=True)
    polling_thread.start()
    
    # Start the Flask web server
    logger.info(f"Dashboard available at http://localhost:{WEB_PORT}")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)

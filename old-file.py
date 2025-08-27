#!/usr/bin/env python3
"""
TP357S Final Dashboard
Always-on web dashboard for your TP357S sensors
Temperature = Byte 3 / 10, Humidity = Byte 5
"""

from flask import Flask, render_template_string, jsonify
import asyncio
import threading
import time
from datetime import datetime
from bleak import BleakClient

app = Flask(__name__)

# Global data store
sensor_data = {}
connection_status = {}

class TP357SDashboard:
    def __init__(self):
        self.sensors = {
            "Living Room": "E5:35:C4:81:8D:8C",
            "Bedroom": "C1:92:D2:5A:72:3E"
        }
        
        # The characteristic that sends real-time data
        self.DATA_CHAR_UUID = "00010203-0405-0607-0809-0a0b0c0d2b10"
        self.running = False
        
    def parse_tp357s_data(self, data):
        """Parse TP357S data: Byte 3 = temp*10, Byte 5 = humidity"""
        if len(data) != 7:
            return None
            
        try:
            # Simple format: Byte 3 = temperature*10, Byte 5 = humidity%
            temp_c = data[3] / 10.0
            humidity = data[5]
            
            # Validate readings
            if -40 <= temp_c <= 85 and 0 <= humidity <= 100:
                return {
                    'temperature_c': temp_c,
                    'temperature_f': temp_c * 9/5 + 32,
                    'humidity': humidity,
                    'timestamp': datetime.now().isoformat(),
                    'raw_data': data.hex()
                }
                
        except Exception as e:
            print(f"Parse error: {e}")
            
        return None
    
    async def monitor_sensor(self, name, mac):
        """Monitor a single sensor continuously"""
        global sensor_data, connection_status
        
        while self.running:
            try:
                print(f"🔄 Connecting to {name}...")
                connection_status[name] = "Connecting"
                
                async with BleakClient(mac, timeout=15) as client:
                    print(f"✅ Connected to {name}")
                    connection_status[name] = "Connected"
                    
                    def notification_handler(sender, data):
                        parsed = self.parse_tp357s_data(data)
                        if parsed:
                            sensor_data[name] = parsed
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            print(f"📡 [{timestamp}] {name}: {parsed['temperature_c']:.1f}°C, {parsed['humidity']:.0f}%")
                    
                    # Set up notifications
                    await client.start_notify(self.DATA_CHAR_UUID, notification_handler)
                    
                    # Keep connection alive
                    while self.running:
                        await asyncio.sleep(1)
                        
            except Exception as e:
                print(f"❌ {name} error: {e}")
                connection_status[name] = f"Error: {e}"
                
                # Wait before reconnecting
                await asyncio.sleep(10)
    
    async def run_monitoring(self):
        """Run monitoring for all sensors"""
        self.running = True
        print("🌡️ Starting TP357S monitoring...")
        
        # Start monitoring each sensor in parallel
        tasks = []
        for name, mac in self.sensors.items():
            task = asyncio.create_task(self.monitor_sensor(name, mac))
            tasks.append(task)
        
        await asyncio.gather(*tasks)

# Create dashboard instance
dashboard = TP357SDashboard()

# HTML template for the web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TP357S Temperature Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            margin-bottom: 30px;
            font-size: 2.5em;
        }
        .status-bar {
            background: rgba(255,255,255,0.1);
            color: white;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .sensor-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
        }
        .sensor-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }
        .sensor-card:hover {
            transform: translateY(-5px);
        }
        .sensor-name {
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-bottom: 20px;
            text-align: center;
        }
        .temp-display {
            font-size: 64px;
            font-weight: bold;
            color: #e74c3c;
            text-align: center;
            margin: 25px 0;
            line-height: 1;
        }
        .temp-unit {
            font-size: 28px;
            color: #666;
            vertical-align: top;
        }
        .temp-fahrenheit {
            font-size: 20px;
            color: #999;
            text-align: center;
            margin: -10px 0 20px 0;
        }
        .humidity-display {
            font-size: 42px;
            font-weight: bold;
            color: #3498db;
            text-align: center;
            margin: 25px 0;
        }
        .humidity-icon {
            font-size: 24px;
            margin-right: 10px;
        }
        .last-update {
            font-size: 14px;
            color: #666;
            text-align: center;
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }
        .no-data {
            text-align: center;
            color: #999;
            font-style: italic;
            padding: 40px;
        }
        .connection-status {
            font-size: 12px;
            padding: 5px 10px;
            border-radius: 15px;
            display: inline-block;
            margin-top: 10px;
        }
        .status-connected {
            background: #2ecc71;
            color: white;
        }
        .status-error {
            background: #e74c3c;
            color: white;
        }
        .status-connecting {
            background: #f39c12;
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌡️ TP357S Dashboard</h1>
        
        <div class="status-bar">
            Last updated: {{ current_time }} | Active sensors: {{ active_count }}/{{ total_count }}
        </div>
        
        {% if sensor_data %}
        <div class="sensor-grid">
            {% for name, data in sensor_data.items() %}
            <div class="sensor-card">
                <div class="sensor-name">{{ name }}</div>
                <div class="temp-display">
                    {{ "%.1f"|format(data.temperature_c) }}<span class="temp-unit">°C</span>
                </div>
                <div class="temp-fahrenheit">
                    {{ "%.1f"|format(data.temperature_f) }}°F
                </div>
                <div class="humidity-display">
                    <span class="humidity-icon">💧</span>{{ "%.0f"|format(data.humidity) }}% RH
                </div>
                <div class="last-update">
                    Last reading: {{ data.timestamp.split('T')[1].split('.')[0] }}
                    <br>
                    <span class="connection-status status-connected">Connected</span>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="sensor-card">
            <div class="no-data">
                <h3>🔍 Connecting to sensors...</h3>
                <p>Make sure your TP357S sensors are powered on and not connected to the mobile app.</p>
                <p>This may take up to 30 seconds for the first connection.</p>
            </div>
        </div>
        {% endif %}
    </div>
    
    <script>
        // Auto-refresh every 10 seconds
        setTimeout(function() {
            window.location.reload();
        }, 10000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard_home():
    active_count = len([s for s in connection_status.values() if s == "Connected"])
    total_count = len(dashboard.sensors)
    
    return render_template_string(
        HTML_TEMPLATE,
        sensor_data=sensor_data,
        connection_status=connection_status,
        current_time=datetime.now().strftime('%H:%M:%S'),
        active_count=active_count,
        total_count=total_count
    )

@app.route('/api/sensors')
def api_sensors():
    return jsonify({
        'sensors': sensor_data,
        'status': connection_status,
        'timestamp': datetime.now().isoformat()
    })

def run_dashboard():
    """Run the async sensor monitoring in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(dashboard.run_monitoring())

if __name__ == "__main__":
    print("🌡️ TP357S Dashboard Starting...")
    print("Format: Temperature = Byte 3 ÷ 10, Humidity = Byte 5")
    print("Make sure sensors are not connected to the mobile app!")
    
    # Start the sensor monitoring in a separate thread
    sensor_thread = threading.Thread(target=run_dashboard, daemon=True)
    sensor_thread.start()
    
    # Give sensors a moment to start connecting
    time.sleep(2)
    
    # Start the Flask web server
    print(f"\n🌐 Dashboard available at:")
    print(f"   Local: http://localhost:5000")
    print(f"   Network: http://192.168.5.40:5000")
    print(f"\nPress Ctrl+C to stop\n")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
        dashboard.running = False
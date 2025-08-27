# Bluetooth Dashboard - TP357S Historical Data Explorer

## Setup
- Raspberry Pi: 192.168.5.40 (SSH: jay)
- Python dependencies: `pip install bleak asyncio`

## Usage
```bash
python dashboard.py
```

## Sensors
- Living Room: E5:35:C4:81:8D:8C
- Bedroom: C1:92:D2:5A:72:3E

We want to create a dashboard where we can monitor the temperature of our bluetooth temperature controllers and allow us to hit it externally over the internet. 
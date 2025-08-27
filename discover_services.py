
import asyncio
from bleak import BleakClient

async def main(address):
    print(f"Attempting to connect to {address}...")
    try:
        async with BleakClient(address) as client:
            if client.is_connected:
                print(f"Connected to {address}")
                for service in client.services:
                    print(f"  Service: {service.uuid} ({service.description})")
                    for char in service.characteristics:
                        print(f"    Characteristic: {char.uuid} ({char.description})")
                        for descriptor in char.descriptors:
                            print(f"      Descriptor: {descriptor.uuid} ({descriptor.handle})")
            else:
                print(f"Failed to connect to {address}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Replace with the MAC address of your sensor
    # Colonisation Box: E5:35:C4:81:8D:8C
    # Fruiting Bucket: C1:92:D2:5A:72:3E
    mac_address = "E5:35:C4:81:8D:8C"
    asyncio.run(main(mac_address))

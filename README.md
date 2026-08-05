# EEG BLE - Bluetooth Low Energy Module for EEG Devices

Cross-platform Bluetooth device abstraction layer for EEG neurofeedback hardware.

## Features

- **Simplified API**: 4 core operations - `search()`, `connect()`, `start()`, `stop()`
- **Cross-platform**: Windows, macOS, Linux via [bleak](https://bleak.readthedocs.io/)
- **Async/Await**: Native asyncio support
- **Hardware Support**: Dbay-EEG2, Dbay-EEGM, Dbay-EEGS

## Installation

```bash
pip install bleak
```

## Quick Start

```python
import asyncio
from ble import BLEWrapper

async def main():
    ble = BLEWrapper()

    # Search devices
    devices = await ble.search(timeout=15.0)
    print(f"Found {len(devices)} devices")

    # Connect
    await ble.connect("AA:BB:CC:DD:EE:30")

    # Register callbacks
    def on_data(channel, data):
        print(f"[{channel}] {data.hex()}")

    def on_metrics(focus, stress, fatigue, **kwargs):
        print(f"Focus: {focus}, Stress: {stress}")

    ble.on_data(on_data)
    ble.on_metrics(on_metrics)

    # Start receiving
    ble.start()
    await asyncio.sleep(30)

    # Stop
    ble.stop()
    await ble.destroy()

asyncio.run(main())
```

## CLI Testing

```bash
# Mock tests
python -m ble.test.test_wrapper

# Hardware tests (auto scan -> connect -> data -> disconnect)
python -m ble.test.hardware_test --duration 30
```

## API Reference

### BLEWrapper

| Method | Description |
|--------|-------------|
| `search(timeout=15.0)` | Scan for BLE devices |
| `connect(address)` | Connect to device |
| `start()` | Start data streaming |
| `stop()` | Stop data streaming |
| `on_data(callback)` | Register raw data callback |
| `on_metrics(callback)` | Register metrics callback |
| `destroy()` | Cleanup and disconnect |

### Callbacks

```python
# Raw data: (channel: str, data: bytearray)
def on_data(channel, data):
    print(f"[{channel}] {data.hex()}")

# Metrics: (focus, stress, fatigue, asy, delta, theta, alpha, beta, gamma)
def on_metrics(focus, stress, fatigue, **kwargs):
    print(f"Focus: {focus:.1f}")
```

## License

MIT

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
| `search(timeout=15.0)` | Scan for BLE devices, returns list of dicts with name/address/rssi |
| `connect(address)` | Connect to device by MAC address |
| `start()` | Start data streaming (requires connected device) |
| `stop()` | Stop data streaming |
| `on_data(callback)` | Register raw data callback |
| `on_metrics(callback)` | Register metrics callback |
| `destroy()` | Cleanup and disconnect |

### Callbacks

#### Raw Data Callback
```python
def on_data(channel: str, data: bytearray):
    """
    channel: str - Data channel ("EEG", "RSP", "ALG")
    data: bytearray - Raw bytes from BLE characteristic
    """
    print(f"[{channel}] {data.hex()}")
```

#### Metrics Callback
```python
def on_metrics(
    focus: float,    # Focus level (0-100)
    stress: float,   # Stress index (0-100)
    fatigue: float,  # Fatigue level (0-100)
    **kwargs         # Extended metrics
):
    """
    Core metrics:
    - focus: float   - Focus/attention level (0-100)
    - stress: float - Stress index (0-100)
    - fatigue: float - Fatigue level (0-100)

    Extended metrics (in kwargs):
    - asy: float     - Left-right brain asymmetry index (-1 to 1)
    - delta: float   - Delta band power (0.5-4 Hz)
    - theta: float   - Theta band power (4-8 Hz)
    - alpha: float   - Alpha band power (8-13 Hz)
    - beta: float    - Beta band power (13-30 Hz)
    - gamma: float   - Gamma band power (30-100 Hz)
    """
    print(f"Focus: {focus:.1f}, Stress: {stress:.1f}, Fatigue: {fatigue:.1f}")
    print(f"Brain waves: δ={kwargs.get('delta',0):.1f} "
          f"θ={kwargs.get('theta',0):.1f} "
          f"α={kwargs.get('alpha',0):.1f} "
          f"β={kwargs.get('beta',0):.1f} "
          f"γ={kwargs.get('gamma',0):.1f}")
    print(f"Asymmetry: {kwargs.get('asy', 0):.3f}")
```

### Device Search Result Format

```python
devices = await ble.search(timeout=15.0)
# Returns:
[
    {
        "name": "Dbay-EEG2",           # Device name (may be None)
        "address": "AA:BB:CC:DD:EE:30", # MAC address
        "rssi": -65,                    # Signal strength in dBm
        "raw": {                        # Raw data from BLE scanner
            "address_type": "random",
            "details": {}
        }
    },
    ...
]
```

## Device Types

| Type | Description |
|------|-------------|
| `Dbay-EEG2` | Standard dual-channel EEG (default) |
| `Dbay-EEGM` | Mid-range version |
| `Dbay-EEGS` | Fabric firmware version |

## License

MIT

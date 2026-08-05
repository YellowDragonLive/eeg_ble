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

    def on_metrics(metrics):
        print(f"Focus: {metrics.focus}, Stress: {metrics.stress}, Fatigue: {metrics.fatigue}")
        print(f"Brain waves: δ={metrics.delta:.1f} θ={metrics.theta:.1f} "
              f"α={metrics.alpha:.1f} β={metrics.beta:.1f} γ={metrics.gamma:.1f}")
        print(f"Asymmetry: {metrics.asy:.3f}")

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
from ble import SignalMetrics

def on_metrics(metrics: SignalMetrics):
    """
    metrics: SignalMetrics - All brain metrics in one object

    Core metrics (0-100):
    - metrics.focus: float   - Focus/attention level
    - metrics.stress: float  - Stress index
    - metrics.fatigue: float - Fatigue level

    Extended metrics:
    - metrics.asy: float     - Left-right brain asymmetry (-1 to 1)
    - metrics.delta: float   - Delta band power (0.5-4 Hz)
    - metrics.theta: float   - Theta band power (4-8 Hz)
    - metrics.alpha: float   - Alpha band power (8-13 Hz)
    - metrics.beta: float    - Beta band power (13-30 Hz)
    - metrics.gamma: float   - Gamma band power (30-100 Hz)
    """
    print(f"Focus: {metrics.focus:.1f}, Stress: {metrics.stress:.1f}, Fatigue: {metrics.fatigue:.1f}")
    print(f"Brain waves: δ={metrics.delta:.1f} θ={metrics.theta:.1f} "
          f"α={metrics.alpha:.1f} β={metrics.beta:.1f} γ={metrics.gamma:.1f}")
    print(f"Asymmetry: {metrics.asy:.3f}")
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

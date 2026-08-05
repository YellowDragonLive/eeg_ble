"""BLE module: Cross-platform Bluetooth device abstraction layer.

================================================================================
Overview
================================================================================

This module provides unified hardware abstraction interfaces for BLE operations,
enabling different platform implementations to follow the same contract:

    Desktop (Windows/Mac/Linux)  ->  bleak library implementation
    Mobile Android               ->  React Native / Flutter implementation
    Mobile iOS                   ->  React Native / Flutter implementation

Business layer code only needs to use HardwareDevice class.

================================================================================
Module Structure
================================================================================

ble/
├── __init__.py          # Module entry, exports public API
├── interfaces.py        # Core protocol definitions (Protocol)
├── exceptions.py        # Unified exception classes
├── device.py            # Hardware device abstraction (business layer uses this)
└── impl/                # Platform implementations
    ├── __init__.py
    └── bleak_adapter.py  # bleak (desktop) adapter

================================================================================
Quick Start
================================================================================

```python
import asyncio
from ble import HardwareDevice

async def main():
    # Create device instance (address hardcoded for device ending in 3430)
    device = HardwareDevice(
        address="AA:BB:CC:DD:EE:30",
        name="Dbay-EEG2",
        device_type="Dbay-EEG2"
    )

    # Use context manager for automatic connect/disconnect
    async with device:
        device.on_data(lambda label, data: print(f"{label}: {data.hex()}"))
        device.start_streaming()
        await asyncio.sleep(30)

asyncio.run(main())
```

================================================================================
Design Principles
================================================================================

1. Interface Segregation
   - Each protocol defines only one capability
   - Avoid "god interfaces"

2. Dependency Inversion
   - Business layer depends on abstract interfaces, not concrete implementations
   - Concrete implementations (like bleak_adapter) are injected at runtime

3. Duck Typing
   - Python Protocol uses structural subtyping
   - No explicit inheritance required

4. Lazy Import
   - Platform-specific imports are in impl/ directory
   - Won't error if bleak not installed until actually used

================================================================================
"""

from .interfaces import (
    BLEDevice as BLEDeviceProtocol,
    BLEClient as BLEClientProtocol,
    BLEScanner as BLEScannerProtocol,
    NotificationCallback,
    GATTService,
    GATTCharacteristic,
)

from .exceptions import (
    BLEError,
    BLEConnectionError,
    BLEConnectionTimeoutError,
    BLEConnectionRefusedError,
    BLEServiceNotFoundError,
    BLECharacteristicNotFoundError,
    BLEScanError,
    BLEOperationError,
)

from .device import (
    HardwareDevice,
    SignalMetrics,
    DataParser,
    build_legacy_alg_frame,
    parse_alg_frame,
    PROTOCOL_MODE_LEGACY,
    PROTOCOL_MODE_NEUROFEEDBACK,
    DEVICE_TYPE_EEG2,
    DEVICE_TYPE_EEGM,
    DEVICE_TYPE_EEGS,
)

from .wrapper import (
    BLEWrapper,
    BLESearchError,
    BLEConnectError,
    BLEStateError,
    RawDataCallback,
    MetricsCallback,
)

__all__ = [
    # Core class
    "HardwareDevice",
    "BLEWrapper",

    # BLEWrapper specific
    "BLESearchError",
    "BLEConnectError",
    "BLEStateError",
    "RawDataCallback",
    "MetricsCallback",

    # Protocols
    "BLEDeviceProtocol",
    "BLEClientProtocol",
    "BLEScannerProtocol",
    "NotificationCallback",
    "GATTService",
    "GATTCharacteristic",

    # Data parsing
    "SignalMetrics",
    "DataParser",
    "build_legacy_alg_frame",
    "parse_alg_frame",

    # Constants
    "PROTOCOL_MODE_LEGACY",
    "PROTOCOL_MODE_NEUROFEEDBACK",
    "DEVICE_TYPE_EEG2",
    "DEVICE_TYPE_EEGM",
    "DEVICE_TYPE_EEGS",

    # Exceptions
    "BLEError",
    "BLEConnectionError",
    "BLEConnectionTimeoutError",
    "BLEConnectionRefusedError",
    "BLEServiceNotFoundError",
    "BLECharacteristicNotFoundError",
    "BLEScanError",
    "BLEOperationError",
]

__version__ = "0.1.0"

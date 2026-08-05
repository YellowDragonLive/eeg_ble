"""BLE 平台实现模块。

================================================================================
设计说明
================================================================================

本目录包含不同平台的 BLE 适配器实现。

每个适配器都实现了 ble/interfaces.py 中定义的协议接口：

    BLEScanner  →  扫描器实现
    BLEClient   →  客户端实现

当前可用的适配器：

    impl/
    ├── __init__.py       # 导出入口
    ├── bleak_adapter.py   # bleak (Windows/macOS/Linux) 适配器

即将支持：
    impl/
    ├── react_native_adapter.py   # React Native 适配器
    ├── flutter_adapter.py        # Flutter 适配器

================================================================================
使用适配器
================================================================================

业务代码通常不需要直接使用适配器，而是通过 HardwareDevice：

    from ble import HardwareDevice

    device = HardwareDevice(address="AA:BB:CC:DD:EE:30")

如果你需要直接使用适配器：

    from ble.impl.bleak_adapter import BleakBLEScanner, BleakBLEClient

    # 扫描设备
    scanner = BleakBLEScanner()
    devices = await scanner.discover(timeout=5.0)

    # 连接设备
    client = BleakBLEClient(address="AA:BB:CC:DD:EE:30")
    await client.connect()

================================================================================
添加新平台适配器
================================================================================

如果你需要为新平台（如 Flutter）创建适配器：

1. 在 impl/ 目录下创建新文件，如 flutter_adapter.py

2. 实现协议类：

    from ble.interfaces import (
        BLEDevice,
        BLEClient,
        BLEScanner,
        NotificationCallback,
    )

    class FlutterBLEScanner(BLEScanner):
        '''Flutter BLE 扫描器适配器'''
        async def discover(self, timeout: float = 5.0) -> List[BLEDevice]:
            ...

        async def scan_for_address(self, address: str, timeout: float = 5.0) -> Optional[BLEDevice]:
            ...

    class FlutterBLEClient(BLEClient):
        '''Flutter BLE 客户端适配器'''
        ...

3. 在 __init__.py 中导出新类

4. 在 HardwareDevice._create_client() 中添加新平台的分支

================================================================================
"""

# 导出平台实现
from .bleak_adapter import (
    BleakBLEScanner,
    BleakBLEClient,
    BleakBLEDevice,
)

__all__ = [
    "BleakBLEScanner",
    "BleakBLEClient",
    "BleakBLEDevice",
]

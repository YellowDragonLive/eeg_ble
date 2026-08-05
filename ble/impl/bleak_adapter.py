"""bleak 平台适配器实现。

================================================================================
概述
================================================================================

本模块提供了基于 bleak 库的 BLE 适配器实现。
bleak 是一个跨平台的 BLE 库，支持 Windows、macOS 和 Linux。

支持的平台：
- Windows 10+ (使用 Windows.Devices.Bluetooth API)
- macOS 10.13+ (使用 CoreBluetooth)
- Linux (使用 BlueZ DBus API)

安装：
    pip install bleak

================================================================================
架构
================================================================================

                    ┌─────────────────────────────────────┐
                    │         业务代码                     │
                    │   (HardwareDevice, 业务逻辑)          │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │      协议接口层 (interfaces.py)       │
                    │  BLEClient, BLEDevice, BLEScanner    │
                    └─────────────────┬───────────────────┘
                                      │
                                      │ 运行时绑定
                                      ▼
                    ┌─────────────────────────────────────┐
                    │      平台适配层 (本文件)               │
                    │   BleakBLEClient, BleakBLEDevice     │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │        bleak 库                      │
                    │  BleakClient, BleakScanner          │
                    └─────────────────────────────────────┘

================================================================================
使用示例
================================================================================

直接使用适配器：

    import asyncio
    from ble.impl.bleak_adapter import BleakBLEScanner, BleakBLEClient

    async def main():
        # 扫描设备
        scanner = BleakBLEScanner()
        devices = await scanner.discover(timeout=5.0)

        for d in devices:
            print(f"{d.name} @ {d.address}")

        # 连接设备
        client = BleakBLEClient(address="AA:BB:CC:DD:EE:FF")
        await client.connect()

        # 发现服务
        services = await client.get_services()
        service = services.get_service(SERVICE_UUID)

        # 读取数据
        char = service.get_characteristic(CHAR_UUID)
        value = await client.read_gatt_char(char)

        # 订阅通知
        def callback(sender, data):
            print(f"收到: {data.hex()}")

        await client.start_notify(char, callback)

        await asyncio.sleep(30)

        # 清理
        await client.stop_notify(char)
        await client.disconnect()

    asyncio.run(main())

通过 HardwareDevice 使用：

    from ble import HardwareDevice

    async def main():
        device = HardwareDevice(
            address="AA:BB:CC:DD:EE:30",
            name="Dbay-EEG2",
            device_type="Dbay-EEG2"
        )

        async with device:
            device.on_data(lambda label, data: print(f"{label}: {data.hex()}"))
            device.start_streaming()
            await asyncio.sleep(30)

    asyncio.run(main())

================================================================================
线程安全性
================================================================================

bleak 的连接和操作是异步的，应该在同一个 asyncio 事件循环中执行。
通知回调在 bleak 的内部线程中执行，注意线程安全。

================================================================================
异常处理
================================================================================

所有 bleak 的异常都会被捕获并转换为统一的 BLE 异常：

    try:
        await client.connect()
    except BLEConnectionError:
        print("连接失败")
    except BLEError:
        print("其他 BLE 错误")

================================================================================
"""

from __future__ import annotations

import asyncio
import logging
from typing import (
    List,
    Optional,
    Dict,
    Any,
    Callable,
)

from ..interfaces import (
    BLEDevice,
    BLEClient,
    BLEScanner,
    GATTService,
    GATTCharacteristic,
    GATTDescriptor,
    GATTServiceCollection,
    NotificationCallback,
)
from ..exceptions import (
    BLEError,
    BLEConnectionError,
    BLEConnectionTimeoutError,
    BLEConnectionRefusedError,
    BLEServiceNotFoundError,
    BLECharacteristicNotFoundError,
    BLEScanError,
)

logger = logging.getLogger(__name__)

# =============================================================================
# 延迟导入 bleak
# =============================================================================

def _ensure_bleak_available() -> Any:
    """
    确保 bleak 库可用。

    如果 bleak 未安装，抛出 BLEError 并提供安装提示。

    返回:
        bleak 模块

    异常:
        BLEError: bleak 未安装
    """
    try:
        import bleak
        return bleak
    except ImportError:
        raise BLEError(
            "bleak 库未安装。\n"
            "请运行: pip install bleak\n"
            "或参考: https://bleak.readthedocs.io/en/latest/installation.html"
        )


# =============================================================================
# BleakBLEDevice - BLE 设备适配器
# =============================================================================

class BleakBLEDevice:
    """
    bleak BLE 设备适配器。

    包装 bleak 返回的 BleakDevice 对象，
    实现 BLEDevice 协议接口。

    属性:
        address: 蓝牙地址
        name: 设备名称（可能为 None）
        rssi: 信号强度（可能为 None）
    """

    def __init__(self, bleak_device: Any):
        """
        初始化适配器。

        参数:
            bleak_device: bleak 的 BleakDevice 对象
        """
        self._device = bleak_device

    @property
    def name(self) -> str | None:
        """
        设备名称。

        可能为 None（设备未广播名称）。
        """
        return self._device.name

    @property
    def address(self) -> str:
        """
        蓝牙地址。

        统一转为大写冒号格式。
        """
        addr = self._device.address
        # 统一转为大写冒号格式
        addr = addr.replace("-", ":").upper()
        return addr

    @property
    def rssi(self) -> int | None:
        """
        信号强度 RSSI。

        可能为 None（某些平台不提供 RSSI）。
        """
        return getattr(self._device, "rssi", None)

    @property
    def _raw_device(self) -> Any:
        """
        原始 bleak 设备对象。

        供内部使用，业务代码不应直接访问。
        """
        return self._device

    def __repr__(self) -> str:
        return (
            f"<BleakBLEDevice "
            f"name={self.name!r} "
            f"address={self.address} "
            f"rssi={self.rssi}>"
        )


# =============================================================================
# BleakGATTDescriptor - GATT 描述符适配器
# =============================================================================

class BleakGATTDescriptor:
    """GATT 描述符适配器。"""

    def __init__(self, bleak_descriptor: Any):
        self._descriptor = bleak_descriptor

    @property
    def uuid(self) -> str:
        return self._descriptor.uuid

    @property
    def handle(self) -> int:
        return getattr(self._descriptor, "handle", 0)

    def __repr__(self) -> str:
        return f"<BleakGATTDescriptor uuid={self.uuid} handle={self.handle}>"


# =============================================================================
# BleakGATTCharacteristic - GATT 特征适配器
# =============================================================================

class BleakGATTCharacteristic:
    """
    GATT 特征适配器。

    包装 bleak 的 BleakGATTCharacteristic 对象。
    """

    def __init__(self, bleak_char: Any):
        """
        初始化适配器。

        参数:
            bleak_char: bleak 的 BleakGATTCharacteristic 对象
        """
        self._char = bleak_char
        # 缓存描述符列表
        self._descriptors: List[GATTDescriptor] | None = None

    @property
    def uuid(self) -> str:
        """特征 UUID。"""
        return self._char.uuid

    @property
    def description(self) -> str | None:
        """特征描述。"""
        return getattr(self._char, "description", None)

    @property
    def properties(self) -> List[str]:
        """
        特征属性列表。

        返回:
            属性列表，如 ['read', 'notify', 'write']
        """
        # bleak 的 properties 可能已经是 list
        props = getattr(self._char, "properties", [])
        if isinstance(props, list):
            return props
        # 也可能是集合或其他可迭代对象
        return list(props)

    @property
    def descriptors(self) -> List[GATTDescriptor]:
        """
        描述符列表。

        返回:
            GATTDescriptor 列表
        """
        if self._descriptors is None:
            descs = getattr(self._char, "descriptors", [])
            # 新版 bleak 返回 dict，需要取 values
            if isinstance(descs, dict):
                self._descriptors = [
                    BleakGATTDescriptor(d) for d in descs.values()
                ]
            else:
                self._descriptors = [
                    BleakGATTDescriptor(d) for d in descs
                ]
        return self._descriptors

    def __repr__(self) -> str:
        return (
            f"<BleakGATTCharacteristic "
            f"uuid={self.uuid} "
            f"properties={self.properties}>"
        )


# =============================================================================
# BleakGATTService - GATT 服务适配器
# =============================================================================

class BleakGATTService:
    """
    GATT 服务适配器。

    包装 bleak 的 BleakGATTService 对象。
    """

    def __init__(self, bleak_service: Any):
        """
        初始化适配器。

        参数:
            bleak_service: bleak 的 BleakGATTService 对象
        """
        self._service = bleak_service
        # 缓存特征列表
        self._characteristics: List[GATTCharacteristic] | None = None

    @property
    def uuid(self) -> str:
        """服务 UUID。"""
        return self._service.uuid

    @property
    def description(self) -> str | None:
        """服务描述。"""
        return getattr(self._service, "description", None)

    @property
    def characteristics(self) -> List[GATTCharacteristic]:
        """
        服务包含的特征列表。

        返回:
            GATTCharacteristic 列表
        """
        if self._characteristics is None:
            chars = getattr(self._service, "characteristics", [])
            # 新版 bleak 返回 dict，需要取 values
            if isinstance(chars, dict):
                self._characteristics = [
                    BleakGATTCharacteristic(c) for c in chars.values()
                ]
            else:
                self._characteristics = [
                    BleakGATTCharacteristic(c) for c in chars
                ]
        return self._characteristics

    def get_characteristic(self, uuid: str) -> Optional[GATTCharacteristic]:
        """
        按 UUID 查找特征。

        参数:
            uuid: 特征 UUID

        返回:
            找到返回 GATTCharacteristic，否则返回 None
        """
        # 尝试直接用 bleak 的方法
        char = getattr(self._service, "get_characteristic", None)
        if callable(char):
            result = char(uuid)
            if result is not None:
                return BleakGATTCharacteristic(result)

        # 回退：手动遍历
        for c in self.characteristics:
            if c.uuid.upper() == uuid.upper():
                return c

        return None

    def __repr__(self) -> str:
        return (
            f"<BleakGATTService "
            f"uuid={self.uuid} "
            f"description={self.description!r}>"
        )


# =============================================================================
# BleakGATTServiceCollection - GATT 服务集合适配器
# =============================================================================

class BleakGATTServiceCollection:
    """
    GATT 服务集合适配器。

    包装 bleak 的服务集合。
    """

    def __init__(self, bleak_services: Any):
        """
        初始化适配器。

        参数:
            bleak_services: bleak 的服务集合对象
        """
        self._services = bleak_services
        # 缓存服务列表
        self._service_list: List[GATTService] | None = None

    def get_service(self, uuid: str) -> Optional[GATTService]:
        """
        按 UUID 查找服务。

        参数:
            uuid: 服务 UUID

        返回:
            找到返回 GATTService，否则返回 None
        """
        # 尝试直接用 bleak 的方法
        service_getter = getattr(self._services, "get_service", None)
        if callable(service_getter):
            result = service_getter(uuid)
            if result is not None:
                return BleakGATTService(result)

        # 回退：手动遍历
        for s in self.services:
            if s.uuid.upper() == uuid.upper():
                return s

        return None

    @property
    def services(self) -> List[GATTService]:
        """
        服务列表。

        返回:
            GATTService 列表
        """
        if self._service_list is None:
            # bleak 的服务集合可能支持直接迭代
            services = getattr(self._services, "services", None)
            if services is not None:
                # 新版 bleak 返回 dict，需要取 values
                if isinstance(services, dict):
                    self._service_list = [
                        BleakGATTService(s) for s in services.values()
                    ]
                else:
                    self._service_list = [
                        BleakGATTService(s) for s in services
                    ]
            else:
                # 尝试直接迭代
                try:
                    svcs = self._services
                    if isinstance(svcs, dict):
                        self._service_list = [
                            BleakGATTService(s) for s in svcs.values()
                        ]
                    else:
                        self._service_list = [
                            BleakGATTService(s) for s in svcs
                        ]
                except TypeError:
                    self._service_list = []

        return self._service_list

    def __repr__(self) -> str:
        count = len(self._service_list) if self._service_list is not None else "?"
        return f"<BleakGATTServiceCollection services={count}>"


# =============================================================================
# BleakBLEClient - BLE 客户端适配器
# =============================================================================

class BleakBLEClient:
    """
    bleak BLE 客户端适配器。

    实现 BLEClient 协议接口。

    使用示例:
        client = BleakBLEClient(address="AA:BB:CC:DD:EE:FF")
        await client.connect()
        services = await client.get_services()
        ...
        await client.disconnect()
    """

    def __init__(self, address: str, **kwargs: Any):
        """
        初始化客户端。

        参数:
            address: 蓝牙设备地址
            **kwargs: 传递给 bleak.BleakClient 的其他参数
        """
        self._address = address.upper().replace("-", ":")
        self._kwargs = kwargs
        self._client: Any = None
        self._is_connected = False

    # -------------------------------------------------------------------------
    # 连接生命周期
    # -------------------------------------------------------------------------

    async def connect(self, timeout: float = 10.0) -> None:
        """
        连接到 BLE 设备。

        参数:
            timeout: 连接超时时间（秒）

        异常:
            BLEConnectionTimeoutError: 连接超时
            BLEConnectionError: 连接失败
        """
        bleak = _ensure_bleak_available()
        BleakClient = bleak.BleakClient

        self._logger.info(f"正在连接到 {self._address}...")

        try:
            self._client = BleakClient(self._address, **self._kwargs)
            result = await self._client.connect(timeout=timeout)

            # 新版 bleak 返回 None 表示成功，旧版返回 True
            # 只有明确返回 False 才表示失败
            if result is False:
                raise BLEConnectionError(
                    "连接被拒绝",
                    device_address=self._address,
                )

            # 检查连接状态
            if not self.is_connected:
                raise BLEConnectionError(
                    "连接后 is_connected 为 False",
                    device_address=self._address,
                )

            self._is_connected = True
            self._logger.info(f"已连接到 {self._address}")

        except BLEConnectionError:
            raise
        except asyncio.TimeoutError:
            raise BLEConnectionTimeoutError(
                "连接超时",
                device_address=self._address,
                timeout=timeout,
            )
        except Exception as e:
            error_msg = str(e).lower()

            if "timeout" in error_msg:
                raise BLEConnectionTimeoutError(
                    f"连接超时: {e}",
                    device_address=self._address,
                    timeout=timeout,
                )
            elif "refused" in error_msg or "reject" in error_msg:
                raise BLEConnectionRefusedError(
                    f"连接被拒绝: {e}",
                    device_address=self._address,
                )
            else:
                raise BLEConnectionError(
                    f"连接失败: {e}",
                    device_address=self._address,
                )

    async def disconnect(self) -> None:
        """
        断开与设备的连接。

        异常:
            BLEError: 断开失败
        """
        if self._client is None:
            return

        try:
            await self._client.disconnect()
        except Exception as e:
            self._logger.warning(f"断开连接时出错: {e}")
        finally:
            self._is_connected = False
            self._client = None

    @property
    def is_connected(self) -> bool:
        """
        检查是否已连接。

        返回:
            True - 已连接
            False - 未连接
        """
        if self._client is None:
            return False

        # 检查 bleak 客户端的连接状态
        return getattr(self._client, "is_connected", False)

    # -------------------------------------------------------------------------
    # GATT 操作
    # -------------------------------------------------------------------------

    async def get_services(self) -> GATTServiceCollection:
        """
        发现设备支持的 GATT 服务。

        返回:
            GATTServiceCollection 对象

        异常:
            BLEError: 服务发现失败
        """
        if self._client is None:
            raise BLEError("客户端未连接")

        try:
            # 新版 bleak 在 connect() 后自动缓存服务
            # 优先用缓存的属性
            services = getattr(self._client, "services", None)
            if services is None:
                # 旧版 bleak 需要调用方法
                get_services = getattr(self._client, "get_services", None)
                if callable(get_services):
                    services = await get_services()

            if services is None:
                raise BLEError("无法获取服务集合")

            return BleakGATTServiceCollection(services)

        except BLEError:
            raise
        except Exception as e:
            raise BLEError(
                f"服务发现失败: {e}",
                device_address=self._address,
            )

    async def read_gatt_char(
        self,
        characteristic: GATTCharacteristic,
    ) -> bytearray:
        """
        读取特征值。

        参数:
            characteristic: GATTCharacteristic 对象

        返回:
            特征值（bytearray）

        异常:
            BLEError: 读取失败
        """
        if self._client is None:
            raise BLEError("客户端未连接")

        try:
            # 获取 bleak 的特征对象
            raw_char = getattr(characteristic, "_char", None)
            if raw_char is None:
                raise BLEError("无法获取原始特征对象")

            value = await self._client.read_gatt_char(raw_char)
            return bytearray(value)

        except Exception as e:
            raise BLEError(
                f"读取特征失败: {e}",
                device_address=self._address,
            )

    async def write_gatt_char(
        self,
        characteristic: GATTCharacteristic,
        data: bytes | bytearray,
        response: bool = False,
    ) -> None:
        """
        写入特征值。

        参数:
            characteristic: GATTCharacteristic 对象
            data: 要写入的数据
            response: 是否请求响应

        异常:
            BLEError: 写入失败
        """
        if self._client is None:
            raise BLEError("客户端未连接")

        try:
            raw_char = getattr(characteristic, "_char", None)
            if raw_char is None:
                raise BLEError("无法获取原始特征对象")

            await self._client.write_gatt_char(
                raw_char,
                bytes(data),
                response=response,
            )

        except Exception as e:
            raise BLEError(
                f"写入特征失败: {e}",
                device_address=self._address,
            )

    async def start_notify(
        self,
        characteristic: GATTCharacteristic,
        callback: NotificationCallback,
    ) -> None:
        """
        订阅特征的通知。

        参数:
            characteristic: GATTCharacteristic 对象
            callback: 通知回调函数

        异常:
            BLEError: 订阅失败
        """
        if self._client is None:
            raise BLEError("客户端未连接")

        try:
            raw_char = getattr(characteristic, "_char", None)
            if raw_char is None:
                raise BLEError("无法获取原始特征对象")

            # bleak 的回调签名是 (sender, data)
            # 我们的 NotificationCallback 签名是 (sender_handle, data)
            # 对于 bleak，sender 已经是 handle

            await self._client.start_notify(raw_char, callback)

        except Exception as e:
            raise BLEError(
                f"订阅通知失败: {e}",
                device_address=self._address,
            )

    async def stop_notify(
        self,
        characteristic: GATTCharacteristic,
    ) -> None:
        """
        取消订阅特征的通知。

        参数:
            characteristic: GATTCharacteristic 对象

        异常:
            BLEError: 取消订阅失败
        """
        if self._client is None:
            return

        try:
            raw_char = getattr(characteristic, "_char", None)
            if raw_char is None:
                return

            await self._client.stop_notify(raw_char)

        except Exception as e:
            # stop_notify 失败通常不致命，只是记录警告
            self._logger.warning(f"取消订阅失败: {e}")

    # -------------------------------------------------------------------------
    # 辅助属性
    # -------------------------------------------------------------------------

    @property
    def address(self) -> str:
        """设备地址。"""
        return self._address

    @property
    def _logger(self) -> logging.Logger:
        """日志记录器。"""
        return logger

    def __repr__(self) -> str:
        status = "connected" if self._is_connected else "disconnected"
        return f"<BleakBLEClient address={self._address} status={status}>"


# =============================================================================
# BleakBLEScanner - BLE 扫描器适配器
# =============================================================================

class BleakBLEScanner:
    """
    bleak BLE 扫描器适配器。

    实现 BLEScanner 协议接口。

    使用示例:
        scanner = BleakBLEScanner()
        devices = await scanner.discover(timeout=5.0)

        for d in devices:
            print(f"{d.name} @ {d.address} (RSSI: {d.rssi})")
    """

    def __init__(self, **kwargs: Any):
        """
        初始化扫描器。

        参数:
            **kwargs: 传递给 bleak.BleakScanner 的其他参数
        """
        self._kwargs = kwargs
        self._scanner: Any = None

    async def discover(self, timeout: float = 5.0) -> List[BLEDevice]:
        """
        扫描附近的所有 BLE 设备。

        参数:
            timeout: 扫描超时时间（秒）

        返回:
            BLEDevice 对象列表，按 RSSI 降序排列

        异常:
            BLEScanError: 扫描失败
        """
        bleak = _ensure_bleak_available()
        BleakScanner = bleak.BleakScanner

        try:
            self._scanner = BleakScanner(**self._kwargs)
            devices = await self._scanner.discover(timeout=timeout)

            # 转换为适配器对象
            result = [BleakBLEDevice(d) for d in devices]

            # 按 RSSI 降序排列
            result.sort(
                key=lambda d: (
                    d.rssi is not None,
                    d.rssi if d.rssi is not None else -9999,
                ),
                reverse=True,
            )

            logger.debug(f"扫描完成，发现 {len(result)} 个设备")
            return result

        except Exception as e:
            raise BLEScanError(f"扫描失败: {e}")

    async def scan_for_address(
        self,
        address: str,
        timeout: float = 5.0,
    ) -> Optional[BLEDevice]:
        """
        扫描并等待连接到指定地址的设备。

        参数:
            address: 目标设备地址
            timeout: 扫描超时时间

        返回:
            找到返回 BLEDevice，否则返回 None
        """
        address = address.upper().replace("-", ":")

        devices = await self.discover(timeout=timeout)

        for d in devices:
            if d.address.upper().replace("-", ":") == address:
                return d

        return None

    @property
    def _logger(self) -> logging.Logger:
        """日志记录器。"""
        return logger

    def __repr__(self) -> str:
        return "<BleakBLEScanner>"

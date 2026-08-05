"""BLE 核心接口定义 - 结构子类型协议 (Protocol)。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Callable, List, Optional


# =============================================================================
# 类型别名
# =============================================================================

NotificationCallback = Callable[[int, bytearray], None]


# =============================================================================
# BLEDevice 协议 - 扫描发现的设备信息
# =============================================================================

@runtime_checkable
class BLEDevice(Protocol):
    """BLE 设备信息：名字、地址、信号强度。"""

    @property
    def name(self) -> str | None: ...

    @property
    def address(self) -> str: ...

    @property
    def rssi(self) -> int | None: ...


# =============================================================================
# BLEScanner 协议 - 设备扫描
# =============================================================================

@runtime_checkable
class BLEScanner(Protocol):
    """BLE 设备扫描器。"""

    async def discover(self, timeout: float = 5.0) -> List[BLEDevice]:
        """扫描附近 BLE 设备，返回设备列表。"""
        ...

    async def scan_for_address(self, address: str, timeout: float = 5.0) -> Optional[BLEDevice]:
        """扫描并等待指定地址的设备。"""
        ...


# =============================================================================
# BLEClient 协议 - 连接和 GATT 操作
# =============================================================================

@runtime_checkable
class BLEClient(Protocol):
    """BLE 客户端：连接设备、执行 GATT 操作。"""

    async def connect(self, timeout: float = 10.0) -> None: ...
    async def disconnect(self) -> None: ...

    @property
    def is_connected(self) -> bool: ...

    async def get_services(self) -> "GATTServiceCollection": ...
    async def read_gatt_char(self, characteristic: "GATTCharacteristic") -> bytearray: ...

    async def write_gatt_char(
        self,
        characteristic: "GATTCharacteristic",
        data: bytes | bytearray,
        response: bool = False,
    ) -> None: ...

    async def start_notify(
        self,
        characteristic: "GATTCharacteristic",
        callback: NotificationCallback,
    ) -> None: ...

    async def stop_notify(self, characteristic: "GATTCharacteristic") -> None: ...


# =============================================================================
# GATT 数据结构协议
# =============================================================================

@runtime_checkable
class GATTServiceCollection(Protocol):
    """GATT 服务集合。"""

    def get_service(self, uuid: str) -> Optional["GATTService"]: ...


@runtime_checkable
class GATTService(Protocol):
    """GATT 服务。"""

    @property
    def uuid(self) -> str: ...
    @property
    def description(self) -> str | None: ...
    @property
    def characteristics(self) -> List["GATTCharacteristic"]: ...

    def get_characteristic(self, uuid: str) -> Optional["GATTCharacteristic"]: ...


@runtime_checkable
class GATTCharacteristic(Protocol):
    """GATT 特征。"""

    @property
    def uuid(self) -> str: ...
    @property
    def description(self) -> str | None: ...
    @property
    def properties(self) -> List[str]: ...
    @property
    def descriptors(self) -> List["GATTDescriptor"]: ...


@runtime_checkable
class GATTDescriptor(Protocol):
    """GATT 描述符。"""

    @property
    def uuid(self) -> str: ...
    @property
    def handle(self) -> int: ...

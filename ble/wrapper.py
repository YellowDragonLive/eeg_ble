"""BLE Wrapper - 简化的蓝牙设备封装类。

================================================================================
设计目标
================================================================================

为其他程序和 AI 提供简洁的 BLE 设备操作接口。

暴露 4 个核心操作：
- search()   - 搜索设备
- connect()  - 连接设备
- start()   - 开始数据传输
- stop()    - 停止数据传输

================================================================================
使用示例
================================================================================

基础用法:

    import asyncio
    from ble import BLEWrapper

    async def main():
        ble = BLEWrapper()

        # 搜索设备
        devices = await ble.search(timeout=5.0)
        print(f"发现 {len(devices)} 个设备")

        # 连接
        await ble.connect("AA:BB:CC:DD:EE:30")

        # 注册回调
        def on_data(channel, data):
            print(f"[{channel}] {data.hex()}")

        def on_metrics(focus, stress, fatigue, asy, **kwargs):
            print(f"专注: {focus}, 压力: {stress}")

        ble.on_data(on_data)
        ble.on_metrics(on_metrics)

        # 开始接收
        ble.start()
        await asyncio.sleep(30)

        # 停止
        ble.stop()

        # 销毁
        await ble.destroy()

    asyncio.run(main())

FastAPI 用法:

    from fastapi import FastAPI
    from ble import BLEWrapper

    app = FastAPI()
    ble = BLEWrapper()

    @app.post("/ble/search")
    async def search_devices():
        return await ble.search()

    @app.post("/ble/connect/{address}")
    async def connect_device(address: str):
        await ble.connect(address)
        return {"status": "connected"}

    @app.post("/ble/start")
    async def start_streaming():
        ble.on_data(lambda ch, d: print(f"[{ch}] {d.hex()}"))
        ble.on_metrics(lambda **m: print(m))
        ble.start()
        return {"status": "streaming"}

================================================================================
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field

from .device import HardwareDevice
from .exceptions import BLEError
from .constants import (
    SERVICE_UUID,
    CHARACTERISTIC_UUID_CMD,
    CHARACTERISTIC_UUID_DATA_EEG,
    CHARACTERISTIC_UUID_DATA_RSP_INFO,
    CHARACTERISTIC_UUID_DATA_ALG,
    DEVICE_TYPE_EEG2,
)
from .impl.bleak_adapter import BleakBLEScanner

logger = logging.getLogger(__name__)


# =============================================================================
# 回调类型定义
# =============================================================================

# 原始数据回调
# 参数:
#   - channel: str  - 通道标签 "EEG" | "RSP" | "ALG"
#   - data: bytearray - 原始字节数据
RawDataCallback = Callable[[str, bytearray], None]

# 指标数据回调
# 参数:
#   - focus: float - 专注度 (0-100)
#   - stress: float - 压力指数 (0-100)
#   - fatigue: float - 疲劳度 (0-100)
#   - asy: float - 左右脑不对称指数
#   - delta, theta, alpha, beta, gamma: float - 频段能量
MetricsCallback = Callable[..., None]


# =============================================================================
# BLEWrapper 核心类
# =============================================================================

class BLEWrapper:
    """
    BLE EEG 设备封装类。

    提供简洁的 4 个核心操作接口，适合 AI 和其他程序调用。

    生命周期:
        1. create     - 创建实例
        2. search     - 搜索设备 (可选)
        3. connect    - 连接设备
        4. start      - 开始传输
        5. stop       - 停止传输
        6. destroy    - 销毁实例

    示例:
        ble = BLEWrapper()
        devices = await ble.search()
        await ble.connect("AA:BB:CC:DD:EE:30")
        ble.on_data(my_callback)
        ble.start()
        await asyncio.sleep(30)
        ble.stop()
        await ble.destroy()
    """

    def __init__(
        self,
        device_type: str = "Dbay-EEG2",
        connect_timeout: float = 10.0,
    ):
        """
        初始化 BLE Wrapper。

        参数:
            device_type: 设备类型，影响协议解析方式
                    - "Dbay-EEG2": 标准双通道 EEG
                    - "Dbay-EEGM": 中端版本
                    - "Dbay-EEGS": Fabric 固件版本
                    默认: "Dbay-EEG2"

            connect_timeout: 连接超时时间 (秒)，默认 10 秒
        """
        self._device_type = device_type
        self._connect_timeout = connect_timeout

        # 内部硬件设备实例
        self._device: Optional[HardwareDevice] = None

        # 回调函数
        self._raw_data_callbacks: List[RawDataCallback] = []
        self._metrics_callbacks: List[MetricsCallback] = []

        # 状态
        self._is_connected = False
        self._is_streaming = False

        # 日志
        self._logger = logging.getLogger(f"{__name__}.BLEWrapper")

    # =========================================================================
    # 搜索设备
    # =========================================================================

    async def search(self, timeout: float = 15.0) -> List[Dict[str, Any]]:
        """
        搜索附近的 BLE 设备。

        参数:
            timeout: 搜索超时时间 (秒)，默认 15 秒

        返回:
            设备列表，每个设备是一个字典:
            [
                {
                    "name": "Dbay-EEG2",        # 设备名称 (可能为 None)
                    "address": "AA:BB:CC:DD:EE:30",  # 蓝牙地址
                    "rssi": -65,               # 信号强度 dBm (可能为 None)
                    "raw": {                    # 原始数据
                        "address_type": "random",
                        "details": {}
                    }
                },
                ...
            ]

        异常:
            BLESearchError: 搜索失败

        示例:
            devices = await ble.search()  # 默认 15 秒超时
            for d in devices:
                print(f"{d['name']} @ {d['address']}")
        """
        scanner = BleakBLEScanner()

        try:
            self._logger.info(f"开始搜索设备，超时 {timeout}s...")
            devices = await scanner.discover(timeout=timeout)

            # 转换为 JSON 友好格式
            result = []
            for d in devices:
                result.append({
                    "name": d.name,
                    "address": d.address,
                    "rssi": d.rssi,
                    "raw": {
                        "address_type": getattr(d._raw_device, "address_type", None),
                        "details": {},
                    }
                })

            self._logger.info(f"搜索完成，发现 {len(result)} 个设备")
            return result

        except BLEError as e:
            self._logger.error(f"搜索失败: {e}")
            raise BLESearchError(f"搜索设备失败: {e}") from e
        except Exception as e:
            self._logger.error(f"搜索异常: {e}")
            raise BLESearchError(f"搜索设备异常: {e}") from e

    # =========================================================================
    # 连接设备
    # =========================================================================

    async def connect(self, address: str) -> None:
        """
        连接到指定地址的 BLE 设备。

        参数:
            address: 蓝牙设备地址
                    格式: "AA:BB:CC:DD:EE:30" 或 "AA-BB-CC-DD-EE-30"

        异常:
            BLEConnectError: 连接失败

        示例:
            await ble.connect("AA:BB:CC:DD:EE:30")
        """
        if self._is_connected:
            self._logger.warning("已连接，先断开再连接")
            await self.disconnect()

        self._logger.info(f"正在连接到 {address}...")

        try:
            # 创建硬件设备实例
            self._device = HardwareDevice(
                address=address,
                device_type=self._device_type,
                connect_timeout=self._connect_timeout,
            )

            # 连接
            await self._device.connect()
            self._is_connected = True
            self._logger.info(f"已连接到 {address}")

        except BLEError as e:
            self._logger.error(f"连接失败: {e}")
            raise BLEConnectError(f"连接设备失败: {e}") from e
        except Exception as e:
            self._logger.error(f"连接异常: {e}")
            raise BLEConnectError(f"连接设备异常: {e}") from e

    async def disconnect(self) -> None:
        """
        断开与设备的连接。

        不会销毁实例，可以再次调用 connect() 连接其他设备。
        """
        if not self._is_connected or self._device is None:
            return

        self._logger.info("正在断开连接...")

        try:
            await self._device.disconnect()
            self._logger.info("已断开连接")
        except Exception as e:
            self._logger.warning(f"断开连接时出错: {e}")
        finally:
            self._is_connected = False
            self._is_streaming = False
            self._device = None

    # =========================================================================
    # 回调注册
    # =========================================================================

    def on_data(self, callback: RawDataCallback) -> None:
        """
        注册原始数据回调。

        收到原始 BLE 数据时触发，包括 EEG、RSP、ALG 三个通道。

        参数:
            callback: 回调函数，签名为 (channel: str, data: bytearray)
                    - channel: 通道标签 "EEG" | "RSP" | "ALG"
                    - data: 原始字节数据

        示例:
            def on_raw(channel, data):
                print(f"[{channel}] {data.hex()}")

            ble.on_data(on_raw)
        """
        if callback not in self._raw_data_callbacks:
            self._raw_data_callbacks.append(callback)
            self._logger.debug(f"已注册原始数据回调: {callback.__name__}")

    def on_metrics(self, callback: MetricsCallback) -> None:
        """
        注册指标数据回调。

        收到解析后的神经反馈指标时触发，约 1-2Hz 更新频率。

        参数:
            callback: 回调函数，支持以下参数:
                    - focus: float     专注度 (0-100)
                    - stress: float    压力指数 (0-100)
                    - fatigue: float   疲劳度 (0-100)
                    - asy: float       左右脑不对称指数
                    - delta: float     频段能量
                    - theta: float
                    - alpha: float
                    - beta: float
                    - gamma: float

        示例:
            def on_metrics(focus, stress, fatigue, **kwargs):
                print(f"专注: {focus}, 压力: {stress}")

            ble.on_metrics(on_metrics)
        """
        if callback not in self._metrics_callbacks:
            self._metrics_callbacks.append(callback)
            self._logger.debug(f"已注册指标回调: {callback.__name__}")

    def clear_callbacks(self) -> None:
        """清除所有注册的回调。"""
        self._raw_data_callbacks.clear()
        self._metrics_callbacks.clear()
        self._logger.debug("已清除所有回调")

    # =========================================================================
    # 数据传输控制
    # =========================================================================

    def start(self) -> None:
        """
        开始数据传输。

        订阅所有通道的通知，开始接收 BLE 数据。
        必须在 connect() 之后调用。

        异常:
            BLEStateError: 未连接或已启动

        示例:
            ble.start()
        """
        if not self._is_connected:
            raise BLEStateError("设备未连接，请先调用 connect()")

        if self._is_streaming:
            self._logger.warning("已经在接收数据")
            return

        # 确保设备有回调
        if self._raw_data_callbacks or self._metrics_callbacks:
            self._setup_device_callbacks()
        else:
            self._logger.warning("没有注册回调，数据将被忽略")

        # 开始流
        self._device.start_streaming(send_start_command=True)
        self._is_streaming = True
        self._logger.info("已开始数据传输")

    def stop(self) -> None:
        """
        停止数据传输。

        取消所有通道的通知订阅，不会断开连接。

        示例:
            ble.stop()
        """
        if not self._is_streaming or self._device is None:
            return

        self._logger.info("正在停止数据传输...")

        try:
            # 停止流 - 创建一个后台任务执行异步停止
            asyncio.create_task(self._async_stop())
            self._is_streaming = False
            self._logger.info("已停止数据传输")
        except Exception as e:
            self._logger.warning(f"停止传输时出错: {e}")
            self._is_streaming = False

    async def _async_stop(self) -> None:
        """异步停止传输（内部方法）。"""
        try:
            if self._device is not None:
                await self._device.stop_streaming()
        except Exception as e:
            self._logger.warning(f"异步停止传输时出错: {e}")

    # =========================================================================
    # 生命周期管理
    # =========================================================================

    async def destroy(self) -> None:
        """
        销毁实例，断开连接并清理资源。

        建议在程序退出或不再使用 BLE 时调用。

        示例:
            await ble.destroy()
        """
        self._logger.info("正在销毁 BLEWrapper 实例...")

        # 停止传输
        if self._is_streaming:
            self.stop()

        # 断开连接
        await self.disconnect()

        # 清除回调
        self.clear_callbacks()

        self._logger.info("BLEWrapper 实例已销毁")

    # =========================================================================
    # 内部方法
    # =========================================================================

    def _setup_device_callbacks(self) -> None:
        """设置设备的数据回调。"""
        if self._device is None:
            return

        # 原始数据回调
        def raw_callback(channel: str, data: bytearray) -> None:
            for cb in self._raw_data_callbacks:
                try:
                    cb(channel, data)
                except Exception as e:
                    self._logger.error(f"原始数据回调执行错误: {e}")

        self._device.on_data(raw_callback)

        # 指标回调
        def metrics_wrapper(channel: str, data: bytearray) -> None:
            if channel != "ALG":
                return

            metrics = self._device.latest_metrics
            if metrics is None:
                return

            for cb in self._metrics_callbacks:
                try:
                    cb(
                        focus=metrics.focus,
                        stress=metrics.stress,
                        fatigue=metrics.fatigue,
                        asy=metrics.asy,
                        delta=metrics.delta,
                        theta=metrics.theta,
                        alpha=metrics.alpha,
                        beta=metrics.beta,
                        gamma=metrics.gamma,
                    )
                except Exception as e:
                    self._logger.error(f"指标回调执行错误: {e}")

        self._device.on_data(metrics_wrapper)

    # =========================================================================
    # 属性
    # =========================================================================

    @property
    def is_connected(self) -> bool:
        """是否已连接。"""
        return self._is_connected

    @property
    def is_streaming(self) -> bool:
        """是否正在传输数据。"""
        return self._is_streaming

    @property
    def connected_address(self) -> str | None:
        """已连接设备的地址。"""
        if self._device is not None:
            return self._device.address
        return None

    def __repr__(self) -> str:
        status = []
        if self._is_connected:
            status.append("connected")
        if self._is_streaming:
            status.append("streaming")
        if not status:
            status.append("disconnected")
        return f"<BLEWrapper status={', '.join(status)}>"


# =============================================================================
# 异常类
# =============================================================================

class BLESearchError(BLEError):
    """搜索设备失败。"""

    def __init__(self, message: str):
        super().__init__(message)


class BLEConnectError(BLEError):
    """连接设备失败。"""

    def __init__(self, message: str):
        super().__init__(message)


class BLEStateError(BLEError):
    """状态错误，如未连接时调用 start()"""

    def __init__(self, message: str):
        super().__init__(message)

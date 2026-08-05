"""硬件设备抽象类。

================================================================================
设计理念
================================================================================

HardwareDevice 是业务层直接使用的硬件抽象类。
它封装了 BLE 连接的完整流程：

    扫描 → 连接 → 发现服务 → 配置 → 数据订阅

使用 HardwareDevice，业务代码不需要关心：
- 底层 BLE 库是 bleak 还是 React Native
- GATT 服务的具体 UUID
- 连接和订阅的技术细节

只需要定义：
1. 硬件类型（决定协议解析方式）
2. 数据回调（处理接收到的数据）

================================================================================
使用示例
================================================================================

基础用法（使用上下文管理器）:

    import asyncio
    from ble import HardwareDevice

    async def main():
        device = HardwareDevice(
            address="AA:BB:CC:DD:EE:30",  # 尾号 3430
            name="Dbay-EEG2",
            device_type="Dbay-EEG2",
            # 可选：指定服务 UUID（不指定则使用默认）
            service_uuid="0000FFE0-0000-1000-8000-00805F9B34FB",
        )

        async with device:
            # 注册数据回调
            device.on_data(lambda label, data: print(f"{label}: {data.hex()}"))

            # 开始接收数据
            device.start_streaming()

            # 持续监听 30 秒
            await asyncio.sleep(30)

    asyncio.run(main())

高级用法（手动控制连接生命周期）:

    device = HardwareDevice(address="AA:BB:CC:DD:EE:30")

    try:
        # 连接设备
        await device.connect()

        # 开始流式接收
        device.start_streaming()

        # 注册多个回调
        device.on_eeg(lambda data: process_eeg(data))
        device.on_alg(lambda data: process_alg(data))

        # 等待数据
        await asyncio.sleep(60)

    finally:
        # 确保断开连接
        await device.disconnect()

================================================================================
硬件类型支持
================================================================================

支持的设备类型（device_type 参数）:

    Dbay-EEG2   - 标准 EEG 设备，双通道（FP7/FP8）
    Dbay-EEGM   - 中端 EEG 设备
    Dbay-EEGS   - Fabric 固件版本（帧格式略有不同）

设备类型决定：
- 协议帧的解析方式（前导字节数量）
- 启动命令的格式
- 指标的衍生计算公式

================================================================================
BLE 通道详解
================================================================================

Dbay EEG 设备通过 Nordic UART Service (NUS) 暴露 4 个 BLE 特征：

┌─────────────────────────────────────────────────────────────────────────────┐
│                         NUS Service (6e400001-...)                         │
├──────────────┬──────────────────────────────────┬──────────────────────────┤
│ 特征          │ UUID                             │ 说明                      │
├──────────────┼──────────────────────────────────┼──────────────────────────┤
│ CMD (TX)     │ 6e400002-b5a3-...               │ 发送命令到设备            │
│ EEG (RX)     │ 6e400003-b5a3-...               │ 原始脑电波数据            │
│ RSP (RX)     │ 6e400004-b5a3-...               │ 呼吸/心率等生理数据       │
│ ALG (RX)     │ 6e400005-b5a3-...               │ 算法处理后的指标数据      │
└──────────────┴──────────────────────────────────┴──────────────────────────┘

--------------------------------------------------------------------------------
1. CMD 通道 (Command)
--------------------------------------------------------------------------------
    用途：发送控制命令到设备
    方向：主机 → 设备（写入）
    启动命令：
      - Dbay-EEG2/EEGM: bytes([0x05, 0x03])    # 开始发送数据流
      - Dbay-EEGS:      bytes([0x04, 0x01, 0x01, 0x00, 0x01])  # 带参数启动

--------------------------------------------------------------------------------
2. EEG 通道 (Raw EEG)
--------------------------------------------------------------------------------
    用途：原始脑电波采样数据
    方向：设备 → 主机（通知）
    数据格式：
      - 每包约 128-256 字节
      - 包含两个通道（FP7/FP8）的原始采样值
      - 采样率：500Hz
      - 数据布局：交织排列的高低位字节
    解析说明：
      - 每个采样值占 2 字节（16-bit little-endian）
      - 交织格式：[ch1_low, ch1_high, ch2_low, ch2_high, ...]
      - 需要根据采样率还原时间序列
    典型 hex 示例：
      02 00 05 00 03 00 08 00 ...  (每个值 = low + high * 256)

--------------------------------------------------------------------------------
3. RSP 通道 (Respiration / 呼吸)
--------------------------------------------------------------------------------
    用途：呼吸相关生理数据
    方向：设备 → 主机（通知）
    数据格式：
      - 每包约 8-16 字节
      - 包含呼吸波形数据或呼吸率估算值
    用途说明：
      - 可用于呼吸训练同步
      - 部分设备也输出心率变异性(HRV)数据
    典型 hex 示例：
      5A 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00

--------------------------------------------------------------------------------
4. ALG 通道 (Algorithm / 算法指标)
--------------------------------------------------------------------------------
    用途：设备端算法处理后的神经反馈指标
    方向：设备 → 主机（通知）
    更新频率：约 1-2 Hz（每秒 1-2 包）

    ─── 标准帧格式 (EEG2/EEGM) ───
    总长度：43 字节 (86 hex 字符)

    字节 0:      前导字节 0xC0 (固定)
    字节 1-82:   频段能量数据 (20 对 × 4 字节 + 2 校验)
                 每对 = [ch1高8位, ch1低8位, ch2高8位, ch2低8位]
                 频段顺序: delta, theta, alpha, lowAlpha, hiAlpha,
                           smr, beta, hiBeta, gamma, acBeta
    字节 83-84:  相关性数据 (左/右脑 alpha 相关性)

    ─── Fabric 帧格式 (EEGS) ───
    总长度：45 字节 (90 hex 字符)
    字节 0:      前导 0xC0
    字节 1-2:    2 字节前缀（Fabric 特有）
    字节 3-84:   同标准帧的频段数据
    字节 85-86:  相关性数据

    ─── 解析后的指标 ───
    综合指标 (0-100):
      - focus:     专注度
      - stress:    压力指数
      - fatigue:   疲劳度
      - mindfulness: 正念/放松度

    频段能量 (μV²):
      - delta:  0.5-4 Hz
      - theta:  4-8 Hz
      - alpha:  8-13 Hz
      - beta:   13-30 Hz
      - gamma:  30-100 Hz

    衍生指标:
      - asy:    左右脑不对称指数 (alpha 对数差)
      - tbr:    theta/beta ratio
      - smr:    感觉运动节律 (12-15 Hz)
      - lowAlpha/hiAlpha: alpha 子频段
      - hiBeta/acBeta: beta 子频段

    ─── Legacy 协议格式 ───
    为兼容旧系统，ALG 数据也以 $HEX@\\r\\n 文本格式传输：
      "$C000E200A7..." → "$C000E200A7...@\\r\\n"

================================================================================
线程安全
================================================================================

HardwareDevice 不是线程安全的。
所有操作应该在同一个 asyncio 事件循环中执行。

通知回调在 BLE 线程中执行，如果需要更新 UI，
应该在回调中使用 asyncio.create_task() 或 queue 机制。

================================================================================
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Any,
)

from .interfaces import (
    BLEClient,
    BLEDevice,
    GATTService,
    GATTCharacteristic,
    NotificationCallback,
)
from .exceptions import (
    BLEError,
    BLEConnectionError,
    BLEConnectionTimeoutError,
    BLEServiceNotFoundError,
    BLECharacteristicNotFoundError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 默认 UUID 配置
# =============================================================================

# EEG 设备的标准 GATT UUID (从 constants.py 导入)
from .constants import (
    SERVICE_UUID,
    CHARACTERISTIC_UUID_CMD,
    CHARACTERISTIC_UUID_DATA_EEG,
    CHARACTERISTIC_UUID_DATA_RSP_INFO,
    CHARACTERISTIC_UUID_DATA_ALG,
)

# 保持向后兼容的别名
DEFAULT_SERVICE_UUID = SERVICE_UUID
DEFAULT_EEG_UUID = CHARACTERISTIC_UUID_DATA_EEG
DEFAULT_RSP_UUID = CHARACTERISTIC_UUID_DATA_RSP_INFO
DEFAULT_ALG_UUID = CHARACTERISTIC_UUID_DATA_ALG
DEFAULT_CMD_UUID = CHARACTERISTIC_UUID_CMD

# 设备类型
DEVICE_TYPE_EEG2 = "Dbay-EEG2"
DEVICE_TYPE_EEGM = "Dbay-EEGM"
DEVICE_TYPE_EEGS = "Dbay-EEGS"

# 协议模式
PROTOCOL_MODE_LEGACY = "legacy"
PROTOCOL_MODE_NEUROFEEDBACK = "neurofeedback"

# 设备类型对应的启动命令
DEVICE_START_COMMANDS = {
    DEVICE_TYPE_EEG2: bytes([0x05, 0x03]),  # Dbay-EEG2 标准启动
    DEVICE_TYPE_EEGM: bytes([0x05, 0x03]),  # Dbay-EEGM
    DEVICE_TYPE_EEGS: bytes([0x04, 0x01, 0x01, 0x00, 0x01]),  # Dbay-EEGS
}


# =============================================================================
# 数据解析器
# =============================================================================

@dataclass
class SignalMetrics:
    """
    解析后的神经反馈指标。

    包含注意力、压力、疲劳等综合指标和脑电频段能量。
    """
    # 综合指标 (0-100)
    focus: float = 0.0
    stress: float = 0.0
    fatigue: float = 0.0
    asy: float = 0.0

    # 脑电频段能量 (μV²)
    delta: float = 0.0
    theta: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    gamma: float = 0.0


def build_legacy_alg_frame(data: bytes) -> str:
    """
    把 ALG 原始字节转成旧版串口链路里的 ``$...@\\r\\n`` 文本。

    旧版协议通过串口传输，帧格式为 ``$HEX@\\r\\n``：
    - ``$`` 是帧头，表示一帧开始
    - 中间是大写十六进制字符串，每字节两位
    - ``@\\r\\n`` 是帧尾，表示一帧结束
    """
    return "${0}@\r\n".format(data.hex().upper())


def parse_alg_frame(raw_hex: str, device_type: str) -> SignalMetrics | None:
    """
    解析 ALG 帧的十六进制字符串为指标。

    Args:
        raw_hex: 大写十六进制字符串
        device_type: 设备类型

    Returns:
        SignalMetrics 或 None（解析失败时）
    """
    try:
        # 去掉帧头帧尾符号
        if raw_hex.startswith('$'):
            raw_hex = raw_hex[1:]
        if raw_hex.endswith('@'):
            raw_hex = raw_hex[:-1]

        # 解析指标数据
        # 格式: [focus, stress, fatigue, delta, theta, alpha, beta, gamma]
        # 每个值占2个hex字符 (1 byte)
        metrics = SignalMetrics()

        # 尝试多种解析方式
        if len(raw_hex) >= 16:
            # 固定格式: 每2个hex字符为一个值
            offset = 0
            metrics.focus = int(raw_hex[offset:offset+2], 16) if offset + 2 <= len(raw_hex) else 0
            offset += 2
            metrics.stress = int(raw_hex[offset:offset+2], 16) if offset + 2 <= len(raw_hex) else 0
            offset += 2
            metrics.fatigue = int(raw_hex[offset:offset+2], 16) if offset + 2 <= len(raw_hex) else 0
            offset += 2
            metrics.delta = int(raw_hex[offset:offset+4], 16) if offset + 4 <= len(raw_hex) else 0
            offset += 4
            metrics.theta = int(raw_hex[offset:offset+4], 16) if offset + 4 <= len(raw_hex) else 0
            offset += 4
            metrics.alpha = int(raw_hex[offset:offset+4], 16) if offset + 4 <= len(raw_hex) else 0
            offset += 4
            metrics.beta = int(raw_hex[offset:offset+4], 16) if offset + 4 <= len(raw_hex) else 0
            offset += 4
            metrics.gamma = int(raw_hex[offset:offset+4], 16) if offset + 4 <= len(raw_hex) else 0

        return metrics

    except Exception as e:
        logger.warning(f"解析 ALG 帧失败: {e}")
        return None


@dataclass
class DataParser:
    """
    数据解析器。

    维护 BLE ALG 通知的内存缓存，按协议模式生成解析后的数据。

    两种模式：
    - legacy：兼容旧版 ThreadMain / signal.js 注释中的结构
    - neurofeedback：兼容当前 websocketCallback.js 消费的结构

    neurofeedback 模式额外包含解析后的神经反馈指标。
    """

    protocol_mode: str = PROTOCOL_MODE_LEGACY
    """协议模式"""

    device_name: str = ""
    """设备名称"""

    device_type: str = DEVICE_TYPE_EEG2
    """设备类型"""

    # 运行时状态
    index: int = 0
    """通知序号，每收到一条 ALG 通知就自增 1"""

    update_eeg_flag: int = 0
    """legacy 模式：标记是否有新数据待消费，1 表示有，0 表示已消费"""

    alg_buf: list[int] = field(default_factory=list)
    """legacy 模式：最近一条 ALG 原始字节的十进制整数列表"""

    alg_string: str = ""
    """legacy 模式：最近一条 ALG 原始字节的 $HEX@\\r\\n 文本"""

    str_list: list[str] = field(default_factory=list)
    """neurofeedback 模式：累积的 hex 字符串列表"""

    _latest_metrics: SignalMetrics | None = field(default=None)
    """neurofeedback 模式：最近一条 ALG 解析后的指标"""

    def record_notification(self, label: str, data: bytearray) -> None:
        """
        记录一条通知数据。

        只处理 ALG 通道的数据，其他通道（EEG/RSP/CMD）直接忽略。
        EEG 和 RSP 通道的数据应通过 on_eeg() / on_rsp() 回调处理。

        Args:
            label: 通道标签，"ALG" 表示算法指标通道
            data: 原始字节数据
        """
        # 只处理 ALG 通道
        if label != "ALG":
            return

        # 转换为 bytes 和 hex 字符串
        raw = bytes(data)
        raw_hex = raw.hex().upper()

        # 更新序号
        self.index += 1

        # 更新 legacy 模式状态
        self.alg_buf = list(raw)
        self.alg_string = build_legacy_alg_frame(raw)
        self.update_eeg_flag = 1

        # 更新 neurofeedback 模式状态
        self.str_list.append(raw_hex)

        # 解析指标
        self._latest_metrics = parse_alg_frame(raw_hex, self.device_type)

    def consume_payload(self) -> dict | None:
        """
        按协议模式消费一份可发送的数据。

        - legacy 模式：只在有新数据时返回 payload，否则返回 None
        - neurofeedback 模式：每次都返回 payload，即使 str_list 为空

        Returns:
            payload dict 或 None（legacy 模式无新数据时）
        """
        # --- legacy 模式分支 ---
        if self.protocol_mode == PROTOCOL_MODE_LEGACY:
            if self.update_eeg_flag != 1:
                return None

            # 构造 legacy 协议 payload
            payload = {
                "update_eeg_flag": self.update_eeg_flag,
                "index": self.index,
                "alg_buf": list(self.alg_buf),
                "str": self.alg_string,
            }
            # 消费后清零 flag
            self.update_eeg_flag = 0
            return payload

        # --- neurofeedback 模式分支 ---
        payload = {
            "index": self.index,
            "str_list": list(self.str_list),
            "device_type": self.device_type,
            "device_name": self.device_name,
        }

        # 如果有解析后的指标，合并到 payload 中
        if self._latest_metrics is not None:
            payload["metrics"] = {
                "focus": self._latest_metrics.focus,
                "stress": self._latest_metrics.stress,
                "fatigue": self._latest_metrics.fatigue,
                "asy": self._latest_metrics.asy,
                "delta": self._latest_metrics.delta,
                "theta": self._latest_metrics.theta,
                "alpha": self._latest_metrics.alpha,
                "beta": self._latest_metrics.beta,
                "gamma": self._latest_metrics.gamma,
            }

        # 清空 str_list
        self.str_list = []
        return payload


# =============================================================================
# 数据类型别名
# =============================================================================

# 通道标签 - 用于区分不同的数据流
ChannelLabel = str
"""
通道标签，用于区分不同的数据流。

标准通道：
- "EEG" - 原始脑电波数据
- "RSP" - 呼吸相关数据
- "ALG" - 算法处理后的指标数据
- "CMD" - 命令响应数据

不同设备可能使用不同的通道集合。
"""

# 数据回调类型
DataCallback = Callable[[ChannelLabel, bytearray], None]
"""
数据回调函数签名。

参数:
    label: 数据通道标签（如 "EEG", "ALG"）
    data: 原始字节数据

示例:
    def on_data(label: str, data: bytearray):
        print(f"[{label}] {data.hex()}")

    device.on_data(on_data)
"""

# EEG 数据回调
EEGCallback = Callable[[bytearray], None]
"""
EEG 数据回调函数签名。

只处理 EEG 通道的数据。

示例:
    def on_eeg(data: bytearray):
        print(f"EEG: {data.hex()}")
"""

# 算法指标回调
ALGCallback = Callable[[bytearray], None]
"""
ALG 数据回调函数签名。

ALG 通道包含解析后的神经反馈指标。
"""

# =============================================================================
# 内部数据结构
# =============================================================================

@dataclass
class ChannelConfig:
    """
    通道配置。

    定义一个数据通道的 UUID 和属性。
    """

    label: ChannelLabel
    """通道标签（如 "EEG", "ALG"）"""

    uuid: str
    """BLE 特征的 UUID"""

    notify: bool = True
    """是否订阅通知"""

    @property
    def enabled(self) -> bool:
        """通道是否启用。"""
        return self.notify


# =============================================================================
# HardwareDevice 类
# =============================================================================

class HardwareDevice:
    """
    硬件设备抽象类。

    封装了 BLE 设备连接的完整流程，提供简洁的业务接口。

    主要功能：
    - 自动扫描和连接设备
    - GATT 服务发现
    - 多通道数据订阅
    - 启动命令发送
    - 自动清理和断开

    使用建议：
    - 使用上下文管理器（async with）确保正确清理
    - 注册回调函数处理接收到的数据
    - 调用 start_streaming() 开始接收数据

    示例:
        async with HardwareDevice(address="...") as device:
            device.on_data(my_callback)
            device.start_streaming()
            await asyncio.sleep(30)
    """

    def __init__(
        self,
        address: str,
        name: str | None = None,
        device_type: str = DEVICE_TYPE_EEG2,
        service_uuid: str | None = None,
        eeg_uuid: str | None = None,
        rsp_uuid: str | None = None,
        alg_uuid: str | None = None,
        cmd_uuid: str | None = None,
        client: BLEClient | None = None,
        scan_timeout: float = 5.0,
        connect_timeout: float = 10.0,
    ):
        """
        初始化硬件设备。

        参数:
            address: 蓝牙设备地址（必需）
                    格式：XX:XX:XX:XX:XX:XX 或 XX-XX-XX-XX-XX-XX
                    不区分大小写

            name: 设备名称（可选，用于日志和识别）
                    如果已知可以传入，不知道可以设为 None

            device_type: 设备类型（决定协议解析方式）
                    - "Dbay-EEG2": 标准双通道 EEG
                    - "Dbay-EEGM": 中端版本
                    - "Dbay-EEGS": Fabric 固件版本
                    默认: "Dbay-EEG2"

            service_uuid: GATT 服务 UUID
                    默认使用 EEG 设备的标准 UUID
                    如需自定义可覆盖

            eeg_uuid: EEG 数据通道的 UUID
                    默认使用标准 EEG 特征 UUID

            rsp_uuid: RSP 数据通道的 UUID
                    默认使用标准 RSP 特征 UUID

            alg_uuid: ALG 算法数据通道的 UUID
                    默认使用标准 ALG 特征 UUID

            cmd_uuid: 命令写入特征的 UUID
                    默认使用标准 CMD 特征 UUID

            client: BLE 客户端实例（可选）
                    如果不提供，将在连接时创建
                    用于注入 mock 客户端进行测试

            scan_timeout: 扫描超时时间（秒）
                    默认: 5.0 秒

            connect_timeout: 连接超时时间（秒）
                    默认: 10.0 秒

        示例:
            # 使用默认配置
            device = HardwareDevice(address="AA:BB:CC:DD:EE:30")

            # 自定义 UUID
            device = HardwareDevice(
                address="AA:BB:CC:DD:EE:30",
                service_uuid="12345678-1234-5678-1234-567812345678",
                eeg_uuid="12345678-1234-5678-1234-567812345679",
            )
        """
        # 设备基本信息
        self.address = address.upper().replace("-", ":")
        """蓝牙地址，统一转为大写冒号格式"""

        self.name = name or "<未命名设备>"
        """设备名称"""

        self.device_type = device_type
        """设备类型，决定协议解析方式"""

        # UUID 配置
        self.service_uuid = service_uuid or DEFAULT_SERVICE_UUID
        self.eeg_uuid = eeg_uuid or DEFAULT_EEG_UUID
        self.rsp_uuid = rsp_uuid or DEFAULT_RSP_UUID
        self.alg_uuid = alg_uuid or DEFAULT_ALG_UUID
        self.cmd_uuid = cmd_uuid or DEFAULT_CMD_UUID

        # 通道配置列表
        self._channels: List[ChannelConfig] = []
        self._init_channels()

        # BLE 客户端（由适配器提供）
        self._client: BLEClient | None = client

        # 超时配置
        self.scan_timeout = scan_timeout
        self.connect_timeout = connect_timeout

        # 回调函数
        self._data_callbacks: List[DataCallback] = []
        """通用的数据回调列表（所有通道都会触发）"""

        self._channel_callbacks: Dict[ChannelLabel, List[Callable]] = {}
        """按通道分类的回调 {label: [callbacks]}"""

        # 连接状态
        self._is_connected = False
        self._is_streaming = False

        # GATT 对象缓存
        self._service: GATTService | None = None
        self._notify_chars: Dict[ChannelLabel, GATTCharacteristic] = {}
        self._cmd_char: GATTCharacteristic | None = None

        # 数据解析器
        self._parser: DataParser = DataParser(
            protocol_mode=PROTOCOL_MODE_LEGACY,
            device_name=self.name,
            device_type=self.device_type,
        )
        """数据解析器，用于解析 ALG 通道的原始字节"""

        # 日志
        self._logger = logging.getLogger(f"{__name__}.{self.name}")

    # =========================================================================
    # 通道配置
    # =========================================================================

    def _init_channels(self) -> None:
        """
        初始化通道配置。

        根据设备支持的通道配置通知订阅列表。
        默认订阅所有通道：EEG、RSP、ALG。
        """
        self._channels = [
            ChannelConfig(label="EEG", uuid=self.eeg_uuid, notify=True),
            ChannelConfig(label="RSP", uuid=self.rsp_uuid, notify=True),
            ChannelConfig(label="ALG", uuid=self.alg_uuid, notify=True),
        ]

    def get_channel(self, label: ChannelLabel) -> ChannelConfig | None:
        """
        获取指定通道的配置。

        参数:
            label: 通道标签

        返回:
            通道配置，如果不存在返回 None
        """
        for ch in self._channels:
            if ch.label == label:
                return ch
        return None

    # =========================================================================
    # 回调注册
    # =========================================================================

    def on_data(self, callback: DataCallback) -> None:
        """
        注册通用数据回调。

        所有通道的数据都会触发这个回调。
        适合需要统一处理所有数据的场景。

        参数:
            callback: 回调函数，签名为 (label: str, data: bytearray)

        示例:
            def on_any_data(label: str, data: bytearray):
                print(f"[{label}] {data.hex()}")

            device.on_data(on_any_data)
        """
        if callback not in self._data_callbacks:
            self._data_callbacks.append(callback)

    def on_channel(self, label: ChannelLabel, callback: Callable) -> None:
        """
        注册指定通道的回调。

        只处理特定通道的数据。
        可以为同一通道注册多个回调。

        参数:
            label: 通道标签（如 "EEG", "ALG"）
            callback: 回调函数

        示例:
            def on_eeg(data: bytearray):
                print(f"EEG: {data.hex()}")

            device.on_channel("EEG", on_eeg)
        """
        if label not in self._channel_callbacks:
            self._channel_callbacks[label] = []
        if callback not in self._channel_callbacks[label]:
            self._channel_callbacks[label].append(callback)

    def on_eeg(self, callback: EEGCallback) -> None:
        """
        注册 EEG 通道的回调。

        便捷方法，等价于 on_channel("EEG", callback)。

        参数:
            callback: 回调函数，签名为 (data: bytearray)

        示例:
            device.on_eeg(lambda data: print(f"EEG: {data.hex()}"))
        """
        self.on_channel("EEG", callback)

    def on_alg(self, callback: ALGCallback) -> None:
        """
        注册 ALG 通道的回调。

        便捷方法，等价于 on_channel("ALG", callback)。

        参数:
            callback: 回调函数，签名为 (data: bytearray)

        示例:
            device.on_alg(lambda data: process_alg_data(data))
        """
        self.on_channel("ALG", callback)

    # =========================================================================
    # 数据解析
    # =========================================================================

    def set_protocol_mode(self, mode: str) -> None:
        """
        设置协议模式。

        Args:
            mode: "legacy" 或 "neurofeedback"
                - legacy: 兼容旧版协议，consume_payload 只在新数据到达时返回
                - neurofeedback: 当前协议，每次 consume 都返回 payload
        """
        self._parser.protocol_mode = mode
        self._logger.info(f"协议模式已设置为: {mode}")

    def get_payload(self) -> dict | None:
        """
        消费一份解析后的数据负载。

        返回数据格式取决于当前协议模式：
        - legacy 模式: {"update_eeg_flag": int, "index": int, "alg_buf": list, "str": str}
        - neurofeedback 模式: {"index": int, "str_list": list, "device_type": str, "metrics": dict}

        Returns:
            解析后的数据负载，或 None（legacy 模式无新数据时）
        """
        return self._parser.consume_payload()

    @property
    def latest_metrics(self) -> SignalMetrics | None:
        """
        获取最近解析的神经反馈指标。

        只在 neurofeedback 模式下有实际意义。
        """
        return self._parser._latest_metrics

    @property
    def protocol_index(self) -> int:
        """
        获取当前协议序号。

        每收到一条 ALG 数据就递增 1。
        """
        return self._parser.index

    def _trigger_callbacks(self, label: ChannelLabel, data: bytearray) -> None:
        """
        触发数据回调。

        内部方法，当收到数据时由通知处理器调用。

        参数:
            label: 通道标签
            data: 原始字节数据
        """
        # 更新解析器状态
        self._parser.record_notification(label, data)

        # 触发通用回调
        for callback in self._data_callbacks:
            try:
                callback(label, data)
            except Exception as e:
                self._logger.error(f"回调执行错误 [{label}]: {e}")

        # 触发通道特定回调
        if label in self._channel_callbacks:
            for callback in self._channel_callbacks[label]:
                try:
                    callback(data)
                except Exception as e:
                    self._logger.error(f"通道回调执行错误 [{label}]: {e}")

    # =========================================================================
    # 连接管理
    # =========================================================================

    async def connect(
        self,
        client: BLEClient | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        连接到 BLE 设备。

        执行完整的连接流程：
        1. 如果没有客户端，创建一个（通过适配器）
        2. 建立 BLE 连接
        3. 发现 GATT 服务
        4. 查找目标服务

        参数:
            client: BLE 客户端实例（可选，会覆盖构造函数中的 client）
            timeout: 连接超时时间（秒），None 则使用默认值

        异常:
            BLEConnectionTimeoutError: 连接超时
            BLEConnectionError: 连接失败
            BLEServiceNotFoundError: 未找到目标服务
        """
        timeout = timeout or self.connect_timeout

        # 获取或创建客户端
        if client is not None:
            self._client = client
        elif self._client is None:
            self._client = await self._create_client()

        # 连接设备
        self._logger.info(f"正在连接到 {self.name} ({self.address})...")
        try:
            await self._client.connect(timeout=timeout)
        except Exception as e:
            raise BLEConnectionError(
                f"连接失败: {e}",
                device_address=self.address,
            ) from e

        if not self._client.is_connected:
            raise BLEConnectionError(
                "连接后 is_connected 为 False",
                device_address=self.address,
            )

        self._logger.info(f"已连接到 {self.name}")

        # 发现服务
        self._logger.info("正在发现 GATT 服务...")
        try:
            services = await self._client.get_services()
        except Exception as e:
            await self._client.disconnect()
            raise BLEError(f"服务发现失败: {e}") from e

        # 查找目标服务
        self._service = services.get_service(self.service_uuid)
        if self._service is None:
            await self._client.disconnect()
            raise BLEServiceNotFoundError(
                f"未找到服务: {self.service_uuid}",
                service_uuid=self.service_uuid,
                device_address=self.address,
            )

        self._logger.info(f"已找到服务: {self.service_uuid}")
        self._is_connected = True

    async def disconnect(self) -> None:
        """
        断开与设备的连接。

        安全地清理所有资源：
        1. 停止所有通知订阅
        2. 断开 BLE 连接

        建议使用上下文管理器:
            async with device:
                ...

        这会自动处理断开，即使发生异常也会正确清理。
        """
        if not self._is_connected:
            return

        self._logger.info("正在断开连接...")

        # 停止流（如果正在运行）
        if self._is_streaming:
            try:
                await self.stop_streaming()
            except Exception as e:
                self._logger.warning(f"停止流失败: {e}")

        # 停止所有通知订阅
        for label, char in self._notify_chars.items():
            try:
                await self._client.stop_notify(char)
                self._logger.debug(f"已停止通知: {label}")
            except Exception as e:
                self._logger.warning(f"停止通知失败 [{label}]: {e}")

        # 断开连接
        try:
            await self._client.disconnect()
            self._logger.info("已断开连接")
        except Exception as e:
            self._logger.warning(f"断开连接时出错: {e}")
        finally:
            self._is_connected = False
            self._notify_chars.clear()
            self._service = None

    async def _create_client(self) -> BLEClient:
        """
        创建 BLE 客户端。

        内部方法，由具体平台适配器实现。
        默认使用 bleak 适配器。

        返回:
            BLEClient 实例

        异常:
            BLEError: 无法创建客户端（bleak 未安装等）
        """
        # 延迟导入，避免在未安装 bleak 时报错
        try:
            from .impl.bleak_adapter import BleakBLEClient
            return BleakBLEClient(address=self.address)
        except ImportError as e:
            raise BLEError(
                f"无法创建 BLE 客户端: {e}\n"
                "请安装 bleak: pip install bleak"
            ) from e

    # =========================================================================
    # 流式数据订阅
    # =========================================================================

    def start_streaming(self, send_start_command: bool = True) -> None:
        """
        开始接收数据流。

        订阅所有已配置的通道，开始接收 BLE 通知。
        这个方法是同步的，实际订阅在后台异步进行。

        参数:
            send_start_command: 是否发送启动命令
                    某些设备需要收到启动命令才开始发送数据
                    如果设为 False，需要手动通过其他方式启动设备

        注意:
            - 必须先调用 connect() 连接设备
            - 订阅后数据会通过回调函数传递
            - 如需停止，调用 stop_streaming()

        示例:
            device = HardwareDevice(address="...")
            await device.connect()

            device.on_eeg(lambda data: print(f"EEG: {data.hex()}"))
            device.start_streaming()

            await asyncio.sleep(30)  # 持续接收
        """
        if not self._is_connected:
            raise BLEError("设备未连接，请先调用 connect()")

        if self._is_streaming:
            self._logger.warning("已经在接收数据流")
            return

        self._is_streaming = True
        self._logger.info("开始订阅通知...")

        # 启动订阅任务（在后台异步执行）
        asyncio.create_task(self._subscribe_all(send_start_command))

    async def _subscribe_all(self, send_start_command: bool) -> None:
        """
        执行所有通道的通知订阅。

        内部异步方法。
        """
        assert self._service is not None, "服务未初始化"
        assert self._client is not None, "客户端未初始化"

        # 订阅所有通道的通知
        for channel in self._channels:
            if not channel.notify:
                continue

            char = self._service.get_characteristic(channel.uuid)
            if char is None:
                self._logger.warning(
                    f"未找到通道 [{channel.label}] 的特征: {channel.uuid}"
                )
                continue

            # 构造通知回调
            handler = self._build_notification_handler(channel.label)

            try:
                await self._client.start_notify(char, handler)
                self._notify_chars[channel.label] = char
                self._logger.info(f"已订阅 [{channel.label}]: {channel.uuid}")
            except Exception as e:
                self._logger.error(f"订阅 [{channel.label}] 失败: {e}")

        # 发送启动命令
        if send_start_command:
            await self._send_start_command()

    def _build_notification_handler(self, label: ChannelLabel) -> NotificationCallback:
        """
        构造通知回调闭包。

        参数:
            label: 通道标签

        返回:
            符合 NotificationCallback 签名的闭包函数
        """
        def handler(sender: int, data: bytearray) -> None:
            # 记录时间戳
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

            # 打印调试信息
            hex_data = data.hex(" ")
            self._logger.debug(f"[{timestamp}] [{label}] len={len(data)} data={hex_data}")

            # 触发业务回调
            self._trigger_callbacks(label, data)

        return handler

    async def _send_start_command(self) -> None:
        """
        发送启动命令。

        内部方法，向设备发送启动数据流的命令。
        """
        if self.cmd_uuid is None:
            return

        assert self._service is not None, "服务未初始化"
        assert self._client is not None, "客户端未初始化"

        cmd_char = self._service.get_characteristic(self.cmd_uuid)
        if cmd_char is None:
            self._logger.warning(f"未找到命令特征: {self.cmd_uuid}")
            return

        # 获取启动命令
        start_cmd = DEVICE_START_COMMANDS.get(
            self.device_type,
            DEVICE_START_COMMANDS[DEVICE_TYPE_EEG2]
        )

        try:
            await self._client.write_gatt_char(cmd_char, start_cmd, response=True)
            self._logger.info(f"已发送启动命令: {start_cmd.hex(' ')}")
        except Exception as e:
            self._logger.error(f"发送启动命令失败: {e}")

    async def stop_streaming(self) -> None:
        """
        停止接收数据流。

        取消所有通道的通知订阅。
        不会断开与设备的连接。
        """
        if not self._is_streaming:
            return

        self._logger.info("正在停止订阅...")

        for label, char in self._notify_chars.items():
            try:
                await self._client.stop_notify(char)
                self._logger.debug(f"已停止 [{label}] 的订阅")
            except Exception as e:
                self._logger.warning(f"停止 [{label}] 订阅失败: {e}")

        self._notify_chars.clear()
        self._is_streaming = False
        self._logger.info("已停止订阅")

    # =========================================================================
    # 上下文管理器支持
    # =========================================================================

    async def __aenter__(self) -> "HardwareDevice":
        """
        上下文管理器入口。

        用法:
            async with HardwareDevice(address="...") as device:
                device.on_data(my_callback)
                device.start_streaming()
                await asyncio.sleep(30)

        返回:
            self（已连接的设备实例）
        """
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        上下文管理器退出。

        确保即使发生异常也会正确断开连接。
        """
        await self.disconnect()

    # =========================================================================
    # 属性
    # =========================================================================

    @property
    def is_connected(self) -> bool:
        """设备是否已连接。"""
        return self._is_connected

    @property
    def is_streaming(self) -> bool:
        """是否正在接收数据流。"""
        return self._is_streaming

    @property
    def connected_address(self) -> str | None:
        """已连接设备的地址（未连接时返回 None）。"""
        if self._is_connected and self._client:
            return self.address
        return None

    # =========================================================================
    # 调试辅助
    # =========================================================================

    def get_services_tree(self) -> List[Dict[str, Any]]:
        """
        获取 GATT 服务树（用于调试）。

        返回:
            服务树列表，每个元素包含服务、特征、描述符的信息
        """
        if not self._is_connected or self._service is None:
            return []

        result = []
        for service in [self._service]:  # 只返回当前服务
            service_info = {
                "uuid": service.uuid,
                "description": service.description,
                "characteristics": []
            }

            for char in service.characteristics:
                char_info = {
                    "uuid": char.uuid,
                    "description": char.description,
                    "properties": list(char.properties),
                    "descriptors": []
                }

                for desc in char.descriptors:
                    char_info["descriptors"].append({
                        "handle": desc.handle,
                        "uuid": desc.uuid,
                    })

                service_info["characteristics"].append(char_info)

            result.append(service_info)

        return result

    def __repr__(self) -> str:
        """调试友好的字符串表示。"""
        status = []
        if self._is_connected:
            status.append("connected")
        if self._is_streaming:
            status.append("streaming")
        if not status:
            status.append("disconnected")

        return (
            f"<HardwareDevice "
            f"name={self.name!r} "
            f"address={self.address} "
            f"type={self.device_type} "
            f"status={', '.join(status)}>"
        )

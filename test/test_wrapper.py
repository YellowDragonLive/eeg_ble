"""BLEWrapper FastAPI 测试。

模拟 FastAPI 应用使用 BLEWrapper 类，测试接口正确性。
输出测试报告。

Usage:
    python -m ble.test.test_wrapper
"""

import asyncio
import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

# 添加父目录到路径
sys.path.insert(0, "..")

from ble import (
    BLEWrapper,
    BLESearchError,
    BLEConnectError,
    BLEStateError,
    HardwareDevice,
)

# =============================================================================
# 日志配置
# =============================================================================

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 每次运行生成带时间戳的日志文件
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"test_wrapper_{_log_timestamp}.log"

# 配置根日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("test_wrapper")


# =============================================================================
# 测试报告
# =============================================================================

class TestReport:
    """测试报告生成器。"""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = datetime.now()

    def add_pass(self, name: str, details: str = ""):
        self.results.append({
            "name": name,
            "status": "PASS",
            "details": details,
        })

    def add_fail(self, name: str, error: str, details: str = ""):
        self.results.append({
            "name": name,
            "status": "FAIL",
            "error": error,
            "details": details,
        })

    def add_skip(self, name: str, reason: str):
        self.results.append({
            "name": name,
            "status": "SKIP",
            "reason": reason,
        })

    def print_report(self):
        """打印测试报告。"""
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        total = len(self.results)

        print("\n" + "=" * 70)
        print("  BLEWrapper FastAPI 模拟测试报告")
        print("=" * 70)
        print(f"  测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  总测试数: {total}")
        print(f"  通过: {passed} ✓")
        print(f"  失败: {failed} ✗")
        print(f"  跳过: {skipped} ⊘")
        print("=" * 70)

        for i, r in enumerate(self.results, 1):
            status_icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘"}.get(r["status"], "?")
            print(f"\n[{i}] {r['name']} ... {status_icon} {r['status']}")

            if r["status"] == "PASS":
                if r.get("details"):
                    print(f"    {r['details']}")

            elif r["status"] == "FAIL":
                print(f"    错误: {r.get('error', 'Unknown error')}")
                if r.get("details"):
                    print(f"    详情: {r['details']}")

            elif r["status"] == "SKIP":
                print(f"    原因: {r.get('reason', 'Unknown')}")

        print("\n" + "=" * 70)
        print(f"  结果: {'全部通过 ✓' if failed == 0 else f'失败 {failed} 项 ✗'}")
        print("=" * 70 + "\n")

        return failed == 0


report = TestReport()


# =============================================================================
# Mock 数据
# =============================================================================

MOCK_DEVICES = [
    {
        "name": "Dbay-EEG2",
        "address": "AA:BB:CC:DD:EE:30",
        "rssi": -65,
        "raw": {"address_type": "random", "details": {}},
    },
    {
        "name": "Dbay-EEG2",
        "address": "AA:BB:CC:DD:EE:31",
        "rssi": -72,
        "raw": {"address_type": "random", "details": {}},
    },
    {
        "name": None,
        "address": "11:22:33:44:55:66",
        "rssi": -85,
        "raw": {"address_type": "public", "details": {}},
    },
]

MOCK_METRICS = {
    "focus": 75.5,
    "stress": 23.0,
    "fatigue": 15.0,
    "asy": 0.12,
    "delta": 125.5,
    "theta": 89.0,
    "alpha": 156.2,
    "beta": 78.3,
    "gamma": 45.0,
}


# =============================================================================
# 测试用例
# =============================================================================

async def test_import():
    """测试 1: 模块导入"""
    try:
        from ble import BLEWrapper, BLESearchError, BLEConnectError, BLEStateError
        report.add_pass("模块导入", "BLEWrapper 和异常类导入成功")
    except ImportError as e:
        report.add_fail("模块导入", str(e))
    except Exception as e:
        report.add_fail("模块导入", str(e), traceback.format_exc())


async def test_init():
    """测试 2: 实例初始化"""
    try:
        ble = BLEWrapper()
        assert ble is not None
        assert ble.is_connected == False
        assert ble.is_streaming == False
        assert ble.connected_address is None
        report.add_pass("实例初始化", f"BLEWrapper() 创建成功，状态: {ble}")
    except Exception as e:
        report.add_fail("实例初始化", str(e), traceback.format_exc())


async def test_init_with_params():
    """测试 3: 带参数初始化"""
    try:
        ble = BLEWrapper(
            device_type="Dbay-EEGM",
            connect_timeout=15.0,
        )
        assert ble is not None
        report.add_pass("带参数初始化", "支持 device_type, connect_timeout 参数")
    except Exception as e:
        report.add_fail("带参数初始化", str(e), traceback.format_exc())


async def test_search_mock():
    """测试 4: 搜索设备 (Mock)"""
    try:
        with patch("ble.wrapper.BleakBLEScanner") as mock_scanner_class:
            # 创建 mock 设备
            mock_devices = []
            for d in MOCK_DEVICES:
                mock_dev = MagicMock()
                mock_dev.name = d["name"]
                mock_dev.address = d["address"]
                mock_dev.rssi = d["rssi"]
                mock_dev._raw_device = MagicMock()
                mock_devices.append(mock_dev)

            # 设置 mock
            mock_scanner = MagicMock()
            mock_scanner.discover = AsyncMock(return_value=mock_devices)
            mock_scanner_class.return_value = mock_scanner

            # 测试
            ble = BLEWrapper()
            result = await ble.search(timeout=3.0)

            # 验证
            assert isinstance(result, list), "返回值应该是列表"
            assert len(result) == 3, f"应该返回 3 个设备，实际: {len(result)}"

            # 验证格式
            for item in result:
                assert "name" in item, "缺少 name 字段"
                assert "address" in item, "缺少 address 字段"
                assert "rssi" in item, "缺少 rssi 字段"
                assert "raw" in item, "缺少 raw 字段"

            # 日志记录搜索结果
            logger.info(f"搜索完成，发现 {len(result)} 个设备:")
            for i, device in enumerate(result, 1):
                logger.info(f"  [{i}] {device['name'] or '(无名称)'} @ {device['address']} (RSSI: {device['rssi']} dBm)")

            report.add_pass(
                "搜索设备 (Mock)",
                f"返回 {len(result)} 个设备，格式正确"
            )
    except AssertionError as e:
        report.add_fail("搜索设备 (Mock)", str(e), traceback.format_exc())
    except Exception as e:
        report.add_fail("搜索设备 (Mock)", str(e), traceback.format_exc())


async def test_callback_registration():
    """测试 5: 回调注册"""
    try:
        ble = BLEWrapper()
        callback_data_called = []
        callback_metrics_called = []

        def on_data(channel, data):
            callback_data_called.append((channel, data))

        def on_metrics(focus, stress, fatigue, **kwargs):
            callback_metrics_called.append({
                "focus": focus,
                "stress": stress,
                "fatigue": fatigue,
            })

        ble.on_data(on_data)
        ble.on_metrics(on_metrics)

        # 验证回调被注册
        assert len(ble._raw_data_callbacks) == 1
        assert len(ble._metrics_callbacks) == 1

        # 测试多次注册（应该去重）
        ble.on_data(on_data)
        assert len(ble._raw_data_callbacks) == 1

        # 测试清除
        ble.clear_callbacks()
        assert len(ble._raw_data_callbacks) == 0
        assert len(ble._metrics_callbacks) == 0

        report.add_pass(
            "回调注册",
            "on_data/on_metrics 注册成功，支持去重和清除"
        )
    except Exception as e:
        report.add_fail("回调注册", str(e), traceback.format_exc())


async def test_start_without_connect():
    """测试 6: 未连接时调用 start()"""
    try:
        ble = BLEWrapper()
        try:
            ble.start()
            report.add_fail("未连接时调用 start()", "应该抛出 BLEStateError")
        except BLEStateError as e:
            report.add_pass("未连接时调用 start()", f"正确抛出 BLEStateError: {e}")
    except Exception as e:
        report.add_fail("未连接时调用 start()", str(e), traceback.format_exc())


async def test_stop_without_streaming():
    """测试 7: 非传输状态调用 stop()"""
    try:
        ble = BLEWrapper()
        # 未连接时 stop 不应该报错
        ble.stop()
        report.add_pass("非传输状态调用 stop()", "不会报错，安全")
    except Exception as e:
        report.add_fail("非传输状态调用 stop()", str(e), traceback.format_exc())


async def test_connect_mock():
    """测试 8: 连接设备 (Mock)"""
    try:
        ble = BLEWrapper()

        # Mock HardwareDevice
        mock_device = MagicMock(spec=HardwareDevice)
        mock_device.address = MOCK_DEVICES[0]["address"]
        mock_device.connect = AsyncMock()
        mock_device.disconnect = AsyncMock()
        mock_device.start_streaming = MagicMock()
        mock_device.stop_streaming = AsyncMock()
        mock_device.on_data = MagicMock()
        mock_device.latest_metrics = None

        with patch("ble.wrapper.HardwareDevice", return_value=mock_device):
            await ble.connect(MOCK_DEVICES[0]["address"])

        assert ble.is_connected == True
        assert ble.connected_address == MOCK_DEVICES[0]["address"]

        report.add_pass(
            "连接设备 (Mock)",
            f"连接到 {ble.connected_address}，状态: {ble.is_connected}"
        )
    except Exception as e:
        report.add_fail("连接设备 (Mock)", str(e), traceback.format_exc())


async def test_repr():
    """测试 9: __repr__ 方法"""
    try:
        ble = BLEWrapper()
        repr_str = repr(ble)
        assert "BLEWrapper" in repr_str
        assert "disconnected" in repr_str

        report.add_pass("__repr__ 方法", f"输出: {repr_str}")
    except Exception as e:
        report.add_fail("__repr__ 方法", str(e), traceback.format_exc())


async def test_destroy():
    """测试 10: 销毁实例"""
    try:
        ble = BLEWrapper()

        # Mock 连接状态
        ble._is_connected = True
        ble._is_streaming = True

        mock_device = MagicMock()
        mock_device.disconnect = AsyncMock()
        ble._device = mock_device

        await ble.destroy()

        assert ble.is_connected == False
        assert ble.is_streaming == False
        assert ble._device is None

        report.add_pass("销毁实例", "正确清理所有状态和资源")
    except Exception as e:
        report.add_fail("销毁实例", str(e), traceback.format_exc())


async def test_fastapi_usage_pattern():
    """测试 11: FastAPI 使用模式 (集成测试)"""
    try:
        # 模拟 FastAPI 应用场景
        ble = BLEWrapper()

        # 模拟数据存储
        received_data: List[Dict] = []
        received_metrics: List[Dict] = []

        # 注册回调
        def on_data(channel: str, data: bytearray):
            received_data.append({
                "channel": channel,
                "data": data.hex(),
                "timestamp": datetime.now().isoformat(),
            })
            logger.info(f"[接收原始数据] 通道: {channel}, 长度: {len(data)} 字节, 数据: {data.hex()}")

        def on_metrics(focus: float, stress: float, fatigue: float, **kwargs):
            received_metrics.append({
                "focus": focus,
                "stress": stress,
                "fatigue": fatigue,
                "timestamp": datetime.now().isoformat(),
            })
            logger.info(f"[接收指标数据] 专注: {focus:.1f}, 压力: {stress:.1f}, 疲劳: {fatigue:.1f}")
            if kwargs:
                logger.info(f"  [扩展指标] delta: {kwargs.get('delta')}, theta: {kwargs.get('theta')}, "
                           f"alpha: {kwargs.get('alpha')}, beta: {kwargs.get('beta')}, gamma: {kwargs.get('gamma')}, "
                           f"asy: {kwargs.get('asy')}")

        ble.on_data(on_data)
        ble.on_metrics(on_metrics)

        # 模拟触发回调
        for cb in ble._raw_data_callbacks:
            cb("ALG", bytearray(b"\xC0\x01\x02"))

        for cb in ble._metrics_callbacks:
            cb(
                focus=75.5,
                stress=23.0,
                fatigue=15.0,
                asy=0.12,
                delta=125.5,
                theta=89.0,
                alpha=156.2,
                beta=78.3,
                gamma=45.0,
            )

        # 验证
        assert len(received_data) == 1
        assert received_data[0]["channel"] == "ALG"
        assert len(received_metrics) == 1
        assert received_metrics[0]["focus"] == 75.5

        report.add_pass(
            "FastAPI 使用模式",
            f"模拟 FastAPI 场景成功，收到 {len(received_data)} 条数据、{len(received_metrics)} 条指标"
        )
    except Exception as e:
        report.add_fail("FastAPI 使用模式", str(e), traceback.format_exc())


async def test_exception_types():
    """测试 12: 异常类型"""
    try:
        # 验证异常类继承关系
        from ble import BLEError

        assert issubclass(BLESearchError, BLEError)
        assert issubclass(BLEConnectError, BLEError)
        assert issubclass(BLEStateError, BLEError)

        # 验证异常可以抛出和捕获
        try:
            raise BLESearchError("搜索失败测试")
        except BLEError as e:
            assert isinstance(e, BLESearchError)
            assert str(e) == "搜索失败测试"

        report.add_pass(
            "异常类型",
            "BLESearchError, BLEConnectError, BLEStateError 正确继承自 BLEError"
        )
    except Exception as e:
        report.add_fail("异常类型", str(e), traceback.format_exc())


# =============================================================================
# 主测试函数
# =============================================================================

async def run_all_tests():
    """运行所有测试。"""
    print("\n开始 BLEWrapper FastAPI 模拟测试...\n")

    tests = [
        test_import,
        test_init,
        test_init_with_params,
        test_search_mock,
        test_callback_registration,
        test_start_without_connect,
        test_stop_without_streaming,
        test_connect_mock,
        test_repr,
        test_destroy,
        test_fastapi_usage_pattern,
        test_exception_types,
    ]

    for test in tests:
        try:
            await test()
        except Exception as e:
            report.add_fail(test.__name__, str(e), traceback.format_exc())

    return report.print_report()


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

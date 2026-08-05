"""BLEWrapper 真实硬件测试 - 完整流程自动化测试。

自动执行: 搜索 -> 连接 -> 接收数据(30s) -> 断开 -> 下一个设备

Usage:
    # 自动测试所有找到的 Dbay 设备
    python -m ble.test.hardware_test

    # 指定设备类型
    python -m ble.test.hardware_test --type Dbay-EEGM

    # 指定测试时长
    python -m ble.test.hardware_test --duration 60

    # 指定设备地址(只测试一个)
    python -m ble.test.hardware_test --address AA:BB:CC:DD:EE:30
"""

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ble import BLEWrapper

# =============================================================================
# 日志配置
# =============================================================================

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"hardware_{_log_timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("hardware_test")

# 全局状态
stop_requested = False


def signal_handler(sig, frame):
    """处理 Ctrl+C."""
    global stop_requested
    logger.info("\n收到停止信号，正在关闭...")
    stop_requested = True


async def test_device(address: str, device_type: str, duration: float) -> dict:
    """测试单个设备的完整流程.

    流程: 连接 -> 接收数据(duration秒) -> 断开
    返回测试结果统计.
    """
    global stop_requested

    result = {
        "address": address,
        "connected": False,
        "data_count": 0,
        "metrics_count": 0,
        "error": None,
        "duration": 0,
    }

    ble = BLEWrapper(device_type=device_type)
    data_count = 0
    metrics_count = 0

    # 回调函数
    def on_data(channel: str, data: bytearray):
        nonlocal data_count
        data_count += 1
        result["data_count"] = data_count
        logger.info(f"  [数据] {channel}: {data.hex()[:32]}{'...' if len(data) > 16 else ''}")

    def on_metrics(focus: float, stress: float, fatigue: float, **kwargs):
        nonlocal metrics_count
        metrics_count += 1
        result["metrics_count"] = metrics_count
        logger.info(f"  [指标] 专注:{focus:.1f} 压力:{stress:.1f} 疲劳:{fatigue:.1f}")
        if kwargs:
            logger.info(f"        δ={kwargs.get('delta', 0):.1f} "
                       f"θ={kwargs.get('theta', 0):.1f} "
                       f"α={kwargs.get('alpha', 0):.1f} "
                       f"β={kwargs.get('beta', 0):.1f} "
                       f"γ={kwargs.get('gamma', 0):.1f} "
                       f"不对称={kwargs.get('asy', 0):.3f}")

    ble.on_data(on_data)
    ble.on_metrics(on_metrics)

    start_time = datetime.now()

    try:
        # 连接
        logger.info(f"  -> 连接...")
        await ble.connect(address)
        result["connected"] = True
        logger.info(f"  -> 连接成功")

        # 开始接收数据
        ble.start()
        logger.info(f"  -> 开始接收数据 ({duration}s)...")

        # 等待指定时长
        remaining = duration
        while remaining > 0 and not stop_requested:
            await asyncio.sleep(min(1.0, remaining))
            remaining -= 1

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"  -> 错误: {e}")
    finally:
        # 停止并断开
        try:
            ble.stop()
            await ble.destroy()
        except:
            pass

        result["duration"] = (datetime.now() - start_time).total_seconds()
        status = "成功" if not result["error"] else "失败"
        logger.info(f"  -> 完成 ({status}): 数据={result['data_count']}条, 指标={result['metrics_count']}条")

    return result


async def main(address: str | None, device_type: str, timeout: float, duration: float):
    """主测试流程.

    流程: 扫描设备 -> 遍历测试每个设备(连接->数据->断开) -> 汇总报告
    """
    global stop_requested

    ble = BLEWrapper(device_type=device_type)
    devices_to_test = []
    results = []

    try:
        # ========== 步骤1: 扫描设备 ==========
        logger.info("=" * 60)
        logger.info("[步骤1] 扫描设备...")
        logger.info("=" * 60)

        if address:
            devices_to_test = [{"name": "指定设备", "address": address, "rssi": None}]
        else:
            devices = await ble.search(timeout=timeout)
            # 按设备类型前缀过滤
            devices_to_test = [
                d for d in devices
                if d["name"] and d["name"].startswith(device_type)
            ]

            if not devices_to_test:
                logger.warning(f"未找到 {device_type} 设备")
                logger.info("可用设备列表:")
                for d in devices:
                    logger.info(f"  {d['name'] or '(无名称)'} @ {d['address']}")
                return

        logger.info(f"找到 {len(devices_to_test)} 个设备待测试")

        # ========== 步骤2: 遍历测试每个设备 ==========
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"[步骤2] 开始测试 (每设备 {duration}s)...")
        logger.info("=" * 60)

        for i, device in enumerate(devices_to_test, 1):
            if stop_requested:
                logger.info("已停止")
                break

            logger.info("")
            logger.info(f"-- 设备 {i}/{len(devices_to_test)}: {device['address']} --")
            if device.get("rssi"):
                logger.info(f"   信号: {device['rssi']} dBm")

            result = await test_device(device["address"], device_type, duration)
            results.append(result)

            # 设备间休息 2 秒
            if i < len(devices_to_test) and not stop_requested:
                logger.info(f"   休息 2s 后测试下一个...")
                await asyncio.sleep(2)

        # ========== 步骤3: 汇总报告 ==========
        logger.info("")
        logger.info("=" * 60)
        logger.info("[测试汇总报告]")
        logger.info("=" * 60)

        success_count = sum(1 for r in results if r["connected"] and not r["error"])
        total_data = sum(r["data_count"] for r in results)
        total_metrics = sum(r["metrics_count"] for r in results)

        for i, r in enumerate(results, 1):
            status = "✓ 成功" if r["connected"] and not r["error"] else "✗ 失败"
            logger.info(f"  [{i}] {r['address']}: {status}")
            if r["error"]:
                logger.info(f"      错误: {r['error']}")
            else:
                logger.info(f"      数据:{r['data_count']}条 指标:{r['metrics_count']}条 耗时:{r['duration']:.1f}s")

        logger.info("")
        logger.info(f"总计: {len(results)} 设备, {success_count} 成功, {total_data} 条数据, {total_metrics} 条指标")
        logger.info(f"日志文件: {LOG_FILE}")

    except Exception as e:
        logger.error(f"测试异常: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BLE 真实硬件自动化测试")
    parser.add_argument("--address", "-a", type=str, help="指定设备地址 (不扫描，直接连接)")
    parser.add_argument("--type", "-t", type=str, default="Dbay-EEG2", help="设备类型")
    parser.add_argument("--timeout", "-o", type=float, default=15.0, help="扫描超时(秒)")
    parser.add_argument("--duration", "-d", type=float, default=30.0, help="每设备数据接收时长(秒)")

    args = parser.parse_args()

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print(" BLE 真实硬件自动化测试")
    print(" 流程: 扫描 -> 连接 -> 数据(30s) -> 断开 -> 下一个")
    print("=" * 60)
    print(f"日志文件: {LOG_FILE}")
    print()

    asyncio.run(main(args.address, args.type, args.timeout, args.duration))

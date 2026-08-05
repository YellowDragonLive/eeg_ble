"""BLE 模块异常定义。"""

from __future__ import annotations


# =============================================================================
# 异常继承树
#
#   BLEError (基类)
#   ├── BLEConnectionError (连接相关)
#   │   ├── BLEConnectionTimeoutError
#   │   └── BLEConnectionRefusedError
#   ├── BLEServiceNotFoundError
#   ├── BLECharacteristicNotFoundError
#   └── BLEScanError
# =============================================================================

class BLEError(Exception):
    """BLE 模块基异常。"""
    pass


class BLEConnectionError(BLEError):
    """连接失败。"""
    pass


class BLEConnectionTimeoutError(BLEConnectionError):
    """连接超时。"""
    pass


class BLEConnectionRefusedError(BLEConnectionError):
    """连接被拒绝。"""
    pass


class BLEServiceNotFoundError(BLEError):
    """GATT 服务未找到。"""
    pass


class BLECharacteristicNotFoundError(BLEError):
    """GATT 特征未找到。"""
    pass


class BLEScanError(BLEError):
    """扫描失败。"""
    pass


class BLEOperationError(BLEError):
    """BLE 操作失败。"""
    pass

"""BLE 常量定义。"""

# =============================================================================
# Nordic UART Service UUIDs
# =============================================================================

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
CHARACTERISTIC_UUID_CMD = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
CHARACTERISTIC_UUID_DATA_EEG = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
CHARACTERISTIC_UUID_DATA_RSP_INFO = "6e400004-b5a3-f393-e0a9-e50e24dcca9e"
CHARACTERISTIC_UUID_DATA_ALG = "6e400005-b5a3-f393-e0a9-e50e24dcca9e"

# =============================================================================
# 设备类型
# =============================================================================

DEVICE_TYPE_EEG2 = "Dbay-EEG2"
DEVICE_TYPE_EEGM = "Dbay-EEGM"
DEVICE_TYPE_EEGS = "Dbay-EEGS"

# =============================================================================
# 协议模式
# =============================================================================

PROTOCOL_MODE_LEGACY = "legacy"
PROTOCOL_MODE_NEUROFEEDBACK = "neurofeedback"

# =============================================================================
# 启动命令
# =============================================================================

AUTO_START_COMMANDS = {
    DEVICE_TYPE_EEG2: bytes([0x05, 0x03]),
    DEVICE_TYPE_EEGM: bytes([0x05, 0x03]),
    DEVICE_TYPE_EEGS: bytes([0x04, 0x01, 0x01, 0x00, 0x01]),
}

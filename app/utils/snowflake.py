"""Snowflake ID 生成器。

生成 64 位纯数字 ID（19 位十进制）。
结构：时间戳(41位) + 机器ID(10位) + 序列号(12位)

特点：
- 时间排序：ID 随时间递增
- 分布式友好：不同机器生成不同 ID
- 高性能：单机每毫秒可生成 4096 个 ID
"""

import threading
import time

# Snowflake ID 组成部分位数
TIMESTAMP_BITS = 41  # 时间戳位数（可用约 69 年）
MACHINE_ID_BITS = 10  # 机器 ID 位数（支持 1024 台机器）
SEQUENCE_BITS = 12  # 序列号位数（每毫秒 4096 个 ID）

# 最大值
MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1  # 1023
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1  # 4095

# 自定义起始时间戳（2024-01-01 00:00:00 UTC）
CUSTOM_EPOCH = 1704067200000


class SnowflakeGenerator:
    """Snowflake ID 生成器。

    Usage:
        generator = SnowflakeGenerator(machine_id=1)
        id = generator.generate()
        # 返回：1234567890123456789（19 位纯数字）
    """

    def __init__(self, machine_id: int = 1):
        """初始化生成器。

        Args:
            machine_id: 机器 ID（0-1023），不同机器使用不同值

        Raises:
            ValueError: 机器 ID 超出范围
        """
        if machine_id < 0 or machine_id > MAX_MACHINE_ID:
            raise ValueError(f"machine_id 必须在 0-{MAX_MACHINE_ID} 范围内")

        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = 0
        self._lock = threading.Lock()

    def _current_timestamp(self) -> int:
        """获取当前时间戳（毫秒）。"""
        return int(time.time() * 1000)

    def generate(self) -> int:
        """生成下一个 Snowflake ID。

        Returns:
            64 位整数 ID（19 位十进制数字）

        Note:
            - 线程安全
            - 如果时钟回拨，等待时钟恢复
        """
        with self._lock:
            current_timestamp = self._current_timestamp()

            # 时钟回拨处理：等待时钟恢复
            if current_timestamp < self.last_timestamp:
                wait_time = self.last_timestamp - current_timestamp
                time.sleep(wait_time / 1000)
                current_timestamp = self._current_timestamp()

            # 同一毫秒内，序列号递增
            if current_timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & MAX_SEQUENCE
                # 序列号溢出，等待下一毫秒
                if self.sequence == 0:
                    while current_timestamp <= self.last_timestamp:
                        current_timestamp = self._current_timestamp()
            else:
                # 新毫秒，序列号重置
                self.sequence = 0

            self.last_timestamp = current_timestamp

            # 组装 ID
            timestamp_part = (current_timestamp - CUSTOM_EPOCH) << (MACHINE_ID_BITS + SEQUENCE_BITS)
            machine_part = self.machine_id << SEQUENCE_BITS
            sequence_part = self.sequence

            return timestamp_part | machine_part | sequence_part


# 全局生成器实例（默认 machine_id=1）
_generator: SnowflakeGenerator | None = None


def init_snowflake(machine_id: int = 1) -> None:
    """初始化全局 Snowflake 生成器。

    Args:
        machine_id: 机器 ID（0-1023）
    """
    global _generator
    _generator = SnowflakeGenerator(machine_id)


def snowflake_id() -> int:
    """生成下一个 Snowflake ID（使用全局生成器）。

    Returns:
        64 位整数 ID（19 位十进制数字）

    Raises:
        RuntimeError: 未初始化生成器
    """
    if _generator is None:
        init_snowflake()
    return _generator.generate()


# 模块加载时自动初始化
init_snowflake()
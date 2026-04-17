"""分布式短 ID 生成器 - 高容量版本。

结构：时间戳(28位秒) + 机器ID(2位) + 序列号(10位)
最多4台机器，8年有效期，每秒1024个ID。

示例：
    ID: 12345678901 (11位)
    ID: 234567890123 (12位)
"""
import threading
import time

# 40位结构 - 高容量版本
TIMESTAMP_BITS = 28   # 秒级，约8.5年（覆盖2026-2034）
MACHINE_ID_BITS = 2   # 支持4台机器
SEQUENCE_BITS = 10    # 每秒1024个ID

# 最大值
MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1  # 3
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1      # 1023

# 2026-01-01 00:00 UTC 的秒数
CUSTOM_EPOCH = 1735689600


class ShortIdGenerator:
    """分布式短 ID 生成器（40位，高容量）。"""

    def __init__(self, machine_id: int = 0):
        if machine_id < 0 or machine_id > MAX_MACHINE_ID:
            raise ValueError(f"machine_id 必须在 0-{MAX_MACHINE_ID} 范围内")

        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = 0
        self._lock = threading.Lock()

    def generate(self) -> int:
        """生成下一个短 ID（11-12位数字）。"""
        with self._lock:
            current_timestamp = int(time.time()) - CUSTOM_EPOCH

            # 时钟回拨
            if current_timestamp < self.last_timestamp:
                current_timestamp = self.last_timestamp

            # 同一秒内序列号递增
            if current_timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & MAX_SEQUENCE
                if self.sequence == 0:
                    # 序列号溢出，等待下一秒
                    while int(time.time()) - CUSTOM_EPOCH <= self.last_timestamp:
                        time.sleep(0.001)
                    current_timestamp = int(time.time()) - CUSTOM_EPOCH
            else:
                self.sequence = 0

            self.last_timestamp = current_timestamp

            # 组装：时间戳 << 12 | 机器ID << 10 | 序列号
            return (current_timestamp << (MACHINE_ID_BITS + SEQUENCE_BITS)) \
                   | (self.machine_id << SEQUENCE_BITS) \
                   | self.sequence


_generator: ShortIdGenerator | None = None


def init_short_id(machine_id: int = 0) -> None:
    """初始化生成器，指定机器ID（0-3）。"""
    global _generator
    _generator = ShortIdGenerator(machine_id)


def short_id() -> int:
    """生成短 ID（11-12位数字，每秒1024个容量）。"""
    global _generator
    if _generator is None:
        init_short_id()
    return _generator.generate()


# 向后兼容别名
snowflake_id = short_id


# 模块加载时自动初始化
init_short_id()
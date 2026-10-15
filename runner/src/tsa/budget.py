"""Wall-clock budget with a reserve kept back for reporting and cleanup."""

import time
from dataclasses import dataclass, field


@dataclass
class Budget:
    total_s: float
    reserve_s: float = 30.0
    start: float = field(default_factory=time.monotonic)

    @property
    def deadline(self) -> float:
        return self.start + max(self.total_s - self.reserve_s, 0.0)

    def remaining(self) -> float:
        return max(self.deadline - time.monotonic(), 0.0)

    def exhausted(self) -> bool:
        return self.remaining() <= 0.0

    def describe(self) -> str:
        return f"{self.total_s / 60:.0f} min total, {self.reserve_s:.0f} s reserved for reporting"

from dataclasses import dataclass
from enum import Enum

class LoadLevel(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    ABOVE_AVERAGE = "ABOVE_AVERAGE"
    HIGH = "HIGH"

@dataclass(frozen=True)
class LoadMarker:
    queue_count: int
    level: LoadLevel
    label: str

def percentile(values: list[int], p: float) -> float:
    values = sorted(values)
    if not values: return 0.0
    if len(values) == 1: return float(values[0])
    index = (len(values) - 1) * p
    lo = int(index); hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (index - lo)

def marker_for(queue_count: int, all_counts: list[int]) -> LoadMarker:
    p5, p25, p50, p75 = [percentile(all_counts, p) for p in (0.05, .25, .5, .75)]
    if queue_count < p5: level = LoadLevel.VERY_LOW
    elif queue_count < p25: level = LoadLevel.LOW
    elif queue_count < p50: level = LoadLevel.MEDIUM
    elif queue_count < p75: level = LoadLevel.ABOVE_AVERAGE
    else: level = LoadLevel.HIGH
    return LoadMarker(queue_count, level, str(queue_count) if queue_count < 1000 else "> 1 тыс.")

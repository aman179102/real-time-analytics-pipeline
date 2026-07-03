from __future__ import annotations

import hashlib
import random
from typing import Optional

from src.config import config
from src.domain.models import AnalyticsEvent
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class Sampler:
    def __init__(self) -> None:
        self._default_rate = config.sampling.default_sample_rate
        self._high_volume_threshold = config.sampling.high_volume_threshold
        self._high_volume_rate = config.sampling.high_volume_sample_rate
        self._current_volume: dict[str, int] = {}
        self._reservoir_samples: dict[str, list[AnalyticsEvent]] = {}

    def should_sample(self, event: AnalyticsEvent) -> bool:
        rate = self._get_sample_rate(event)
        if rate >= 1.0:
            return True
        if rate <= 0.0:
            self._add_to_reservoir(event)
            return False

        deterministic_key = f"{event.event_type.value}:{event.source}:{event.user_id or 'anon'}"
        hash_val = hashlib.md5(deterministic_key.encode()).hexdigest()
        hash_int = int(hash_val[:8], 16)
        normalized = (hash_int % 10000) / 10000.0

        decision = normalized < rate
        if not decision:
            self._add_to_reservoir(event)

        return decision

    def _get_sample_rate(self, event: AnalyticsEvent) -> float:
        source_key = f"{event.event_type.value}:{event.source}"
        volume = self._current_volume.get(source_key, 0)

        if volume > self._high_volume_threshold:
            return self._high_volume_rate

        return self._default_rate

    def record_volume(self, event_type: str, source: str, count: int = 1) -> None:
        key = f"{event_type}:{source}"
        self._current_volume[key] = self._current_volume.get(key, 0) + count

    def _add_to_reservoir(
        self, event: AnalyticsEvent
    ) -> None:
        key = f"{event.event_type.value}:{event.source}"
        if key not in self._reservoir_samples:
            self._reservoir_samples[key] = []
        reservoir = self._reservoir_samples[key]
        if len(reservoir) < 100:
            reservoir.append(event)
        else:
            idx = random.randint(0, len(reservoir) - 1)
            reservoir[idx] = event

    def get_reservoir_samples(
        self, event_type: str, source: str
    ) -> list[AnalyticsEvent]:
        key = f"{event_type}:{source}"
        return self._reservoir_samples.get(key, [])

    def clear_reservoir(self, event_type: str, source: str) -> None:
        key = f"{event_type}:{source}"
        self._reservoir_samples.pop(key, None)

    def reset_volume_counts(self) -> None:
        self._current_volume.clear()

    def get_sampling_stats(self) -> dict:
        return {
            "default_sample_rate": self._default_rate,
            "high_volume_threshold": self._high_volume_threshold,
            "high_volume_sample_rate": self._high_volume_rate,
            "current_volumes": dict(self._current_volume),
            "reservoir_sizes": {
                k: len(v) for k, v in self._reservoir_samples.items()
            },
        }

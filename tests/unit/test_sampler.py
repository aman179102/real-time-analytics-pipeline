from __future__ import annotations

from unittest.mock import patch

from src.domain.models import AnalyticsEvent, EventType


class TestSampler:
    def test_should_sample_default_rate_one(self, sampler, page_view_event: AnalyticsEvent):
        assert sampler._default_rate == 1.0
        assert sampler.should_sample(page_view_event) is True

    def test_should_sample_zero_rate(self, sampler, page_view_event: AnalyticsEvent):
        sampler._default_rate = 0.0
        assert sampler.should_sample(page_view_event) is False

    def test_should_sample_rate_point_five(self, sampler, page_view_event: AnalyticsEvent):
        sampler._default_rate = 0.5
        results = [sampler.should_sample(page_view_event) for _ in range(100)]
        sampled = sum(results)
        assert sampled <= 100

    def test_deterministic_same_event(self, sampler):
        sampler._default_rate = 0.5
        event_a = AnalyticsEvent(event_type=EventType.CLICK, source="web", payload={}, user_id="u1")
        event_b = AnalyticsEvent(event_type=EventType.CLICK, source="web", payload={}, user_id="u1")
        assert sampler.should_sample(event_a) == sampler.should_sample(event_b)

    def test_deterministic_different_users(self, sampler):
        sampler._default_rate = 0.5
        event_a = AnalyticsEvent(event_type=EventType.CLICK, source="web", payload={}, user_id="u1")
        event_b = AnalyticsEvent(event_type=EventType.CLICK, source="web", payload={}, user_id="u2")
        results = {sampler.should_sample(event_a), sampler.should_sample(event_b)}
        assert len(results) >= 1

    def test_high_volume_triggers_lower_rate(self, sampler, page_view_event: AnalyticsEvent):
        sampler._high_volume_threshold = 5
        sampler._high_volume_rate = 0.0
        sampler.record_volume("page_view", "web-app", 10)
        assert sampler.should_sample(page_view_event) is False

    def test_high_volume_rate_applied(self, sampler, page_view_event: AnalyticsEvent):
        sampler._high_volume_threshold = 5
        sampler._high_volume_rate = 1.0
        sampler.record_volume("page_view", "web-app", 10)
        assert sampler.should_sample(page_view_event) is True

    def test_volume_tracking(self, sampler):
        sampler.record_volume("click", "web", 5)
        sampler.record_volume("click", "web", 3)
        key = "click:web"
        assert sampler._current_volume[key] == 8

    def test_reservoir_adds_sampled_out_events(self, sampler):
        sampler._default_rate = 0.99
        sampler._high_volume_rate = 0.0
        sampler._high_volume_threshold = 0
        sampler.record_volume("click", "web", 1)
        event = AnalyticsEvent(event_type=EventType.CLICK, source="web", payload={})
        result = sampler.should_sample(event)
        reservoir = sampler.get_reservoir_samples("click", "web")
        if not result:
            assert len(reservoir) == 1
        else:
            assert len(reservoir) == 0

    def test_reservoir_replaces_randomly(self, sampler):
        sampler._default_rate = 0.5
        events = []
        for i in range(200):
            e = AnalyticsEvent(
                event_id=f"e{i}",
                event_type=EventType.CLICK,
                source="web",
                payload={"i": i},
            )
            events.append(e)
            sampler.should_sample(e)
        reservoir = sampler.get_reservoir_samples("click", "web")
        assert len(reservoir) <= 100

    def test_clear_reservoir(self, sampler):
        sampler._default_rate = 0.99
        sampler._high_volume_threshold = 0
        sampler._high_volume_rate = 0.0
        sampler.record_volume("click", "web", 1)
        event = AnalyticsEvent(event_type=EventType.CLICK, source="web", payload={})
        sampler.should_sample(event)
        sampler.clear_reservoir("click", "web")
        assert sampler.get_reservoir_samples("click", "web") == []

    def test_reset_volume_counts(self, sampler):
        sampler.record_volume("page_view", "web", 100)
        sampler.reset_volume_counts()
        assert sampler._current_volume == {}

    def test_get_sampling_stats(self, sampler):
        sampler.record_volume("click", "web", 50)
        stats = sampler.get_sampling_stats()
        assert stats["default_sample_rate"] == 1.0
        assert stats["high_volume_threshold"] == 10000
        assert stats["high_volume_sample_rate"] == 0.1
        assert "current_volumes" in stats
        assert "reservoir_sizes" in stats

    def test_get_sample_rate_normal(self, sampler, page_view_event: AnalyticsEvent):
        rate = sampler._get_sample_rate(page_view_event)
        assert rate == sampler._default_rate

    def test_get_sample_rate_high_volume(self, sampler, page_view_event: AnalyticsEvent):
        sampler._high_volume_threshold = 5
        sampler.record_volume("page_view", "web-app", 10)
        rate = sampler._get_sample_rate(page_view_event)
        assert rate == sampler._high_volume_rate

    def test_same_event_consistent_result(self, sampler):
        sampler._default_rate = 0.3
        event = AnalyticsEvent(event_type=EventType.PURCHASE, source="web", payload={"amt": 10}, user_id="u42")
        results = [sampler.should_sample(event) for _ in range(10)]
        assert all(r == results[0] for r in results)

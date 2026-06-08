from __future__ import annotations

from typing import Optional

from src.config import config
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class TracerProvider:
    def __init__(self) -> None:
        self._tracer: Optional[object] = None
        self._enabled = config.tracing.enabled

    async def initialize(self) -> None:
        if not self._enabled:
            logger.info("Tracing disabled")
            return
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider as SdkProvider
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor,
            )

            resource = Resource.create({
                "service.name": config.tracing.service_name,
                "service.version": config.version,
                "deployment.environment": config.environment.value,
            })

            provider = SdkProvider(resource=resource)
            exporter = OTLPSpanExporter(
                endpoint=config.tracing.exporter_endpoint,
            )
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)

            self._tracer = trace.get_tracer(
                config.tracing.service_name,
                config.version,
            )
            logger.info("Tracing initialized with OTLP exporter")

        except ImportError:
            logger.warning(
                "OpenTelemetry not installed, tracing disabled"
            )
            self._enabled = False

    async def shutdown(self) -> None:
        if self._enabled:
            try:
                from opentelemetry import trace
                provider = trace.get_tracer_provider()
                if hasattr(provider, "shutdown"):
                    await provider.shutdown()
                    logger.info("Tracer shut down")
            except Exception as e:
                logger.error("Error shutting down tracer: %s", str(e))

    def start_span(
        self,
        name: str,
        attributes: Optional[dict[str, str]] = None,
    ) -> Optional[object]:
        if not self._enabled or not self._tracer:
            return None
        span = self._tracer.start_span(name)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        return span


tracer = TracerProvider()


async def get_tracer() -> TracerProvider:
    return tracer

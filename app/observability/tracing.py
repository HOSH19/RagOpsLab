from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from uuid import uuid4

from app.config import get_settings

_langfuse = None
_init_attempted = False


def get_langfuse():
    global _langfuse, _init_attempted
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    if _init_attempted:
        return _langfuse
    _init_attempted = True
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        _langfuse = None
    return _langfuse


class _NullSpan:
    def end(self, *args, **kwargs):
        return None


class TraceHandle:
    """Langfuse v2-compatible wrapper; no-ops when Langfuse is disabled."""

    def __init__(self, name: str, input_data: Any = None, metadata: dict | None = None):
        self.name = name
        self.request_id = str(uuid4())
        self._trace = None
        self._spans: dict[str, Any] = {}
        lf = get_langfuse()
        if lf is not None:
            try:
                self._trace = lf.trace(
                    name=name,
                    input=input_data,
                    metadata={"request_id": self.request_id, **(metadata or {})},
                )
            except Exception:
                self._trace = None

    def span(self, name: str, input_data: Any = None, metadata: dict | None = None, as_type: str = "span"):
        del as_type  # v2 spans are untyped
        if self._trace is None:
            return _NullSpan()
        try:
            span = self._trace.span(name=name, input=input_data, metadata=metadata or {})
            self._spans[name] = span
            return span
        except Exception:
            return _NullSpan()

    def end_span(self, name: str, output: Any = None, level: str = "DEFAULT") -> None:
        span = self._spans.pop(name, None)
        if span is None:
            return
        try:
            span.end(output=output, level=level)
        except Exception:
            pass

    def generation(
        self,
        name: str,
        model: str,
        input_data: Any,
        output: Any,
        usage: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        if self._trace is None:
            return
        try:
            self._trace.generation(
                name=name,
                model=model,
                input=input_data,
                output=output,
                usage=usage,
                metadata=metadata or {},
            )
        except Exception:
            pass

    def update(self, output: Any = None, metadata: dict | None = None) -> None:
        if self._trace is None:
            return
        try:
            kwargs: dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = output
            if metadata:
                kwargs["metadata"] = metadata
            if kwargs:
                self._trace.update(**kwargs)
        except Exception:
            pass

    def score(self, name: str, value: float, comment: str | None = None) -> None:
        if self._trace is None:
            return
        try:
            self._trace.score(name=name, value=value, comment=comment)
        except Exception:
            pass

    def end(self) -> None:
        return None

    def flush(self) -> None:
        lf = get_langfuse()
        if lf is not None:
            try:
                lf.flush()
            except Exception:
                pass


@contextmanager
def start_trace(name: str, input_data: Any = None, metadata: dict | None = None) -> Iterator[TraceHandle]:
    handle = TraceHandle(name=name, input_data=input_data, metadata=metadata)
    try:
        yield handle
    finally:
        handle.end()
        handle.flush()

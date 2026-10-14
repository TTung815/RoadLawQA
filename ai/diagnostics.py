"""Stage diagnostics without exception messages, HTTP payloads or credentials."""

from contextvars import ContextVar
from functools import wraps

TRACE: ContextVar[list | None] = ContextVar("pipeline_trace", default=None)


class PipelineError(RuntimeError):
    def __init__(self, stage: str, error_type: str):
        self.stage, self.error_type = stage, error_type
        super().__init__(f"{stage}: {error_type}")


def record(stage: str, **details):
    trace = TRACE.get()
    if trace is not None:
        trace.append({"stage": stage, **details})


def traced(stage: str):
    def decorate(function):
        @wraps(function)
        async def call(*args, **kwargs):
            record(stage, event="started")
            try:
                result = await function(*args, **kwargs)
            except PipelineError:
                raise
            except Exception as exc:
                origin = getattr(exc, "pipeline_stage", stage)
                record(origin, event="failed", error_type=type(exc).__name__)
                if stage == "answer":
                    raise PipelineError(origin, type(exc).__name__) from exc
                exc.pipeline_stage = origin
                raise
            record(stage, event="completed")
            return result
        return call
    return decorate

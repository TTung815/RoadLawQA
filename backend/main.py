# -*- coding: utf-8 -*-
"""
FastAPI Application Entrypoint for VietLaw-Agent V2
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.health import router as health_router
from backend.api.v1.retrieval import router as retrieval_router
from backend.api.v1.answer import router as answer_router
from backend.api.v1.conversations import router as conversations_router
import asyncio
from contextlib import asynccontextmanager, suppress

from configs.settings import AppSettings, LLMSettings
from backend.dependencies.retrieval import get_current_retriever
from ai.diagnostics import PipelineError
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app):
    task = None
    if LLMSettings().warmup_on_startup:
        from backend.services.warmup import warm_up
        # Background only: the server accepts requests (and /health) immediately;
        # a question asked meanwhile waits for the same locked load.
        task = asyncio.create_task(warm_up(get_current_retriever(), app.state.readiness))
    else:
        app.state.readiness["warmup"] = "disabled"
    yield
    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    if get_current_retriever.cache_info().currsize:
        # close() waits on the same lock as a load still running in its thread.
        get_current_retriever().close()
        get_current_retriever.cache_clear()


def create_app() -> FastAPI:
    settings = AppSettings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="VietLaw-Agent - AI Assistant for Vietnamese Road Traffic Law",
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.state.readiness = {"warmup": "not_started"}

    # Allow CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(retrieval_router, prefix="/api/v1")
    app.include_router(answer_router, prefix="/api/v1")
    app.include_router(conversations_router, prefix="/api/v1")

    @app.exception_handler(PipelineError)
    async def pipeline_error(request, exc):
        return JSONResponse(status_code=502, content={
            "detail": "Một bước xử lý chưa hoàn tất. Vui lòng thử lại.",
            "stage": exc.stage, "error_type": exc.error_type,
        })

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

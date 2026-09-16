# -*- coding: utf-8 -*-
"""
FastAPI Application Entrypoint for VietLaw-Agent V2
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.health import router as health_router
from backend.api.v1.retrieval import router as retrieval_router
from configs.settings import AppSettings


def create_app() -> FastAPI:
    settings = AppSettings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="VietLaw-Agent - AI Assistant for Vietnamese Road Traffic Law",
        debug=settings.debug,
    )

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

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

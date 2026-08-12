from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.jobs import JobManager


def create_app(job_manager: JobManager | None = None) -> FastAPI:
    manager = job_manager or JobManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager.startup()
        yield
        manager.shutdown()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.job_manager = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.frontend_origin.split(",")],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()

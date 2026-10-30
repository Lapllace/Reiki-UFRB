"""Fábrica da aplicação FastAPI."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.routes import auth, health, locations, sessions
from app.api.routes.phase2 import (
    availability_router,
    enrollments_router,
    me_router,
)
from app.api.routes.phase3 import instructor_router as phase3_instructor_router
from app.api.routes.phase4 import router as phase4_router
from app.api.routes.integration import (
    coordination_router as integration_coordination_router,
    instructor_router as integration_instructor_router,
    notifications_router,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Reiki UFRB API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(locations.router)
    app.include_router(sessions.router)
    app.include_router(availability_router)
    app.include_router(enrollments_router)
    app.include_router(me_router)
    app.include_router(phase3_instructor_router)
    app.include_router(phase4_router)
    app.include_router(integration_instructor_router)
    app.include_router(integration_coordination_router)
    app.include_router(notifications_router)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # 422 no formato que o frontend espera (detail + code).
        return JSONResponse(
            status_code=422,
            content={"detail": "Dados inválidos.", "code": "validation_error"},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Nunca expor stack trace.
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor.", "code": "internal_error"},
        )

    return app


app = create_app()

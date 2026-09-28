
from contextlib import asynccontextmanager

from fastapi import FastAPI

from rest.routers import regiter_routes
from infra.database.mongodb_client import test_connection as test_db_connection
from observability.logger import configure_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application.""" 
    configure_logger()
    if not test_db_connection():
        raise RuntimeError("Failed to connect to MongoDB")
    yield


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(title="FIAP POS IA - Tech Challenge - FASE 4", version="1.0.0", lifespan=lifespan)
    api_app = FastAPI()
    regiter_routes(api_app)
    app.mount("/api", api_app)

    return app

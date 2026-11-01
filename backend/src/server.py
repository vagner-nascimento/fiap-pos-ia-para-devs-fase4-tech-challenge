
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.media_paths import MediaStorage
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
    Create and configure the FastAPI application with CORS and media serving.
    """
    app = FastAPI(title="FIAP POS IA - Tech Challenge - FASE 4", version="1.0.0", lifespan=lifespan)

    # Permite CORS para integração transparente com o frontend (porta 8080 ou dev 5173/3000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_app = FastAPI()
    regiter_routes(api_app)
    app.mount("/api", api_app)

    # Rota estática para servir vídeos anotados e evidências geradas para o frontend
    media_storage = MediaStorage.from_env()
    media_storage.media_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_storage.media_root)), name="media")

    return app

from fastapi import APIRouter

from models.rest.health import HealthResponse
from infra.database.mongodb_client import test_connection

router = APIRouter()


@router.get("/health", summary="Health check endpoint", tags=["Health"], response_model=HealthResponse)
def health() -> HealthResponse:
	"""Health check endpoint to verify the service is running."""
	return HealthResponse(database="healthy" if test_connection() else "unhealthy")

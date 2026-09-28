from pydantic import BaseModel, Field

from datetime import datetime


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""
    status: str = Field(default="healthy", description="The health status of the service.")
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M:%S"), description="The timestamp of the health check.")
    database: str = Field(description="The status of the database connection.")

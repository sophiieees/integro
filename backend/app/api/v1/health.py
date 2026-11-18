"""Rutas de comprobación: la API está viva y la base de datos responde."""

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database.connection import read_database_status

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


class DatabaseHealthResponse(BaseModel):
    status: Literal["ok"]
    database: str
    port: int
    server_version: str


class UnavailableResponse(BaseModel):
    status: Literal["unavailable"]


@router.get("/health", response_model=HealthResponse, summary="La API está viva")
def health() -> HealthResponse:
    """Responde sin tocar la base de datos."""
    return HealthResponse(status="ok")


@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    responses={503: {"model": UnavailableResponse}},
    summary="La base de datos responde",
)
def database_health(request: Request):
    """Pide una conexión al grupo y pregunta a la base quién es.

    Si la base no responde contesta 503, sin el motivo ni datos de conexión.
    """
    status = read_database_status(request.app.state.pool)
    if status is None:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return DatabaseHealthResponse(
        status="ok",
        database=status.database,
        port=status.port,
        server_version=status.server_version,
    )

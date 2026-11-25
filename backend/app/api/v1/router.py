"""Reúne las rutas de la versión 1. Cada módulo agrega aquí las suyas."""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.accounts.router import router as accounts_router
from app.modules.accounts.two_factor_router import router as two_factor_router
from app.modules.hosts.router import router as hosts_router

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(accounts_router)
router.include_router(two_factor_router)
router.include_router(hosts_router)

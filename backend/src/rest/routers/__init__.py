"""
Route registration utilities for the FastAPI application.
"""
import importlib
import pkgutil

from fastapi import APIRouter, FastAPI


def regiter_routes(app: FastAPI) -> None:
	"""Discover router modules in this package and include their routers."""
	for module_info in pkgutil.iter_modules(__path__):
		if module_info.ispkg or module_info.name == "__init__":
			continue

		module = importlib.import_module(f"{__name__}.{module_info.name}")
		router = getattr(module, "router", None)
		if isinstance(router, APIRouter):
			app.include_router(router)

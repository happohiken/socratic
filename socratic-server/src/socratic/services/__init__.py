"""Servicios de aplicación.

Funciones/clases que orquestan operaciones de dominio combinando
persistencia, recuperación y reglas de negocio. Son consumidas tanto por
la capa HTTP (`api/`) como por las tools del orquestador.
"""
from socratic.services.navigation import NavigationError, NavigationService

__all__ = ["NavigationError", "NavigationService"]

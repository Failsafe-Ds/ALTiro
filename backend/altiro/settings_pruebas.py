"""Ajustes para pytest (ADR-014): los de ``altiro.settings`` más un recurso ficticio.

``tests.recurso_prueba`` aporta un recurso con dueño y dos rutas de prueba
para verificar la autorización centralizada antes de que existan recursos de
negocio (S2). Nada de esto llega a ``altiro.settings`` ni a ``altiro.urls``
(lo verifica ``tests/test_settings_pruebas.py``).
"""
from altiro.settings import *  # noqa: F401,F403
from altiro.settings import INSTALLED_APPS as _APPS_BASE

# Lista nueva: no se modifica la de altiro.settings.
INSTALLED_APPS = [*_APPS_BASE, "tests.recurso_prueba"]

ROOT_URLCONF = "tests.recurso_prueba.urls"

# El correo de recuperación se escribe en línea para leer el buzón sin esperar
# un hilo (identidad.recuperacion._en_segundo_plano; ADR-027, E-1). Una prueba
# lo activa para verificar el hilo.
ALTIRO_CORREO_EN_SEGUNDO_PLANO = False

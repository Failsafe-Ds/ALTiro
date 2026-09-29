"""Pruebas del QA de cierre del Sprint 2 (docs/testing/cierre-sprint-2.md).

DEF-QA-008: la suite de pruebas usa el directorio de documentos configurado por
el entorno (el volumen real ``documentos`` cuando se corre con
``docker compose exec -T app pytest``) en las pruebas que no piden la fixture
``directorio_documentos``. La prueba
``test_avisos_planificador.py::test_un_error_de_base_de_datos_en_una_tarea_se_registra_sin_datos``
corre ``limpiar_archivos_huerfanos`` con ``AHORA`` = 2026-10-14 sobre ese
directorio y con la base de pruebas, donde ningún documento referencia los
archivos reales: borra todos los archivos cifrados del volumen, y los documentos
de la base principal quedan sin foto (la descarga responde 500).

Esta prueba documenta el defecto (xfail estricto): pasará cuando las pruebas
nunca apunten al directorio real (por ejemplo, con una fixture autouse que
redirija ``ALTIRO_DOCUMENTOS_DIR`` a un directorio temporal).
"""
import os
from pathlib import Path

import pytest
from django.conf import settings


@pytest.mark.xfail(
    strict=True,
    reason="DEF-QA-008: las pruebas usan el directorio real de documentos si no piden la fixture",
)
def test_las_pruebas_nunca_usan_el_directorio_real_de_documentos():
    configurado = os.environ.get("ALTIRO_DOCUMENTOS_DIR")
    if not configurado:
        pytest.skip("Sin ALTIRO_DOCUMENTOS_DIR en el entorno: no hay directorio real que proteger.")
    assert Path(settings.ALTIRO_DOCUMENTOS_DIR).resolve() != Path(configurado).resolve()

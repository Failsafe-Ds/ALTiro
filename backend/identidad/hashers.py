"""Hasher de contraseñas del proyecto (RNF-05, ADR-004).

Argon2id con parámetros medidos en el equipo de referencia: 64 MiB, 3
iteraciones, 1 hilo (135 ms por verificación el 2026-09-28). Con 2 workers
de gunicorn, a lo más 2 verificaciones simultáneas: unos 128 MiB (RNF-04).
"""
from django.contrib.auth.hashers import Argon2PasswordHasher


class Argon2idAlTiro(Argon2PasswordHasher):
    # Se conserva el algoritmo "argon2" de Django: el hash guardado empieza
    # con "argon2$argon2id$" y Django lo recalcula si cambian los parámetros.
    memory_cost = 65536
    time_cost = 3
    parallelism = 1

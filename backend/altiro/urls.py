from django.urls import path

from altiro.salud import salud

urlpatterns = [
    path("api/health/", salud, name="salud"),
]

# Localidades/urls.py

from django.urls import include, path

urlpatterns = [
    # Telas web: /web/<slug>/localidades/estados/, /cidades/, /paises/ ...
    path("", include("localidades.web.urls_web")),

    # API REST: /api/<slug>/localidades/estados/, /cidades/, /paises/ ...
    path("api/", include("localidades.rest.api_urls")),
]

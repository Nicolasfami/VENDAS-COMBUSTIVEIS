"""
Funções de geocodificação (via Nominatim/OpenStreetMap, gratuito) e
otimização simples de rota (vizinho mais próximo).
"""
import time
from math import radians, sin, cos, sqrt, atan2
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

import db

_geolocator = Nominatim(user_agent="prospeccao_postos_combustiveis_app")
_geocode = RateLimiter(_geolocator.geocode, min_delay_seconds=1.1)


def geocode_endereco(endereco, municipio, uf, cep=""):
    """Geocodifica um endereço, usando cache no SQLite para não repetir chamadas."""
    endereco_completo = f"{endereco}, {municipio}, {uf}"
    cached = db.get_geocode(endereco_completo)
    if cached:
        return cached

    tentativas = [
        f"{endereco}, {municipio}, {uf}, Brazil",
        f"{cep}, {municipio}, {uf}, Brazil" if cep else None,
        f"{municipio}, {uf}, Brazil",
    ]
    for query in tentativas:
        if not query:
            continue
        try:
            loc = _geocode(query)
        except Exception:
            loc = None
        if loc:
            db.save_geocode(endereco_completo, loc.latitude, loc.longitude)
            return loc.latitude, loc.longitude
    return None


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def otimizar_rota(pontos, origem=None):
    """
    pontos: lista de dicts com 'lat', 'lon', 'razao_social', 'cnpj'
    origem: (lat, lon) opcional. Se None, usa o primeiro ponto da lista.
    Retorna lista ordenada (algoritmo do vizinho mais próximo - simples e rápido).
    """
    if not pontos:
        return []

    restantes = pontos.copy()

    if origem:
        atual = {"lat": origem[0], "lon": origem[1]}
    else:
        atual = restantes.pop(0)
        ordenados = [atual]
        while restantes:
            prox = min(restantes, key=lambda p: haversine_km(atual["lat"], atual["lon"], p["lat"], p["lon"]))
            ordenados.append(prox)
            restantes.remove(prox)
            atual = prox
        return ordenados

    ordenados = []
    while restantes:
        prox = min(restantes, key=lambda p: haversine_km(atual["lat"], atual["lon"], p["lat"], p["lon"]))
        ordenados.append(prox)
        restantes.remove(prox)
        atual = prox
    return ordenados


def gerar_link_google_maps_rota(pontos_ordenados, origem=None):
    """Gera um link do Google Maps com waypoints na ordem otimizada."""
    coords = []
    if origem:
        coords.append(f"{origem[0]},{origem[1]}")
    coords += [f"{p['lat']},{p['lon']}" for p in pontos_ordenados]

    if len(coords) < 2:
        if coords:
            return f"https://www.google.com/maps/search/?api=1&query={coords[0]}"
        return ""

    destino = coords[-1]
    waypoints = coords[:-1]
    base = "https://www.google.com/maps/dir/?api=1"
    url = f"{base}&destination={destino}"
    if waypoints:
        wp_str = "|".join(waypoints)
        url += f"&waypoints={wp_str}"
    return url

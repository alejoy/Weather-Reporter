import os
import requests
import json
import time
from datetime import datetime
import re
import markdown

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# Coordenadas Neuquén Capital (Para Open-Meteo)
LAT = -38.9516
LON = -68.0591

# --- 1. DATOS (MOTOR HÍBRIDO) ---

def obtener_clima_openmeteo():
    """Obtiene datos precisos y actualizados de Open-Meteo (Respaldo Global)."""
    print("🌍 Consultando Open-Meteo (Datos Satelitales)...", end=" ")
    
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current": "temperature_2m,relative_humidity_2m,is_day,weather_code,wind_speed_10m,wind_gusts_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_sum,precipitation_probability_max",
        "timezone": "America/Argentina/Salta", # Huso horario correcto (-3)
        "forecast_days": 1
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        current = data['current']
        daily = data['daily']
        
        # Mapeo de datos para nuestra estructura
        clima = {
            "temp_actual": current['temperature_2m'],
            "humedad": current['relative_humidity_2m'],
            "viento_vel": current['wind_speed_10m'],
            "viento_rafagas": current['wind_gusts_10m'],
            "es_dia": current['is_day'] == 1,
            "codigo_wmo": current['weather_code'], # Código numérico del clima
            
            # Pronóstico Hoy
            "temp_min": daily['temperature_2m_min'][0],
            "temp_max": daily['temperature_2m_max'][0],
            "lluvia_mm": daily['precipitation_sum'][0],
            "prob_lluvia": daily['precipitation_probability_max'][0],
            "uv_index": daily['uv_index_max'][0],
            "codigo_wmo_dia": daily['weather_code'][0]
        }
        print("✅ Datos frescos recibidos.")
        return clima
    except Exception as e:
        print(f"❌ Error Open-Meteo: {e}")
        return None

def obtener_alertas_smn():
    """Obtiene SOLO las alertas oficiales del SMN Argentina."""
    print("🇦🇷 Consultando Alertas Oficiales SMN...", end=" ")
    alertas_detectadas = []
    
    # Truco: Agregamos timestamp para romper el caché del servidor del SMN si está pegado
    url = f"https://ws.smn.gob.ar/alerts/type/AL?v={int(time.time())}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        todas = res.json()
        
        for alerta in todas:
            # Buscamos si la alerta afecta a nuestra zona
            json_str = json.dumps(alerta, ensure_ascii=False)
            if "Confluencia" in json_str or ("Neuquén" in json_str and "Cordillera" not in json_str):
                alertas_detectadas.append({
                    "titulo": alerta['title'],      # Ej: Alerta por viento
                    "nivel": alerta['severity'],    # Ej: Amarillo
                    "descripcion": alerta['description']
                })
        
        if alertas_detectadas:
            print(f"🚨 {len(alertas_detectadas)} Alerta(s) encontrada(s).")
        else:
            print("✅ Sin alertas vigentes.")
            
    except Exception as e:
        print(f"⚠️ Error SMN Alertas: {e}")
    
    return alertas_detectadas

# --- 2. VISUAL (TRADUCTOR WMO A PLACA) ---

def interpretar_wmo(codigo):
    """Traduce el código numérico WMO a texto y diseño."""
    # Tabla de códigos WMO: https://open-meteo.com/en/docs
    if codigo == 0: return "Despejado", "☀️", "linear-gradient(135deg, #f6d365 0%, #fda085 100%)", "#333"
    if codigo in [1, 2, 3]: return "Nublado", "☁️", "linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%)", "#fff"
    if codigo in [45, 48]: return "Niebla", "🌫️", "linear-gradient(135deg, #757F9A 0%, #D7DDE8 100%)", "#333"
    if codigo in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]: return "Lluvia", "🌧️", "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)", "#fff"
    if codigo in [95, 96, 99]: return "Tormenta", "⛈️", "linear-gradient(135deg, #434343 0%, #000000 100%)", "#fff"
    if codigo in [71, 73, 75, 77, 85, 86]: return "Nieve", "❄️", "linear-gradient(135deg, #83a4d4 0%, #b6fbff 100%)", "#333"

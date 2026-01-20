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

# --- 1. DISEÑO VISUAL (CSS + ICONOS) ---
def generar_placa_html(datos, fecha):
    """Genera una tarjeta HTML/CSS moderna según el clima."""
    
    estado = datos['estado']
    if not estado: return ""
    
    # Lógica de Colores e Iconos
    condicion = estado['cielo'].lower()
    es_noche = datetime.now().hour > 20 or datetime.now().hour < 6
    
    # Defaults
    icono = "⛅"
    fondo = "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)" # Azul cielo
    color_texto = "#fff"
    
    # Personalización según clima
    if "despejado" in condicion or "sol" in condicion:
        if es_noche:
            icono = "🌙"
            fondo = "linear-gradient(135deg, #2c3e50 0%, #3498db 100%)" # Noche azulada
        else:
            icono = "☀️"
            fondo = "linear-gradient(135deg, #f6d365 0%, #fda085 100%)" # Naranja soleado
            color_texto = "#333"
            
    elif "nublado" in condicion or "cubierto" in condicion:
        icono = "☁️"
        fondo = "linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%)" # Gris plomo
        
    elif "lluvia" in condicion or "llovizna" in condicion or "chaparron" in condicion:
        icono = "🌧️"
        fondo = "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)" # Azul lluvia
        
    elif "tormenta" in condicion:
        icono = "⛈️"
        fondo = "linear-gradient(135deg, #434343 0%, #000000 100%)" # Negro tormenta
    
    elif "viento" in condicion:
        icono = "🍃"
        fondo = "linear-gradient(135deg, #D7D2CC 0%, #304352 100%)" # Gris Viento

    # Si hay Alerta, la placa se pone "Picante" (Roja/Naranja)
    alerta_html = ""
    if datos['alertas']:
        fondo = "linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%)" # Rojo Alerta
        icono = "⚠️"
        alerta_msg = datos['alertas'][0]['titulo']
        alerta_html = f"""
        <div style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px; margin-top: 15px; font-weight: bold; font-size: 14px; text-align: center; border: 1px solid rgba(255,255,255,0.4);">
            🚨 {alerta_msg}
        </div>
        """

    # HTML DE LA PLACA
    placa = f"""
    <div style="
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: {fondo};
        color: {color_texto};
        border-radius: 20px;
        padding: 25px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        max-width: 500px;
        margin: 0 auto 30px auto;
        position: relative;
        overflow: hidden;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; opacity: 0.9; font-size: 0.9em; margin-bottom: 15px;">
            <span>📍 Neuquén Capital</span>
            <span>📅 {fecha}</span>
        </div>

        <div style="text-align: center; margin: 20px 0;">
            <div style="font-size: 4em; margin-bottom: 10px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.2));">{icono}</div>
            <div style="font-size: 3.5em; font-weight: 800; line-height: 1;">{estado['temp']}</div>
            <div style="font-size: 1.2em; font-weight: 500; margin-top: 5px; text-transform: capitalize; opacity: 0.95;">{estado['cielo']}</div>
        </div>

        <div style="
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 10px; 
            background: rgba(255,255,255,0.15); 
            border-radius: 12px; 
            padding: 15px;
            backdrop-filter: blur(5px);
        ">
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">💨</span>
                <div style="font-size: 0.8em; opacity: 0.8;">Viento</div>
                <div style="font-weight: bold;">{estado['viento_vel']}</div>
            </div>
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">💧</span>
                <div style="font-size: 0.8em; opacity: 0.8;">Humedad</div>
                <div style="font-weight: bold;">{estado['humedad']}</div>
            </div>
        </div>

        {alerta_html}
    </div>
    """
    return placa

# --- 2. CONEXIÓN AL SMN ---
def obtener_datos_s

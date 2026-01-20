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
    return "Variable", "⛅", "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)", "#fff"

def generar_placa_html(clima, alertas, fecha):
    texto_cielo, icono, fondo, color_texto = interpretar_wmo(clima['codigo_wmo'])
    
    # Ajuste Nocturno
    if not clima['es_dia'] and clima['codigo_wmo'] == 0:
        icono = "🌙"
        fondo = "linear-gradient(135deg, #2c3e50 0%, #3498db 100%)"
        color_texto = "#fff"

    # Si hay alerta, el fondo se pone ROJO automáticamente
    alerta_html = ""
    if alertas:
        fondo = "linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%)"
        color_texto = "#fff"
        icono = "⚠️"
        alerta_msg = alertas[0]['titulo']
        alerta_html = f"""
        <div style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 8px; margin-top: 15px; font-weight: bold; font-size: 14px; text-align: center; border: 1px solid rgba(255,255,255,0.5);">
            🚨 {alerta_msg}
        </div>
        """

    placa = f"""
    <div style="font-family: 'Segoe UI', Roboto, sans-serif; background: {fondo}; color: {color_texto}; border-radius: 20px; padding: 25px; box-shadow: 0 10px 25px rgba(0,0,0,0.2); max-width: 500px; margin: 0 auto 30px auto;">
        <div style="display: flex; justify-content: space-between; font-size: 0.9em; opacity: 0.9;">
            <span>📍 Neuquén Capital</span>
            <span>📅 {fecha}</span>
        </div>
        <div style="text-align: center; margin: 20px 0;">
            <div style="font-size: 4em; text-shadow: 0 4px 10px rgba(0,0,0,0.2);">{icono}</div>
            <div style="font-size: 3.5em; font-weight: 800; line-height: 1;">{clima['temp_actual']}°C</div>
            <div style="font-size: 1.3em; font-weight: 500; margin-top: 5px;">{texto_cielo}</div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; background: rgba(255,255,255,0.2); border-radius: 12px; padding: 12px; backdrop-filter: blur(5px);">
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">💨</span>
                <div style="font-size: 0.75em;">Viento</div>
                <div style="font-weight: bold;">{clima['viento_vel']} km/h</div>
            </div>
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">💧</span>
                <div style="font-size: 0.75em;">Humedad</div>
                <div style="font-weight: bold;">{clima['humedad']}%</div>
            </div>
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">☀️</span>
                <div style="font-size: 0.75em;">UV Max</div>
                <div style="font-weight: bold;">{clima['uv_index']}</div>
            </div>
        </div>
        {alerta_html}
    </div>
    """
    return placa, texto_cielo

# --- 3. REDACCIÓN IA ---
def generar_pronostico_ia(clima, alertas, texto_cielo, fecha):
    
    alertas_str = json.dumps(alertas, ensure_ascii=False) if alertas else "NO HAY ALERTAS. NO INVENTAR."
    
    input_data = {
        "ubicacion": "Neuquén Capital",
        "fecha": fecha,
        "actual": f"{clima['temp_actual']}°C, {texto_cielo}",
        "pronostico_hoy": f"Min {clima['temp_min']}°C / Max {clima['temp_max']}°C",
        "viento": f"Ráfagas de hasta {clima['viento_rafagas']} km/h",
        "uv_index": clima['uv_index'],
        "alertas_oficiales": alertas_str
    }
    input_str = json.dumps(input_data, ensure_ascii=False, indent=2)

    prompt = f"""
    ROL: Periodista Meteorológico.
    
    DATOS REALES (OPEN-METEO + SMN):
    <input_usuario>
    {input_str}
    </input_usuario>

    ESTRUCTURA MARKDOWN:
    1. TÍTULO (#):
       - SI HAY ALERTA: "Alerta en Neuquén: [Tipo de alerta] y ráfagas, las recomendaciones".
       - SI NO: "Clima en Neuquén: [Temp Max] y [Cielo], ¿cómo estará el día?".
    
    2. BAJADA: Cita al SMN y AIC.
    
    3. CUERPO (## Subtítulos):
       - "## Estado actual": Análisis corto.
       - "## Lo que viene": Pronóstico tarde/noche.
       - "## Tips del día": 3 consejos OBLIGATORIOS basados en datos (Ej: Si UV alto -> Protector solar).

    REGLAS:
    - Negritas (**texto**) en datos numéricos.
    - NO inventes alertas si el JSON dice "NO HAY ALERTAS".
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return None

# --- UTILS ---
def obtener_fecha():
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    now = datetime.now()
    return f"{dias[now.weekday()]} {now.day} de {meses[now.month-1]}"

def buscar_imagen_google(query):
    print(f"👉 Buscando imagen: {query}...", end=" ")
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "searchType": "image", "imgSize": "large", "num": 3, "safe": "active"}
        res = requests.get(url, params=params)
        items = res.json().get("items", [])
        for item in items:
            if "facebook" not in item["displayLink"]:
                print("✅")
                return item["link"]
    except: pass
    return None

def subir_imagen(img_url):
    if not img_url: return None
    try:
        res = requests.get(img_url)
        if res.status_code == 200:
            filename = f"clima-{int(time.time())}.jpg"
            url = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
            auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
            headers = {"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"}
            post = requests.post(url, headers=headers, data=res.content, auth=auth)
            if post.status_code == 201: return post.json()['id']
    except: pass
    return None

# --- MAIN ---
def main():
    fecha = obtener_fecha()
    print(f"--- REPORTE HÍBRIDO: {fecha} ---")
    
    # 1. Obtener Datos
    clima = obtener_clima_openmeteo()
    if not clima: return
    
    alertas = obtener_alertas_smn() # SMN Oficial

    # 2. Generar Visuales y Texto
    placa_html, texto_cielo = generar_placa_html(clima, alertas, fecha)
    
    texto_md = generar_pronostico_ia(clima, alertas, texto_cielo, fecha)
    if not texto_md: return

    # Limpieza Markdown
    texto_md = texto_md.replace('```markdown', '').replace('```', '').strip()
    if texto_md.startswith('#'):
        parts = texto_md.split('\n', 1)
        # --- AQUÍ ESTÁ LA CORRECCIÓN CLAVE ---
        # Extraemos el título y le quitamos los asteriscos **
        titulo_raw = parts[0].replace('#', '').strip()
        titulo = titulo_raw.replace('**', '').replace('__', '') 
        
        cuerpo_md = parts[1].strip() if len(parts) > 1 else ""
    else:
        titulo = f"Clima: {fecha}"
        cuerpo_md = texto_md
        
    cuerpo_html = markdown.markdown(cuerpo_md)

    # 3. Imagen Destacada
    img_url = buscar_imagen_google(f"Paisaje Neuquen {texto_cielo}")
    media_id = subir_imagen(img_url)

    # 4. Publicar
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        {placa_html}
        {cuerpo_html}
        <hr>
        <div style="background: #f4f4f4; padding: 10px; font-size: 14px;">
            ℹ️ Datos: Open-Meteo & SMN Argentina.
        </div>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_final, 'status': 'draft', 'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id}
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    if r.status_code == 201: print("✅ Éxito total.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

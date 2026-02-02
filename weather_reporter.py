import os
import requests
import json
import time
from datetime import datetime
import re
import markdown
import sys
import imgkit # LIBRERÍA NUEVA PARA GENERAR IMÁGENES

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

if not WORDPRESS_URL or not WORDPRESS_USER or not WORDPRESS_APP_PASSWORD:
    print("❌ ERROR: Faltan variables de entorno WP.")
    sys.exit(1)
WORDPRESS_URL = WORDPRESS_URL.rstrip('/')
LAT = -38.9516; LON = -68.0591 # Neuquén

# --- 1. DATOS (MOTOR HÍBRIDO) ---
def obtener_clima_openmeteo():
    print("🌍 Open-Meteo...", end=" ")
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LAT, "longitude": LON,
            "current": "temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_sum,precipitation_probability_max",
            "timezone": "America/Argentina/Salta", "forecast_days": 1
        }
        res = requests.get(url, params=params, timeout=10); res.raise_for_status()
        data = res.json(); cur = data['current']; day = data['daily']
        
        print("✅")
        return {
            # Datos actuales (para el texto)
            "temp_actual": cur['temperature_2m'],
            "viento_vel": cur['wind_speed_10m'],
            "viento_rafagas": cur['wind_gusts_10m'],
            "es_dia_actual": cur['is_day'] == 1,
            
            # Datos DEL DÍA (para la placa y pronóstico)
            "temp_max": day['temperature_2m_max'][0],
            "temp_min": day['temperature_2m_min'][0],
            "lluvia_mm": day['precipitation_sum'][0],
            "prob_lluvia": day['precipitation_probability_max'][0],
            "uv_index": day['uv_index_max'][0],
            "codigo_wmo_dia": day['weather_code'][0] # Código del día entero
        }
    except Exception as e: print(f"❌ Error OM: {e}"); return None

def obtener_alertas_smn():
    print("🇦🇷 SMN Alertas...", end=" ")
    alertas = []
    try:
        res = requests.get(f"https://ws.smn.gob.ar/alerts/type/AL?v={int(time.time())}", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        for a in res.json():
            txt = json.dumps(a, ensure_ascii=False)
            if "Confluencia" in txt or ("Neuquén" in txt and "Cordillera" not in txt):
                alertas.append({"titulo": a['title'], "nivel": a['severity']})
        print(f"✅ ({len(alertas)})")
    except: print("⚠️ Error SMN")
    return alertas

# --- 2. VISUAL (PLACA Y GENERACIÓN DE IMAGEN) ---
def interpretar_wmo(codigo, es_dia=True):
    # Mapeo WMO a Iconos y Fondos
    if codigo == 0: return "Despejado", ("☀️" if es_dia else "🌙"), "linear-gradient(135deg, #f6d365 0%, #fda085 100%)", "#333"
    if codigo in [1, 2, 3]: return "Nublado", "☁️", "linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%)", "#fff"
    if codigo in [45, 48]: return "Niebla", "🌫️", "linear-gradient(135deg, #757F9A 0%, #D7DDE8 100%)", "#333"
    if codigo in [51,61,63,80,81]: return "Lluvia", "🌧️", "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)", "#fff"
    if codigo in [95, 96, 99]: return "Tormenta", "⛈️", "linear-gradient(135deg, #434343 0%, #000000 100%)", "#fff"
    return "Variable", "⛅", "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)", "#fff"

def generar_placa_html(clima, alertas, fecha):
    """Genera el HTML de la placa enfocado en el pronóstico diario."""
    # Usamos el código WMO del día, no el actual
    texto_cielo, icono, fondo, color_texto = interpretar_wmo(clima['codigo_wmo_dia'], es_dia=True)

    alerta_html = ""
    if alertas:
        fondo, color_texto, icono = "linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%)", "#fff", "⚠️"
        alerta_html = f"<div style='background: rgba(0,0,0,0.3); padding: 10px; border-radius: 8px; margin-top: 15px; font-weight: bold; text-align: center; border: 1px solid rgba(255,255,255,0.5);'>🚨 {alertas[0]['titulo']}</div>"

    # HTML diseñado para ser convertido a imagen (anchura fija, tipografía del sistema)
    placa = f"""
    <div style="width: 800px; padding: 40px; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: {fondo}; color: {color_texto}; border-radius: 20px; position: relative;">
        <div style="display: flex; justify-content: space-between; font-size: 1.2em; opacity: 0.9; margin-bottom: 20px;">
            <span>📍 Neuquén Capital</span><span>📅 {fecha}</span>
        </div>
        <div style="text-align: center; margin: 30px 0;">
            <div style="font-size: 6em; text-shadow: 0 4px 10px rgba(0,0,0,0.2); line-height: 1;">{icono}</div>
            <div style="font-size: 2em; font-weight: 500; margin: 10px 0;">Pronóstico del día</div>
            <div style="font-size: 5em; font-weight: 800; line-height: 1;">{clima['temp_max']}°C <span style="font-size: 0.5em; opacity: 0.7;">/ {clima['temp_min']}°C</span></div>
            <div style="font-size: 1.8em; font-weight: 500; margin-top: 10px;">{texto_cielo}</div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; background: rgba(255,255,255,0.2); border-radius: 15px; padding: 20px; backdrop-filter: blur(5px);">
            <div style="text-align: center;"><span style="font-size: 2em;">💨</span><div style="font-size: 1em;">Ráfagas</div><div style="font-weight: bold; font-size: 1.3em;">{clima['viento_rafagas']} km/h</div></div>
            <div style="text-align: center;"><span style="font-size: 2em;">☔</span><div style="font-size: 1em;">Prob. Lluvia</div><div style="font-weight: bold; font-size: 1.3em;">{clima['prob_lluvia']}%</div></div>
            <div style="text-align: center;"><span style="font-size: 2em;">☀️</span><div style="font-size: 1em;">Índice UV</div><div style="font-weight: bold; font-size: 1.3em;">{clima['uv_index']}</div></div>
        </div>
        {alerta_html}
    </div>
    """
    return placa, texto_cielo

def generar_imagen_desde_html(html_content):
    """Convierte el HTML de la placa en bytes de una imagen JPG."""
    print("🖼️ Renderizando placa a imagen...", end=" ")
    try:
        # Opciones para wkhtmltoimage
        options = {
            'format': 'jpg',
            'width': 820, # Un poco más que el div para margen
            'disable-smart-width': '',
            'quality': 90,
            'encoding': "UTF-8"
        }
        # Convertimos el HTML string a bytes de imagen
        img_bytes = imgkit.from_string(html_content, False, options=options)
        print("✅")
        return img_bytes
    except Exception as e:
        print(f"❌ Error generando imagen: {e}")
        # Si falla, devolvemos None y el script seguirá sin imagen destacada
        return None

# --- 3. REDACCIÓN IA ---
def generar_pronostico_ia(clima, alertas, texto_cielo, fecha):
    input_data = {
        "ubicacion": "Neuquén Capital", "fecha": fecha,
        "resumen_dia": f"Máxima {clima['temp_max']}°C, Mínima {clima['temp_min']}°C. Cielo {texto_cielo}.",
        "temp_actual": f"{clima['temp_actual']}°C",
        "viento": f"Ráfagas hasta {clima['viento_rafagas']} km/h",
        "uv_index": clima['uv_index'],
        "alertas": [a['titulo'] for a in alertas] if alertas else "Ninguna"
    }
    prompt = f"""
    ROL: Periodista Meteorológico.
    DATOS: {json.dumps(input_data, ensure_ascii=False)}
    ESTRUCTURA MARKDOWN:
    1. TÍTULO (#):
       - SI ALERTA: "⚠️ Alerta en Neuquén: [Fenómeno] y ráfagas fuertes".
       - SI NO: "Clima en Neuquén: se espera una máxima de [Temp Max] y cielo [Cielo]".
    2. BAJADA: Resumen del día citando fuentes oficiales.
    3. CUERPO (##): "## Así estará el día" (Análisis general), "## Temperaturas y Viento" (Detalle), "## Recomendaciones" (3 tips).
    REGLAS: Negritas en datos. Tono útil y directo.
    """
    try:
        print("🤖 IA...", end=" ")
        res = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}", 
                            headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}), timeout=15)
        if res.status_code == 200: print("✅"); return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    print("❌"); return None

# --- UTILS & UPLOAD ---
def obtener_fecha():
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    now = datetime.now()
    return f"{dias[now.weekday()]} {now.day} de {meses[now.month-1]}"

def subir_imagen_wordpress(img_data, es_url=False, filename_prefix="clima"):
    """Sube imagen a WP desde URL o desde bytes crudos."""
    print("⬆️ Subiendo a WP...", end=" ")
    try:
        if es_url:
            res = requests.get(img_data, timeout=10); content = res.content
        else:
            content = img_data # Ya son bytes

        filename = f"{filename_prefix}-{int(time.time())}.jpg"
        res = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/media",
                            headers={"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"},
                            data=content, auth=(WORDPRESS_USER, WORDPRESS_APP_PASSWORD), timeout=15)
        if res.status_code == 201: print(f"✅ ID: {res.json()['id']}"); return res.json()['id']
        else: print(f"❌ {res.status_code} {res.text}")
    except Exception as e: print(f"❌ {e}")
    return None

# --- MAIN ---
def main():
    print(f"--- REPORTE CLIMA (PLACA + IMAGEN) ---")
    fecha = obtener_fecha()
    
    # 1. Datos
    clima = obtener_clima_openmeteo()
    if not clima: sys.exit(1)
    alertas = obtener_alertas_smn()

    # 2. Generar Placa HTML (Enfocada en el día)
    placa_html, texto_cielo = generar_placa_html(clima, alertas, fecha)
    
    # 3. GENERAR IMAGEN DESTACADA DESDE EL HTML
    img_bytes = generar_imagen_desde_html(placa_html)
    media_id = subir_imagen_wordpress(img_bytes, es_url=False, filename_prefix="placa-clima")
    
    # 4. Redacción IA
    texto_md = generar_pronostico_ia(clima, alertas, texto_cielo, fecha)
    if not texto_md: sys.exit(1)

    # Limpieza Título
    texto_md = texto_md.replace('```markdown', '').replace('```', '').strip()
    if texto_md.startswith('#'):
        parts = texto_md.split('\n', 1)
        titulo = parts[0].replace('#', '').replace('**', '').replace('__', '').strip()
        cuerpo_md = parts[1].strip() if len(parts) > 1 else ""
    else:
        titulo = f"Clima: {fecha}"
        cuerpo_md = texto_md
    cuerpo_html = markdown.markdown(cuerpo_md)

    # 5. Armado Final (Placa HTML en cuerpo + Imagen Destacada seteada)
    # Para el cuerpo usamos una versión escalada de la placa para que sea responsive
    placa_responsive = f'<div style="max-width: 100%; overflow: auto;">{placa_html.replace("width: 800px;", "max-width: 600px; margin: auto;")}</div>'
    
    html_final = f"{placa_responsive}<br>{cuerpo_html}<hr><div style='background:#f4f4f4;padding:10px;font-size:14px;'>ℹ️ Datos oficiales: SMN y Open-Meteo.</div>"
    
    print(f"🚀 Publicando: {titulo} ...", end=" ")
    post = {
        'title': titulo, 'content': html_final, 'status': 'publish',
        'author': int(WORDPRESS_AUTHOR_ID), 
        'featured_media': media_id # <-- AQUÍ VA LA PLACA GENERADA COMO IMAGEN
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=(WORDPRESS_USER, WORDPRESS_APP_PASSWORD))
    if r.status_code == 201: print("✅ OK")
    else: print(f"❌ ERROR WP: {r.text}"); sys.exit(1)

if __name__ == "__main__":
    main()

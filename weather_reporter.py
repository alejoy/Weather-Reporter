import os
import requests
import unicodedata
import json
import time

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# Diccionario de Traducción (Para que la placa salga en Español)
TRADUCCIONES = {
    "sunny": "Soleado", "mostly sunny": "Mayormente Soleado", "partly sunny": "Parcialmente Soleado",
    "mostly cloudy": "Mayormente Nublado", "cloudy": "Nublado", "overcast": "Cubierto",
    "rain": "Lluvia", "light rain": "Lluvia Débil", "heavy rain": "Lluvia Intensa",
    "snow": "Nieve", "thunderstorm": "Tormenta", "clear": "Despejado", "fog": "Niebla", "mist": "Neblina"
}

def traducir_estado(texto):
    return TRADUCCIONES.get(texto.lower().strip(), texto).upper()

def normalizar_ciudad(texto):
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def llamar_api_directa(modelo, prompt):
    """Intenta generar texto vía REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }

    try:
        print(f"👉 Probando conexión con: {modelo}...")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        elif res.status_code == 429:
            print(f"⚠️ Cuota llena en {modelo} (429).")
            return None
        else:
            print(f"⚠️ Error {modelo} ({res.status_code})")
            return None
    except Exception as e:
        print(f"⚠️ Error red: {e}")
        return None

def generar_noticia_robusta(prompt):
    # ESTRATEGIA CASCADA:
    # 1. Flash: Prioridad absoluta. Rápido y con mucha cuota gratis.
    # 2. Pro: Solo si Flash falla.
    
    modelos = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto:
            print(f"✅ ¡ÉXITO! Redacción completada con {modelo}")
            return texto
        print("🔄 Cambiando al siguiente modelo de la lista...")
        time.sleep(1) # Pausa de seguridad
    
    return None

def main():
    print(f"--- REPORTE CLIMÁTICO: {TARGET_CITY} ---")
    
    # 1. Obtener Clima
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    estado_es = traducir_estado(curr['summary']) # Traducimos aquí para la placa y el prompt

    # 2. Redacción IA
    prompt = f"""
    Eres Periodista Senior en Neuquén. Escribe una NOTICIA EXTENSA (SEO) sobre el clima.
    
    DATOS REALES:
    - Ciudad: {TARGET_CITY}
    - Estado actual: {estado_es} (Original: {curr['summary']})
    - Temp: {curr['temperature']}°C
    - Mín: {day['temperature_min']}°C | Máx: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS (HTML OBLIGATORIO):
    1. Título H1 Periodístico (Clickbait ético).
    2. CUERPO: 4 PÁRRAFOS COMPLETOS Y LARGOS.
       - Intro: Sensación térmica y estado del cielo.
       - Desarrollo: Pronóstico para la tarde.
       - Viento: Análisis detallado (es clave en Patagonia).
       - Cierre: Recomendaciones.
    3. Usa etiquetas <h3> para subtítulos y <strong> para resaltar datos.
    4. IDIOMA: Español Argentino Neutro.
    """
    
    texto_ia = generar_noticia_robusta(prompt)

    # Fallback (Emergencia)
    if not texto_ia:
        print("❌ Fallaron todos los modelos. Usando texto básico.")
        texto_ia = f"<h3>Reporte {TARGET_CITY}</h3><p>Condiciones actuales: {estado_es}, {curr['temperature']}°C. Se espera una máxima de {day['temperature_max']}°C.</p>"

    # 3. Limpieza y HTML
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split

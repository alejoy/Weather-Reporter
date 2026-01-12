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

# Diccionario para traducir estados (PLACA EN ESPAÑOL)
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
    """Intenta generar texto con un modelo específico vía REST."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }

    try:
        print(f"👉 Probando con modelo: {modelo}...")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        elif res.status_code == 429:
            print(f"⚠️ Cuota excedida en {modelo} (429). Saltando al siguiente...")
            return None
        elif res.status_code == 404:
            print(f"⚠️ Modelo no encontrado {modelo} (404). Saltando...")
            return None
        else:
            print(f"⚠️ Error desconocido ({res.status_code}): {res.text}")
            return None
    except Exception as e:
        print(f"⚠️ Excepción de red: {e}")
        return None

def generar_noticia_inteligente(prompt):
    # LISTA DE PRIORIDAD (CASCADA)
    # 1. Pro (Calidad máxima) -> 2. Flash (Velocidad/Respaldo) -> 3. Pro Viejo
    modelos_a_probar = [
        "gemini-1.5-pro",
        "gemini-1.5-flash", 
        "gemini-2.0-flash-exp", # Experimental si existe
        "gemini-pro"
    ]

    for modelo in modelos_a_probar:
        texto = llamar_api_directa(modelo, prompt)
        if texto:
            print(f"✅ ¡ÉXITO! Nota generada con {modelo}")
            return texto
        time.sleep(1) # Pequeña pausa antes de reintentar
    
    return None

def main():
    print(f"--- INICIANDO REPORTE NEUQUÉN ---")
    
    # 1. Clima
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    estado_es = traducir_estado(curr['summary'])

    # 2. Redacción
    prompt = f"""
    Actúa como Periodista Senior de un diario en Neuquén.
    Escribe una NOTICIA EXTENSA y PROFESIONAL (SEO) sobre el clima.
    
    DATOS:
    - Ciudad: {TARGET_CITY}
    - Estado: {estado_es}
    - Temp Actual: {curr['temperature']}°C
    - Mín: {day['temperature_min']}°C | Máx: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS (HTML OBLIGATORIO):
    1. Título H1 impactante (Clickbait ético).
    2. CUERPO: Escribe 4 PÁRRAFOS LARGOS.
       - Intro: Sensación térmica y estado del cielo.
       - Desarrollo: Pronóstico para la tarde.
       - Viento: Análisis detallado (es clave en Patagonia).
       - Cierre: Recomendaciones.
    3. Usa etiquetas <h3> para subtítulos y <strong> para resaltar datos.
    4. IDIOMA: Español Argentino Neutro.
    """
    
    texto_ia = generar_noticia_inteligente(prompt)

    # Fallback FINAL (Solo si fallan los 4 modelos)
    if not texto_ia:
        texto_ia = f"<h3>Pronóstico {TARGET_CITY}</h3><p>Condiciones actuales: {estado_es}, {curr['temperature']}°C. Máxima de {day['temperature_max']}°C.</p>"

    # 3. Limpieza
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    
    # Extracción de título
    titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
    cuerpo = texto_limpio
    
    if len(lineas) > 0 and ("<h1>" in lineas[0] or "#" in lineas[0] or len(lineas[0]) < 100):
         clean_title = lineas[0].replace('<h1>','').replace('</h1>','').replace('#','').replace('*','').strip()
         if len(clean_title) > 5:
            titulo = clean_title
            cuerpo = "\n".join(lineas[1:])

    # 4. Placa Visual y HTML Final
    color_bg = "#e67e22" if curr['temperature'] > 26 else "#2980b9"
    
    html_post = f"""
    <div style="font-family:'Georgia',serif; font-size:18px; line-height:1.6; color:#333;">
        <div style="background:{color_bg}; color:white; padding:30px; border-radius:10px; text-align:center; margin-bottom:20px;">
            <p style="text-transform:uppercase; font-size:14px; opacity:0.8; margin:0; font-family:sans-serif;">Reporte Oficial</p>
            <h2 style="font-size:80px; margin:5px 0; font-weight:700; font-family:sans-serif;">{curr['temperature']}°C</h2>
            <p style="font-size:24px; font-weight:600; text-transform:uppercase; margin:0; font-family:sans-serif;">{estado_es}</p>
            <div style="margin-top:20px; border-top:1px solid rgba(255,255,255,0.3); padding-top:15px; display:flex; justify-content:center; gap:20px;">
                <span>Min: <b>{day['temperature_min']}°</b></span>
                <span>Viento: <b>{curr['wind']['speed']} km/h</b></span>
                <span>Max: <b>{day['temperature_max']}°</b></span>
            </div>
        </div>
        <div style="background:#fff; padding:10px;">{cuerpo}</div>
    </div>
    """

    # 5. Publicar
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_post, 'status': 'draft'}
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO TOTAL: Nota publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

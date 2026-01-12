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

# Diccionario de Traducción
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
        else:
            print(f"⚠️ Falló {modelo} (Error {res.status_code})")
            return None
    except Exception as e:
        print(f"⚠️ Error de red: {e}")
        return None

def generar_noticia_robusta(prompt):
    # ESTRATEGIA CASCADA:
    # 1. Flash: Rápido, límites altos, muy estable. (Nuestra mejor opción)
    # 2. Pro: Más "inteligente" pero con límites estrictos. (Solo si Flash falla)
    # 3. Legacy: El modelo viejo por si todo lo moderno falla.
    
    modelos = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto:
            print(f"✅ ¡ÉXITO! Nota generada usando: {modelo}")
            return texto
        print("🔄 Cambiando al siguiente modelo...")
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
    estado_es = traducir_estado(curr['summary'])

    # 2. Redacción IA
    prompt = f"""
    Eres Periodista en Neuquén. Escribe una NOTICIA LARGA (SEO) sobre el clima.
    
    DATOS:
    - Ciudad: {TARGET_CITY}
    - Estado: {estado_es}
    - Temp: {curr['temperature']}°C
    - Mín: {day['temperature_min']}°C | Máx: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS (HTML):
    1. Título H1 Periodístico (Clickbait ético).
    2. CUERPO: 4 PÁRRAFOS COMPLETOS Y LARGOS.
       - Intro, Pronóstico tarde, Viento, Cierre.
    3. Usa <h3> y <strong>.
    4. IDIOMA: Español.
    """
    
    texto_ia = generar_noticia_robusta(prompt)

    # Fallback (Emergencia)
    if not texto_ia:
        texto_ia = f"<h3>Reporte {TARGET_CITY}</h3><p>Condiciones actuales: {estado_es}, {curr['temperature']}°C. Se espera una máxima de {day['temperature_max']}°C.</p>"

    # 3. Limpieza y HTML
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    
    titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
    cuerpo = texto_limpio
    
    # Intentar extraer título si la IA lo puso
    if len(lineas) > 0:
        posible_titulo = lineas[0].replace('<h1>','').replace('</h1>','').replace('#','').replace('*','').strip()
        # Si la primera línea parece un título (corto y sin tags raros)
        if len(posible_titulo) > 5 and len(posible_titulo) < 100:
            titulo = posible_titulo
            cuerpo = "\n".join(lineas[1:])

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

    # 4. Publicar
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_post, 'status': 'draft'}
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO TOTAL: Nota publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

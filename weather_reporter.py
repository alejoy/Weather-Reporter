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
    # Usamos v1beta que es compatible con modelos 2.5 y 3
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }

    try:
        print(f"👉 Probando modelo: {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if res.status_code == 200:
            print("✅ ¡CONECTADO!")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        elif res.status_code == 404:
            print("❌ No encontrado (404)")
            return None
        elif res.status_code == 429:
            print("⏳ Cuota llena (429)")
            return None
        else:
            print(f"⚠️ Error {res.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error red: {e}")
        return None

def generar_noticia_especifica(prompt):
    # LISTA ACTUALIZADA CON TUS MODELOS REALES
    # Prioridad: 2.5 Flash -> 3 Flash -> 2.5 Lite
    modelos_disponibles = [
        "gemini-2.5-flash",
        "gemini-3-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash" # Dejamos el viejo por si acaso
    ]

    for modelo in modelos_disponibles:
        texto = llamar_api_directa(modelo, prompt)
        if texto:
            return texto
        # Si falla, pasa al siguiente instantáneamente
    
    return None

def main():
    print(f"--- REPORTE CLIMÁTICO: {TARGET_CITY} ---")
    
    # 1. Clima
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
    DATOS: {TARGET_CITY}, {estado_es}, Temp {curr['temperature']}°C, Viento {curr['wind']['speed']} km/h.
    
    REQUISITOS (HTML):
    1. Título H1 llamativo.
    2. CUERPO: 4 PÁRRAFOS COMPLETOS.
    3. Usa <h3> y <strong>.
    4. IDIOMA: Español Argentino.
    """
    
    texto_ia = generar_noticia_especifica(prompt)

    # Fallback
    if not texto_ia:
        print("❌ TODOS LOS MODELOS FALLARON. Usando plantilla.")
        texto_ia = f"<h3>Reporte {TARGET_CITY}</h3><p>Condiciones: {estado_es}, {curr['temperature']}°C.</p>"

    # 3. Limpieza y HTML
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    
    titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
    cuerpo = texto_limpio
    
    if len(lineas) > 0:
        posible = lineas[0].replace('<h1>','').replace('</h1>','').replace('#','').replace('*','').strip()
        if len(posible) > 5 and len(posible) < 120:
            titulo = posible
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
        print(f"✅ ÉXITO FINAL: Nota publicada con '{titulo}'")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

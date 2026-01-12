import os
import requests
import unicodedata
import json
import time
import re

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# Diccionario de Traducción
TRADUCCIONES = {
    "sunny": "Soleado", "mostly sunny": "Mayormente soleado", "partly sunny": "Parcialmente nublado",
    "mostly cloudy": "Mayormente nublado", "cloudy": "Nublado", "overcast": "Cubierto",
    "rain": "Lluvia", "light rain": "Lluvias aisladas", "heavy rain": "Tormentas fuertes",
    "snow": "Nevadas", "thunderstorm": "Tormenta eléctrica", "clear": "Despejado", "fog": "Niebla", "mist": "Neblina"
}

def traducir_estado(texto):
    return TRADUCCIONES.get(texto.lower().strip(), texto).capitalize()

def normalizar_ciudad(texto):
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1800 # Aumentamos un poco para permitir el párrafo extra
        }
    }

    try:
        print(f"👉 Probando: {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if res.status_code == 200:
            print("✅ ¡CONECTADO!")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        elif res.status_code in [404, 429, 503]:
            print(f"⚠️ Error {res.status_code}, saltando...")
        else:
            print(f"⚠️ Error desconocido {res.status_code}")
        return None
    except Exception as e:
        print(f"⚠️ Error red: {e}")
        return None

def generar_noticia_periodistica(prompt):
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto:
            return texto
        time.sleep(1)
    return None

def limpiar_respuesta_ia(texto):
    """Limpia markdown y extrae título H1."""
    texto = texto.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto, re.IGNORECASE)
    if titulo_match:
        titulo_limpio = titulo_match.group(1).strip()
        cuerpo_limpio = re.sub(r'<h1>.*?</h1>', '', texto, count=1, flags=re.IGNORECASE).strip()
    else:
        titulo_limpio = "Reporte del Clima"
        cuerpo_limpio = texto

    return titulo_limpio, cuerpo_limpio

def main():
    print(f"--- REPORTE ESTILO CLARÍN + RECOMENDACIONES ---")
    
    # 1. Datos
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    estado_es = traducir_estado(curr['summary'])

    # 2. Prompt Actualizado con Lógica de Recomendaciones
    prompt = f"""
    Actúa como un Meteorólogo Redactor de un diario importante (tipo Clarín o La Nación).
    Escribe una nota útil y detallada sobre el clima hoy en {TARGET_CITY}.
    
    DATOS:
    - Estado: {estado_es}
    - Temp Actual: {curr['temperature']}°C
    - Máxima pronosticada: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h
    
    INSTRUCCIONES DE ESTRUCTURA (HTML):
    1. TÍTULO (H1): Informativo. Ejemplo: "Clima en {TARGET_CITY}: pronóstico para hoy".
    2. BAJADA (H2): Resumen de una línea (Ej: "Alerta por vientos" o "Jornada de calor intenso").
    3. CUERPO (5 PÁRRAFOS OBLIGATORIOS):
       - Párrafo 1: Situación actual (mañana).
       - Párrafo 2: Pronóstico de la tarde (temperatura máxima).
       - Párrafo 3: El viento (análisis detallado).
       - Párrafo 4 (NUEVO - RECOMENDACIONES):
         * Si T > 28°C o hay sol: Recomendar hidratación, evitar sol directo al mediodía y usar protector solar.
         * Si Viento > 25km/h: Recomendar precaución al manejar, cuidado con ramas y prohibido hacer fuego.
         * Si T < 10°C: Recomendar abrigo.
       - Párrafo 5: Cierre breve sobre la noche.
    
    4. ESTILO: Profesional, de servicio y preventivo. Usa etiquetas <p>, <h3> y <strong>.
    """
    
    texto_crudo = generar_noticia_periodistica(prompt)

    if not texto_crudo:
        print("❌ Fallo IA.")
        return

    titulo_final, cuerpo_final = limpiar_respuesta_ia(texto_crudo)

    if len(titulo_final) < 5:
        titulo_final = f"Clima en {TARGET_CITY}: el tiempo para hoy"

    # 3. HTML Final
    color_bg = "#e67e22" if curr['temperature'] > 26 else "#3498db"
    
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333; max-width: 800px; margin: auto;">
        
        <div style="background: #f9f9f9; border-left: 6px solid {color_bg}; padding: 20px; margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <div>
                <span style="font-size: 12px; text-transform: uppercase; color: #666; font-weight: bold; letter-spacing: 1px;">Ahora en {TARGET_CITY}</span>
                <div style="font-size: 38px; font-weight: 800; color: #333; margin-top: 5px;">{curr['temperature']}°C</div>
                <div style="font-size: 16px; color: {color_bg}; font-weight: bold;">{estado_es}</div>
            </div>
            <div style="text-align: right; font-size: 14px; color: #555; line-height: 1.8;">
                <div>⬇ Mín: <strong>{day['temperature_min']}°</strong></div>
                <div>⬆ Máx: <strong>{day['temperature_max']}°</strong></div>
                <div>💨 Viento: <strong>{curr['wind']['speed']} km/h</strong></div>
            </div>
        </div>

        <div class="contenido-nota">
            {cuerpo_final}
        </div>

        <div style="margin-top: 30px; font-size: 13px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 15px;">
            Reporte generado automáticamente por Meteosource.
        </div>
    </div>
    """

    # 4. Publicar
    print(f"Publicando: {titulo_final}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo_final, 'content': html_post, 'status': 'draft'}
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

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
            "temperature": 0.4, # Bajamos temperatura para ser más periodísticos y menos "creativos"
            "maxOutputTokens": 1500
        }
    }

    try:
        print(f"👉 Probando: {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if res.status_code == 200:
            print("✅ ¡CONECTADO!")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        elif res.status_code == 404:
            print("❌ No encontrado (404)")
        elif res.status_code == 429:
            print("⏳ Cuota llena (429)")
        elif res.status_code == 503:
            print("💤 Servicio ocupado (503)")
        else:
            print(f"⚠️ Error {res.status_code}")
        return None
    except Exception as e:
        print(f"⚠️ Error red: {e}")
        return None

def generar_noticia_periodistica(prompt):
    # Ponemos el LITE primero porque ya vimos que funciona en tu cuenta
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto:
            return texto
        time.sleep(1)
    return None

def limpiar_respuesta_ia(texto):
    """Elimina etiquetas de código y extrae el título limpio."""
    # 1. Quitar bloques de código markdown y doctypes
    texto = texto.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').replace('<html>', '').replace('<body>', '').replace('</html>', '').replace('</body>', '')
    texto = texto.strip()
    
    # 2. Extraer el Título (H1) usando Regex para mayor precisión
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto, re.IGNORECASE)
    if titulo_match:
        titulo_limpio = titulo_match.group(1).strip()
        # Removemos el H1 del cuerpo para no repetirlo
        cuerpo_limpio = re.sub(r'<h1>.*?</h1>', '', texto, count=1, flags=re.IGNORECASE).strip()
    else:
        # Fallback si la IA no puso H1
        titulo_limpio = "Reporte del Clima"
        cuerpo_limpio = texto

    return titulo_limpio, cuerpo_limpio

def main():
    print(f"--- REPORTE ESTILO CLARÍN: {TARGET_CITY} ---")
    
    # 1. Datos
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    estado_es = traducir_estado(curr['summary'])

    # 2. Prompt Periodístico (Estilo Clarín)
    prompt = f"""
    Actúa como un Meteorólogo Redactor del diario Clarín o La Nación.
    Escribe un reporte detallado sobre el clima hoy en {TARGET_CITY}.
    
    DATOS TÉCNICOS:
    - Ciudad: {TARGET_CITY}
    - Estado actual: {estado_es}
    - Temperatura actual: {curr['temperature']}°C
    - Mínima pronosticada: {day['temperature_min']}°C
    - Máxima pronosticada: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h (Dirección: {curr['wind']['dir']})
    
    INSTRUCCIONES DE REDACCIÓN (ESTRICTO):
    1. ESTRUCTURA HTML LIMPIA: No uses etiquetas <html>, <head> o <body>. Solo usa <h1>, <h2>, <p> y <strong>.
    2. TÍTULO (H1): Debe ser informativo y formal. Ejemplo: "Clima en {TARGET_CITY}: pronóstico del tiempo para hoy".
    3. BAJADA (H2): Un resumen de una frase sobre lo más destacado (viento, calor o lluvias).
    4. CUERPO DE LA NOTA (4 Párrafos Mínimo):
       - Párrafo 1 (Situación Actual): Describe cómo arranca el día, temperatura actual y sensación.
       - Párrafo 2 (Evolución): "Por la tarde...", describe si sube la temperatura y llega a la máxima.
       - Párrafo 3 (Viento y Alertas): Detalla la velocidad del viento, vital para la Patagonia.
       - Párrafo 4 (Cierre/Mañana): Breve proyección de cómo terminará la jornada.
    5. ESTILO: Usa frases como "El Servicio Meteorológico indica...", "Se espera una jornada...", "La humedad se mantendrá...".
    """
    
    texto_crudo = generar_noticia_periodistica(prompt)

    if not texto_crudo:
        print("❌ Fallo total de IA.")
        titulo_final = f"Clima en {TARGET_CITY}: Pronóstico para hoy"
        cuerpo_final = f"<p>Temperatura actual: {curr['temperature']}°C. Se espera una máxima de {day['temperature_max']}°C.</p>"
    else:
        # Usamos la nueva función de limpieza
        titulo_final, cuerpo_final = limpiar_respuesta_ia(texto_crudo)

    # Si el título sigue siendo genérico, lo forzamos
    if len(titulo_final) < 5 or "DOCTYPE" in titulo_final:
        titulo_final = f"Clima en {TARGET_CITY}: el pronóstico del tiempo para hoy"

    # 3. HTML Final (Diseño Sobrio tipo Diario)
    color_bg = "#e67e22" if curr['temperature'] > 26 else "#3498db"
    
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333; max-width: 800px; margin: auto;">
        
        <div style="border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; padding: 15px 0; margin-bottom: 25px; display: flex; align-items: center; justify-content: space-between;">
            <div>
                <span style="font-size: 12px; text-transform: uppercase; color: #666; font-weight: bold;">Datos al instante</span>
                <div style="font-size: 32px; font-weight: bold; color: {color_bg};">{curr['temperature']}°C</div>
                <div style="font-size: 16px; text-transform: capitalize;">{estado_es}</div>
            </div>
            <div style="text-align: right; font-size: 14px; color: #555;">
                <div>⬇ Mín: <strong>{day['temperature_min']}°</strong></div>
                <div>⬆ Máx: <strong>{day['temperature_max']}°</strong></div>
                <div>💨 Viento: <strong>{curr['wind']['speed']} km/h</strong></div>
            </div>
        </div>

        <div class="contenido-nota">
            {cuerpo_final}
        </div>

        <div style="margin-top: 30px; font-size: 13px; color: #888; border-top: 1px solid #eee; padding-top: 10px;">
            <em>Información proporcionada por Meteosource.</em>
        </div>
    </div>
    """

    # 4. Publicar
    print(f"Publicando: {titulo_final}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo_final, 'content': html_post, 'status': 'draft'}
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota publicada correctamente.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

import os
import requests
import unicodedata
import json

# CONFIGURACIÓN
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# DICCIONARIO DE TRADUCCIÓN (Para la placa visual)
TRADUCCIONES = {
    "sunny": "Soleado",
    "mostly sunny": "Mayormente Soleado",
    "partly sunny": "Parcialmente Soleado",
    "mostly cloudy": "Mayormente Nublado",
    "cloudy": "Nublado",
    "overcast": "Cubierto",
    "rain": "Lluvia",
    "light rain": "Lluvia Débil",
    "heavy rain": "Lluvia Intensa",
    "snow": "Nieve",
    "thunderstorm": "Tormenta",
    "clear": "Despejado",
    "fog": "Niebla",
    "mist": "Neblina"
}

def traducir_estado(texto_ingles):
    """Traduce el estado del clima o lo devuelve en mayúsculas si no lo encuentra."""
    texto_lower = texto_ingles.lower().strip()
    return TRADUCCIONES.get(texto_lower, texto_ingles).upper()

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def llamar_api_google(modelo, prompt):
    """Intenta generar texto con un modelo específico vía REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Falló modelo {modelo}: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error conexión {modelo}: {e}")
        return None

def main():
    # 1. Obtener clima
    print(f"Obteniendo datos para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Traducción manual para la imagen
    estado_es = traducir_estado(curr['summary'])

    # 3. Redacción con IA (Estrategia de doble intento)
    print("Iniciando redacción periodística...")
    
    prompt = f"""
    Actúa como Editor Jefe de un diario digital en la Patagonia.
    Escribe una NOTA COMPLETA EN ESPAÑOL sobre el clima en {TARGET_CITY}.

    DATOS:
    - Estado: {estado_es} ({curr['summary']})
    - Temp: {curr['temperature']}°C
    - Mín: {day['temperature_min']}°C | Máx: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS (HTML):
    1. TITULAR: Periodístico, impactante, sin clickbait barato.
    2. CUERPO: Escribe 4 PÁRRAFOS COMPLETOS.
       - Párrafo 1: Introducción y sensación térmica.
       - Párrafo 2: Pronóstico de la tarde (Máxima).
       - Párrafo 3: Análisis del viento (importante en la zona).
       - Párrafo 4: Recomendaciones y cierre.
    3. FORMATO: Usa etiquetas <p> para párrafos, <h3> para subtítulos y <strong> para resaltar números.
    """
    
    # INTENTO 1: Gemini 1.5 Pro (Nombre estándar)
    texto_ia = llamar_api_google("gemini-1.5-pro", prompt)
    
    # INTENTO 2: Si falla, probamos Gemini 1.5 Flash (Más robusto)
    if not texto_ia:
        print("🔄 Cambiando a modelo Flash de respaldo...")
        texto_ia = llamar_api_google("gemini-1.5-flash", prompt)

    # Fallback final (solo si todo falla)
    if not texto_ia:
        texto_ia = f"<p>Reporte de emergencia: Clima en {TARGET_CITY} con {curr['temperature']}°C y condiciones de {estado_es}.</p>"

    # 4. Procesamiento de texto
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    
    # Extracción inteligente de título
    titulo = lineas[0].replace('<h1>', '').replace('</h1>', '').replace('#', '').strip()
    if len(titulo) > 100 or "<p>" in titulo: 
        titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
        cuerpo = texto_limpio
    else:
        cuerpo = "\n".join(lineas[1:])

    # 5. Generación de HTML Final (Placa Traducida + Nota)
    color_bg = "#e67e22" if curr['temperature'] > 26 else "#2980b9"
    
    html_final = f"""
    <div style="font-family: 'Georgia', serif; font-size: 18px; color: #333; line-height: 1.6;">
        <div style="background: {color_bg}; color: white; padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px;">
            <p style="text-transform: uppercase; font-size: 14px; letter-spacing: 2px; margin:0; opacity:0.9;">Reporte del Tiempo</p>
            <h2 style="font-size: 80px; margin: 10px 0; font-weight: 700;">{curr['temperature']}°C</h2>
            <p style="font-size: 24px; font-weight: 600; text-transform: uppercase; margin:0;">{estado_es}</p>
            <div style="margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.4); padding-top: 15px; display: flex; justify-content: center; gap: 20px; font-size: 16px;">
                <span>Min: <strong>{day['temperature_min']}°</strong></span>
                <span>Viento: <strong>{curr['wind']['speed']} km/h</strong></span>
                <span>Max: <strong>{day['temperature_max']}°</strong></span>
            </div>
        </div>

        <div style="background: #fff; padding: 10px;">
            {cuerpo}
        </div>
        
        <div style="margin-top: 30px; padding: 15px; background: #f0f0f0; border-left: 4px solid #555; font-size: 14px; color: #666;">
            <em>Información generada automáticamente basada en datos de Meteosource.</em>
        </div>
    </div>
    """

    # 6. Publicar
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {'title': titulo, 'content': html_final, 'status': 'draft'}
    
    res = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post_data, auth=auth)
    
    if res.status_code == 201:
        print("✅ ÉXITO: Nota publicada con traducción y redacción completa.")
    else:
        print(f"❌ Error WP: {res.text}")

if __name__ == "__main__":
    main()

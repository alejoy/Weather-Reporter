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

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def generar_texto_gemini(prompt):
    """
    Conexión directa a la REST API de Google para evitar errores de librería.
    Usa el modelo Gemini 1.5 Pro.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
        }
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code != 200:
            print(f"⚠️ Error API Google ({response.status_code}): {response.text}")
            return None
            
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"⚠️ Excepción de conexión: {e}")
        return None

def main():
    # 1. Obtener clima de Meteosource
    print(f"Obteniendo datos precisos para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    weather_url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(weather_url)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Redacción Periodística (Directa a API)
    print("Enviando prompt a Gemini 1.5 Pro (REST API)...")
    
    prompt = f"""
    Actúa como Editor Jefe de un diario digital en la Patagonia Argentina.
    Redacta una NOTICIA COMPLETA y PROFESIONAL para Google Discover sobre el clima hoy en {TARGET_CITY}.

    DATOS:
    - Estado: {curr['summary']} (Traducir al español natural)
    - Temp Actual: {curr['temperature']}°C
    - Mínima: {day['temperature_min']}°C | Máxima: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h (Evaluar si es peligroso para la zona)

    REQUISITOS OBLIGATORIOS:
    1. IDIOMA: Español 100%.
    2. TITULAR SEO: Un título gancho que invite al clic (sin mentir).
    3. ESTRUCTURA: 
       - Primer párrafo: Resumen de impacto (Lead).
       - Segundo párrafo: Detalles de la temperatura y sensación.
       - Tercer párrafo: Análisis del viento (crucial en Neuquén).
       - Cuarto párrafo: Recomendaciones (ropa, tránsito).
    4. FORMATO: Usa etiquetas HTML <h3> para subtítulos y <strong> para resaltar datos. NO uses Markdown (# o *), usa HTML directo.
    """
    
    texto_ia = generar_texto_gemini(prompt)

    # Fallback si falla la API directa
    if not texto_ia:
        texto_ia = f"<h3>Reporte de {TARGET_CITY}</h3><p>Temperatura actual: <strong>{curr['temperature']}°C</strong>. Estado: {curr['summary']}. Se espera una máxima de {day['temperature_max']}°C.</p>"

    # 3. Formateo Final
    # Limpieza básica por si la IA devuelve algo de markdown
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    
    # Intentamos separar título si la IA lo puso en la primera línea
    lineas = texto_limpio.split('\n')
    titulo = lineas[0].replace('<h1>', '').replace('</h1>', '').replace('<h2>', '').replace('</h2>', '').strip()
    
    # Si el título parece muy largo o es un párrafo, usamos uno genérico y ponemos todo el texto en el cuerpo
    if len(titulo) > 100:
        titulo = f"El tiempo en {TARGET_CITY}: Todo lo que tenés que saber hoy"
        cuerpo = texto_limpio
    else:
        cuerpo = "\n".join(lineas[1:])

    color_header = "#e67e22" if curr['temperature'] > 25 else "#2980b9"

    html_final = f"""
    <div style="font-family: 'Merriweather', 'Georgia', serif; font-size: 18px; line-height: 1.8; color: #222;">
        <div style="background: {color_header}; color: white; padding: 40px; border-radius: 12px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-family: sans-serif; text-transform: uppercase; font-size: 14px; letter-spacing: 2px; opacity: 0.9;">Pronóstico Oficial</div>
            <div style="font-size: 80px; font-weight: 700; margin: 10px 0;">{curr['temperature']}°C</div>
            <div style="font-size: 24px; font-weight: 600; text-transform: uppercase;">{curr['summary']}</div>
            <div style="display: flex; justify-content: center; gap: 20px; margin-top: 25px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.4);">
                <span>Mín: <strong>{day['temperature_min']}°</strong></span>
                <span>Viento: <strong>{curr['wind']['speed']} km/h</strong></span>
                <span>Máx: <strong>{day['temperature_max']}°</strong></span>
            </div>
        </div>

        <div style="background: #fff; padding: 10px;">
            {cuerpo}
        </div>
        
        <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-left: 4px solid #333; font-size: 14px; font-family: sans-serif; color: #666;">
            Fuente: Meteosource API & Redacción Digital Automática.
        </div>
    </div>
    """

    # 4. Publicar
    print(f"Publicando nota: {titulo}")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {'title': titulo, 'content': html_final, 'status': 'draft'}

    res = requests.post(wp_api, json=post_data, auth=auth)
    
    if res.status_code == 201:
        print("✅ ÉXITO TOTAL: Nota generada y enviada a WordPress.")
    else:
        print(f"❌ Error WP: {res.text}")

if __name__ == "__main__":
    main()

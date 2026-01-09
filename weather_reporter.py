import os
import requests
from google import genai # Nueva librería

# 1. Configuración
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
TARGET_CITY = os.environ.get("TARGET_CITY", "Madrid")

# 2. Cliente de Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

def get_weather_data(city, api_key):
    url = "https://www.meteosource.com/api/v1/free/point"
    params = {'place_id': city.lower(), 'sections': 'current,daily', 'key': api_key, 'units': 'metric'}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data

def main():
    # Verificación de variables (mejorada para debug)
    required = ["METEOSOURCE_API_KEY", "GEMINI_API_KEY", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD", "WORDPRESS_URL"]
    for var in required:
        if not os.environ.get(var):
            print(f"ERROR: Falta la variable {var}")
            return

    # Obtener clima
    data = get_weather_data(TARGET_CITY, METEOSOURCE_API_KEY)
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # Generar Texto con Gemini 2.0 (el modelo de 2026)
    prompt = f"Escribe una noticia breve sobre el clima en {TARGET_CITY}. Hoy hace {curr['temperature']}°C con {curr['summary']}. Máxima de {day['temperature_max']}°C. Usa tono periodístico y termina con consejos."
    
    response = client.models.generate_content(
        model="gemini-2.0-flash", # Usando el modelo más actual
        contents=prompt
    )
    full_text = response.text

    # Preparar contenido HTML
    content_paragraphs = full_text.replace('\n', '</p><p>')
    title = f"Clima en {TARGET_CITY}: {curr['summary']} y {curr['temperature']}°C"
    
    html_content = f"""
    <div style='font-family: sans-serif;'>
        <h1>{title}</h1>
        <p>{content_paragraphs}</p>
        <p><strong>Datos técnicos:</strong> Viento a {curr['wind']['speed']} m/s. Humedad estimada.</p>
    </div>
    """

    # Publicar Borrador
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {'title': title, 'content': html_content, 'status': 'draft'}
    
    res = requests.post(wp_api, json=post_data, auth=auth)
    if res.status_code == 201:
        print(f"✅ ¡Éxito! Borrador creado en WordPress para {TARGET_CITY}.")
    else:
        print(f"❌ Error WP: {res.text}")

if __name__ == "__main__":
    main()

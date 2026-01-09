import os
import requests
import unicodedata
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

def normalizar_ciudad(texto):
    """Convierte 'Neuquén' en 'neuquen' para que la API no falle."""
    texto = texto.lower()
    # Elimina tildes
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')
    return texto
    
def get_weather_data(city, api_key):
    city_id = normalizar_ciudad(city)
    url = "https://www.meteosource.com/api/v1/free/point"
    params = {
        'place_id': city_id, 
        'sections': 'current,daily', 
        'key': api_key, 
        'units': 'metric'
    }
    response = requests.get(url, params=params)
    
    # Debug para ver qué pasó si falla
    if response.status_code != 200:
        print(f"Error API Meteosource: {response.status_code} - {response.text}")
        
    response.raise_for_status()
    return response.json()

def main():
    # ... (Verificación de variables igual)

    # 1. Obtener clima
    data = get_weather_data(TARGET_CITY, METEOSOURCE_API_KEY)
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Prompt Maestro para Nota + Placa
    prompt = f"""
    Actúa como un periodista digital. Datos de {TARGET_CITY}: 
    Actual: {curr['temperature']}°C, {curr['summary']}. Máx: {day['temperature_max']}°C, Mín: {day['temperature_min']}°C.
    
    Genera:
    1. Un titular corto y potente.
    2. Tres párrafos de noticia.
    3. Al final, escribe un bloque llamado [PROMPT_IMAGEN] con instrucciones detalladas para crear una placa de Instagram (1080x1080) que resuma estos datos usando un estilo visual moderno y limpio.
    """
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    full_output = response.text

    # 3. Separar la noticia del prompt de imagen
    partes = full_output.split("[PROMPT_IMAGEN]")
    noticia_html = partes[0].replace('\n', '</p><p>')
    prompt_grafico = partes[1] if len(partes) > 1 else "No se generó prompt de imagen"

    # 4. Formatear para WordPress
    title = f"Pronóstico en {TARGET_CITY}: {curr['summary']}"
    html_final = f"""
    <div style='background: #f4f4f4; padding: 20px; border-radius: 10px;'>
        <h2>{title}</h2>
        {noticia_html}
        <div style='background: #333; color: #fff; padding: 15px; margin-top: 20px;'>
            <strong>💡 SUGERENCIA DE PLACA PARA REDES:</strong><br>
            <em>{prompt_grafico}</em>
        </div>
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

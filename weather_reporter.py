import os
import requests
import unicodedata
from google import genai

# CONFIGURACIÓN
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/') # Quita barra final si existe
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

client = genai.Client(api_key=GEMINI_API_KEY)

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def main():
    # A. Obtener clima
    print(f"Obteniendo clima para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    weather_url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(weather_url)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']

    # B. Redactar con Gemini
    print("Redactando con Gemini...")
    prompt = f"Escribe una noticia breve sobre el clima en {TARGET_CITY}. Hoy hace {curr['temperature']}°C con {curr['summary']}."
    
    try:
        # Cambio de nombre de modelo para máxima compatibilidad
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        texto_ia = response.text
    except Exception as e:
        print(f"Error IA: {e}")
        texto_ia = f"Reporte automático: El clima en {TARGET_CITY} presenta {curr['summary']} con {curr['temperature']}°C."

    # C. Publicar en WordPress
    print("Enviando a WordPress...")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    
    # IMPORTANTE: Asegúrate de que WORDPRESS_APP_PASSWORD no tenga espacios al guardarlo en GitHub
    # o si los tiene, pásalos tal cual.
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    
    post_data = {
        'title': f"Clima en {TARGET_CITY}: {curr['summary']}",
        'content': f"<h3>Reporte actualizado</h3><p>{texto_ia.replace('\n', '<br>')}</p>",
        'status': 'draft'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json'
    }

    res_wp = requests.post(wp_api, json=post_data, auth=auth, headers=headers)
    
    if res_wp.status_code == 201:
        print("✅ ¡LOGRADO! Nota creada en WordPress.")
    else:
        print(f"❌ Error {res_wp.status_code}: {res_wp.text}")

if __name__ == "__main__":
    main()

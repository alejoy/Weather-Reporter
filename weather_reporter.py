import os
import requests
import unicodedata
from google import genai

# 1. CONFIGURACIÓN DE VARIABLES
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# 2. CLIENTE DE IA
client = genai.Client(api_key=GEMINI_API_KEY)

def normalizar_ciudad(texto):
    """Convierte 'Neuquén' en 'neuquen' para la API."""
    texto = texto.lower()
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
    response.raise_for_status()
    return response.json()

def main():
    # Verificar que no falten datos
    required = ["METEOSOURCE_API_KEY", "GEMINI_API_KEY", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD", "WORDPRESS_URL"]
    for var in required:
        if not os.environ.get(var):
            print(f"ERROR: Falta configurar {var} en los Secretos de GitHub")
            return

    # A. Obtener datos del clima
    print(f"Obteniendo clima para {TARGET_CITY}...")
    data = get_weather_data(TARGET_CITY, METEOSOURCE_API_KEY)
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # B. Redactar nota con IA (Usamos 1.5 Flash para evitar errores de cuota)
    print("Redactando nota con Gemini...")
    prompt = f"""
    Actúa como periodista meteorológico. Ciudad: {TARGET_CITY}.
    Clima actual: {curr['temperature']}°C, {curr['summary']}. 
    Extremos: Máxima {day['temperature_max']}°C, Mínima {day['temperature_min']}°C.
    
    Escribe:
    1. Un titular periodístico.
    2. La noticia en 3 párrafos informativos.
    3. Una sugerencia de 'Prompt' para generar una imagen de redes sociales al final.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        texto_ia = response.text
    except Exception as e:
        print(f"Error con Gemini: {e}")
        texto_ia = f"Reporte del clima para {TARGET_CITY}. Temperatura actual: {curr['temperature']}°C."

    # C. Formatear para WordPress (HTML)
    title = f"Pronóstico del Tiempo en {TARGET_CITY}: {curr['summary']}"
    # Convertimos los saltos de línea en párrafos HTML
    cuerpo_html = texto_ia.replace('\n', '<br>')
    
    html_final = f"""
    <div style="font-family: Arial; line-height: 1.6; color: #333;">
        <div style="background: #0073aa; color: white; padding: 20px; text-align: center; border-radius: 10px;">
            <h2 style="margin:0;">CLIMA EN {TARGET_CITY.upper()}</h2>
            <p style="font-size: 40px; margin: 10px 0;">{curr['temperature']}°C</p>
            <p>{curr['summary'].upper()}</p>
        </div>
        <div style="padding: 20px;">
            {cuerpo_html}
        </div>
        <p style="color: #888; font-size: 12px;">Generado automáticamente para revisión.</p>
    </div>
    """

    # D. Publicar en WordPress como Borrador
    print("Enviando a WordPress...")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {
        'title': title,
        'content': html_final,
        'status': 'draft' # Se guarda en 'Borradores'
    }
    
    res = requests.post(wp_api, json=post_data, auth=auth)
    if res.status_code == 201:
        print(f"✅ ÉXITO: Nota creada en WordPress. Ve a tu panel para revisarla.")
    else:
        print(f"❌ Error al publicar: {res.text}")

if __name__ == "__main__":
    main()

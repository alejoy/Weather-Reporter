import os
import requests
import google.generativeai as genai

# --- 1. Configuración de API Keys y URLs ---
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
TARGET_CITY = os.environ.get("TARGET_CITY", "Madrid") # Por defecto Madrid

# Configurar Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

def get_weather_data(city, api_key):
    """Obtiene el pronóstico de Meteosource usando el endpoint 'point'."""
    # Primero, Meteosource prefiere coordenadas o IDs de lugar. 
    # Para simplicidad, usamos su búsqueda de lugares primero o el endpoint de texto.
    url = "https://www.meteosource.com/api/v1/free/point"
    params = {
        'place_id': city.lower(), # Ej: 'madrid'
        'sections': 'current,daily',
        'timezone': 'auto',
        'language': 'es',
        'units': 'metric',
        'key': api_key
    }
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    # Mapeo de datos para mantener compatibilidad con el resto del script
    current = data['current']
    return {
        'name': city.capitalize(),
        'main': {
            'temp': current['temperature'],
            'feels_like': current['temperature'], # Meteosource Free no siempre da feels_like
            'humidity': 50, # Valor genérico si no está en el plan free
            'temp_max': data['daily']['data'][0]['all_day']['temperature_max'],
            'temp_min': data['daily']['data'][0]['all_day']['temperature_min']
        },
        'weather': [{'description': current['summary']}],
        'wind': {'speed': current['wind']['speed']}
    }
def generate_news_copy(weather_data):
    """Genera el texto de la noticia usando Gemini."""
    city = weather_data['name']
    temp = weather_data['main']['temp']
    feels_like = weather_data['main']['feels_like']
    description = weather_data['weather'][0]['description']
    humidity = weather_data['main']['humidity']
    wind_speed = weather_data['wind']['speed'] # m/s

    prompt = f"""
    Eres un periodista experto en noticias meteorológicas.
    Escribe una nota periodística concisa y atractiva sobre el pronóstico del tiempo para {city}.
    Incluye un titular llamativo y un cuerpo de texto que resuma los datos clave.
    El tono debe ser informativo y ligeramente cautivador.

    Datos del Clima para {city}:
    - Temperatura actual: {temp}°C
    - Sensación térmica: {feels_like}°C
    - Condiciones: {description}
    - Humedad: {humidity}%
    - Viento: {wind_speed:.1f} m/s (convertir a km/h si es posible, aprox. {wind_speed * 3.6:.1f} km/h)

    Estructura esperada:
    [TITULAR_ATRACTIVO]

    [Cuerpo de la noticia con párrafos cortos. Menciona la temperatura, condiciones y recomendaciones.]
    """
    response = model.generate_content(prompt)
    return response.text

def post_to_wordpress(title, content, wp_url, username, app_password):
    """Publica la nota en WordPress como borrador."""
    api_url = f"{wp_url}/wp-json/wp/v2/posts"
    headers = {
        'Content-Type': 'application/json'
    }
    auth = requests.auth.HTTPBasicAuth(username, app_password)
    
    post_data = {
        'title': title,
        'content': content,
        'status': 'draft' # Publicar como borrador para revisión
    }

    try:
        response = requests.post(api_url, headers=headers, json=post_data, auth=auth)
        response.raise_for_status() # Lanzar excepción para códigos de estado erróneos
        print(f"Nota '{title}' publicada como borrador en WordPress con éxito.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al publicar en WordPress: {e}")
        print(f"Respuesta del servidor: {response.text if 'response' in locals() else 'No response'}")
        return None

def main():
    if not all([OPENWEATHER_API_KEY, GEMINI_API_KEY, WORDPRESS_USER, WORDPRESS_APP_PASSWORD, WORDPRESS_URL]):
        print("Error: Asegúrate de que todas las variables de entorno están configuradas.")
        exit(1)

    print(f"Obteniendo datos del clima para {TARGET_CITY}...")
    weather_data = get_weather_data(TARGET_CITY, OPENWEATHER_API_KEY)
    print("Datos del clima obtenidos.")

    print("Generando texto de la noticia con Gemini...")
    full_news_copy = generate_news_copy(weather_data)
    
    # Extraer título y contenido
    lines = full_news_copy.strip().split('\n')
    title = lines[0].strip()
    content = '\n'.join(lines[1:]).strip() # El resto es el contenido
    
    # --- Generación de imagen para redes ---
    # Aquí es donde el modelo mágico de imagen interviene
    # El prompt para la imagen debería ser algo así:
    # "Una placa para redes sociales con el pronóstico del tiempo para [Ciudad].
    # Debe mostrar la temperatura máxima y mínima, el estado del cielo (soleado, nublado, etc.)
    # y un ícono representativo. Usa colores claros y un diseño moderno."
    # Para la prueba de concepto, simplemente imprimiremos el prompt de imagen.
    print("\n--- PROMPT PARA GENERACIÓN DE IMAGEN PARA REDES SOCIALES ---")
    image_prompt = f"""
    Crea una placa visualmente atractiva para redes sociales (formato cuadrado o 1:1)
    con el pronóstico del tiempo para {TARGET_CITY}.
    Elementos clave a incluir:
    - **Título:** "Pronóstico {TARGET_CITY}" o "El Tiempo en {TARGET_CITY}"
    - **Temperatura Máxima:** (ej. {weather_data['main'].get('temp_max', weather_data['main']['temp'])}°C)
    - **Temperatura Mínima:** (ej. {weather_data['main'].get('temp_min', weather_data['main']['temp'])}°C)
    - **Condición principal:** (ej. {weather_data['weather'][0]['description']})
    - **Ícono representativo** del clima (sol, nubes, lluvia, etc.).
    - **Humedad:** {weather_data['main']['humidity']}%
    - **Velocidad del viento:** {weather_data['wind']['speed'] * 3.6:.1f} km/h
    - **Fecha:** Hoy
    - Estilo: Limpio, moderno, con colores asociados al clima (azules, blancos, amarillos).
    """
    print(image_prompt)
    print("----------------------------------------------------------")

    # Si tuvieras una API de generación de imágenes, aquí la llamarías y obtendrías una URL.
    # Por ahora, simplemente simula la generación.
    # image_url = generate_social_media_image(image_prompt)
    image_url = "https://example.com/placeholder-weather-image.jpg" # Placeholder

    # Añadir un enlace a la imagen en el contenido de la nota para la revisión
    html_content = f"<img src='{image_url}' alt='Placa del clima para redes sociales' /><br/>"
    html_content += f"<h1>{title}</h1>"
    html_content += f"<p>{content.replace('\n', '</p><p>')}</p>" # Formatear párrafos

    print("\nPublicando nota en WordPress como borrador...")
    post_to_wordpress(title, html_content, WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_APP_PASSWORD)

if __name__ == "__main__":
    main()

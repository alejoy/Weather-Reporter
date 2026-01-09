import os
import requests
import unicodedata
from google import genai

# CONFIGURACIÓN
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

client = genai.Client(api_key=GEMINI_API_KEY)

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def main():
    print(f"Obteniendo datos climáticos profundos para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    
    # Pedimos secciones más completas (current y daily)
    weather_url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(weather_url)
    res_w.raise_for_status()
    data = res_w.json()
    
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    # Extraemos info específica para el editor
    viento_vel = curr['wind']['speed']
    viento_dir = curr['wind']['dir']

    print("Redactando nota editorial...")
    
    # PROMPT AVANZADO
    prompt = f"""
    Eres el editor jefe de la sección clima de un importante diario de la Patagonia Argentina.
    Escribe una nota periodística completa sobre el tiempo hoy en {TARGET_CITY}.
    
    DATOS TÉCNICOS:
    - Estado actual: {curr['summary']}
    - Temperatura actual: {curr['temperature']}°C
    - Máxima prevista: {day['temperature_max']}°C
    - Mínima prevista: {day['temperature_min']}°C
    - Viento: {viento_vel} km/h dirección {viento_dir}
    
    REQUISITOS DE LA NOTA:
    1. Título: Atractivo y profesional (usa el estilo de diarios como La Mañana o Río Negro).
    2. Introducción: Describe cómo arranca la jornada en la ciudad.
    3. Desarrollo: Analiza cómo evolucionará la temperatura hacia la tarde y menciona el viento (factor clave en Patagonia).
    4. Conclusión: Recomendaciones para los ciudadanos (ropa, cuidados, actividades al aire libre).
    5. Estilo: Serio, informativo pero cercano. No uses listas, usa párrafos fluidos.
    """
    
    try:
        # Usamos gemini-1.5-flash que es estable
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        texto_ia = response.text
    except Exception as e:
        print(f"Error IA: {e}")
        texto_ia = "Error en la redacción automática."

    # C. Formatear para WordPress con un diseño más elegante
    print("Enviando a WordPress...")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    
    # Separamos el título del cuerpo (asumiendo que la IA pone el título en la primera línea)
    lineas = texto_ia.strip().split('\n')
    titulo_nota = lineas[0].replace('#', '').strip()
    cuerpo_nota = '<p>' + '</p><p>'.join(lineas[1:]) + '</p>'
    
    # Creamos un bloque visual para los datos clave
    bloque_datos = f"""
    <div style="background:#f9f9f9; border-left:5px solid #e67e22; padding:15px; margin-bottom:20px;">
        <strong>Servicio Meteorológico Personalizado</strong><br>
        📍 Ciudad: {TARGET_CITY}<br>
        🌡️ Extremos: {day['temperature_min']}°C / {day['temperature_max']}°C<br>
        🌬️ Viento: {viento_vel} km/h {viento_dir}
    </div>
    """

    post_data = {
        'title': titulo_nota if len(titulo_nota) > 10 else f"El tiempo en {TARGET_CITY}: Pronóstico para hoy",
        'content': bloque_datos + cuerpo_nota,
        'status': 'draft'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/json'
    }

    res_wp = requests.post(wp_api, json=post_data, auth=auth, headers=headers)
    
    if res_wp.status_code == 201:
        print(f"✅ ¡LOGRADO! Nota publicada como borrador: {titulo_nota}")
    else:
        print(f"❌ Error {res_wp.status_code}: {res_wp.text}")

if __name__ == "__main__":
    main()

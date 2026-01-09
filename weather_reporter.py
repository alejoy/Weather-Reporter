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

# Inicialización del cliente (Ajuste para evitar 404)
client = genai.Client(api_key=GEMINI_API_KEY)

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def main():
    # 1. Obtener clima
    print(f"Conectando con Meteosource para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    weather_url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(weather_url)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    viento_vel = curr['wind']['speed']

    # 2. Redactar con Gemini (Ajuste de modelo)
    print("Redactando nota editorial...")
    prompt = f"""
    Eres el Editor Jefe de un diario en Neuquén. Escribe una nota periodística profesional.
    DATOS: {TARGET_CITY}, {curr['temperature']}°C, {curr['summary']}, Viento {viento_vel}km/h.
    Máxima: {day['temperature_max']}°C, Mínima: {day['temperature_min']}°C.
    
    REQUISITOS:
    - Titular profesional sin hashtags.
    - Tres párrafos analizando la jornada y el impacto del viento.
    - Tono serio y regional.
    """
    
    try:
        # Probamos la llamada estándar
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        texto_ia = response.text
    except Exception as e:
        print(f"Error detectado: {e}. Reintentando con configuración alternativa...")
        # Fallback de texto si la cuota o el modelo fallan
        texto_ia = f"Jornada con {curr['summary']} en {TARGET_CITY}. Se espera una máxima de {day['temperature_max']}°C."

    # 3. Diseño de la Placa y Cuerpo
    color_clima = "#e67e22" if curr['temperature'] > 25 else "#3498db"
    
    # Separar título de cuerpo
    partes = texto_ia.strip().split('\n', 1)
    titulo_final = partes[0].replace('#', '').strip()
    cuerpo_final = partes[1].replace('\n', '<br>') if len(partes) > 1 else partes[0]

    html_final = f"""
    <div style="max-width:600px; margin:auto; font-family: 'Helvetica', sans-serif; border:1px solid #ddd; border-radius:15px; overflow:hidden;">
        <div style="background: {color_clima}; color: white; padding: 40px 20px; text-align: center;">
            <h2 style="margin: 0; text-transform: uppercase; font-size: 18px; letter-spacing: 2px;">Pronóstico Hoy</h2>
            <div style="font-size: 72px; font-weight: bold; margin: 10px 0;">{curr['temperature']}°C</div>
            <p style="font-size: 20px; margin: 0;">{curr['summary'].upper()}</p>
            <div style="margin-top: 20px; display: flex; justify-content: space-around; font-size: 14px; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 15px;">
                <span>🌡️ Mín: {day['temperature_min']}°C</span>
                <span>🌬️ Viento: {viento_vel} km/h</span>
                <span>🌡️ Máx: {day['temperature_max']}°C</span>
            </div>
        </div>
        <div style="padding: 25px; line-height: 1.8; color: #2c3e50; font-size: 17px; background: white;">
            {cuerpo_final}
        </div>
    </div>
    """

    # 4. Enviar a WordPress
    print("Publicando en WordPress...")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    
    post_data = {
        'title': titulo_final,
        'content': html_final,
        'status': 'draft'
    }

    res_wp = requests.post(wp_api, json=post_data, auth=auth)
    
    if res_wp.status_code == 201:
        print(f"✅ LOGRADO: '{titulo_final}' disponible en borradores.")
    else:
        print(f"❌ Error WP {res_wp.status_code}: {res_wp.text}")

if __name__ == "__main__":
    main()

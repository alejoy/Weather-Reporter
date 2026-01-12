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

# INICIALIZACIÓN PRO: Forzamos la versión v1 de producción
client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def main():
    # 1. Obtención de Datos
    print(f"Buscando datos meteorológicos de precisión para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    weather_url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(weather_url)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Redacción Periodística (Gemini 1.5 Pro)
    print("Enviando datos a Gemini 1.5 Pro para redacción editorial...")
    
    prompt = f"""
    Actúa como el Director Editorial de un importante diario digital patagónico. 
    Tu objetivo es escribir una nota de alto impacto para Google Discover sobre el pronóstico en {TARGET_CITY}.

    DATOS ACTUALES:
    - Estado: {curr['summary']}
    - Temperatura actual: {curr['temperature']}°C
    - Máxima prevista: {day['temperature_max']}°C | Mínima: {day['temperature_min']}°C
    - Viento: {curr['wind']['speed']} km/h con ráfagas.

    REQUISITOS TÉCNICOS Y SEO:
    1. IDIOMA: Escribe íntegramente en español neutro/argentino profesional.
    2. TITULAR SEO: Crea un título "gancho" (Click-worthy) para Discover. Si hay calor (>28°C) o viento (>35km/h), destácalo como alerta.
    3. ESTRUCTURA: Al menos 4-5 párrafos largos. Usa <h3> para subtítulos y <strong> para datos clave.
    4. TONO: Periodismo de servicio. Analiza cómo afectará el clima al día de los vecinos (ropa, transporte, actividades).
    5. DETALLES: Si el viento es fuerte, menciona las precauciones necesarias en la zona del Alto Valle.
    """
    
    try:
        # Usamos el modelo PRO para máxima calidad
        response = client.models.generate_content(
            model="gemini-1.5-pro", 
            contents=prompt
        )
        texto_ia = response.text
    except Exception as e:
        print(f"Error con Pro: {e}. Intentando con Flash...")
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        texto_ia = response.text

    # 3. Formateo de Contenido
    color_header = "#e67e22" if curr['temperature'] > 26 else "#2980b9"
    
    # Limpiamos el texto de la IA (títulos y saltos)
    partes = texto_ia.strip().split('\n', 1)
    titulo_final = partes[0].replace('#', '').replace('*', '').strip()
    cuerpo_final = partes[1].replace('\n', '<br>') if len(partes) > 1 else partes[0]

    html_final = f"""
    <article style="max-width:750px; margin:auto; font-family: 'Georgia', serif; color: #2c3e50; line-height: 1.8;">
        <div style="background: {color_header}; color: white; padding: 50px 25px; text-align: center; border-radius: 15px; margin-bottom: 30px; box-shadow: 0 10px 20px rgba(0,0,0,0.1);">
            <h2 style="font-family: sans-serif; text-transform: uppercase; font-size: 16px; letter-spacing: 3px; margin-bottom: 10px;">Pronóstico Regional</h2>
            <div style="font-size: 95px; font-weight: bold; margin: 0;">{curr['temperature']}°C</div>
            <p style="font-size: 26px; font-weight: bold; text-transform: uppercase; margin-top: 10px;">{curr['summary']}</p>
            <div style="margin-top: 25px; display: flex; justify-content: center; gap: 30px; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 20px; font-size: 15px;">
                <span><strong>MÍN:</strong> {day['temperature_min']}°C</span>
                <span><strong>VIENTO:</strong> {curr['wind']['speed']} km/h</span>
                <span><strong>MÁX:</strong> {day['temperature_max']}°C</span>
            </div>
        </div>

        <div style="font-size: 20px; background: white; padding: 0 10px;">
            {cuerpo_final}
        </div>
        
        <footer style="margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px; font-size: 14px; color: #95a5a6; text-align: center;">
            © 2026 - Servicio Meteorológico Automatizado - Actualización en tiempo real.
        </footer>
    </article>
    """

    # 4. Inserción en WordPress
    print(f"Publicando nota Pro: {titulo_final}")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    
    post_data = {
        'title': titulo_final,
        'content': html_final,
        'status': 'draft'
    }

    res_wp = requests.post(wp_api, json=post_data, auth=auth)
    
    if res_wp.status_code == 201:
        print("✅ ÉXITO: La nota editorial Pro ha sido creada en borradores.")
    else:
        print(f"❌ Error WP: {res_wp.text}")

if __name__ == "__main__":
    main()

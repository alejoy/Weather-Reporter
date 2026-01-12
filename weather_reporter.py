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
    # 1. Obtener datos
    print(f"Obteniendo datos de Meteosource...")
    city_id = normalizar_ciudad(TARGET_CITY)
    weather_url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(weather_url)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Redacción Editorial de Alto Impacto (PROMPT MEJORADO)
    print("Redactando nota SEO con Gemini...")
    
    prompt = f"""
    Eres el Editor Jefe de un diario digital líder en la Patagonia. 
    Escribe una noticia optimizada para Google Discover y SEO sobre el clima en {TARGET_CITY}.

    DATOS TÉCNICOS:
    - Estado actual: {curr['summary']} (Tradúcelo al español)
    - Temperatura: {curr['temperature']}°C
    - Máxima: {day['temperature_max']}°C | Mínima: {day['temperature_min']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS OBLIGATORIOS:
    1. IDIOMA: Todo el contenido DEBE estar en español.
    2. TITULAR SEO: Debe ser llamativo, usar verbos de acción y mencionar si hay alertas (viento, calor extremo o frío).
    3. ESTRUCTURA: Al menos 4 párrafos extensos y bien redactados.
    4. FORMATO: Usa negritas (<strong>) para datos clave y subtítulos (<h3>) para separar secciones.
    5. SEO: Incluye palabras clave como "pronóstico", "clima", "Neuquén", "viento".
    6. GOOGLE DISCOVER: El primer párrafo debe ser un "gancho" que invite a seguir leyendo.
    7. ALERTAS: Si el viento supera los 40km/h o la temperatura los 32°C, destácalo como una advertencia importante.
    """
    
    try:
        # Usamos 1.5-pro si tienes acceso, o 1.5-flash para velocidad
        response = client.models.generate_content(
            model="gemini-1.5-flash", 
            contents=prompt
        )
        texto_ia = response.text
    except Exception as e:
        print(f"Error IA: {e}")
        return

    # 3. Procesamiento de la nota
    partes = texto_ia.strip().split('\n', 1)
    titulo_final = partes[0].replace('#', '').replace('*', '').strip()
    cuerpo_final = partes[1].replace('\n', '<br>') if len(partes) > 1 else partes[0]

    # Traducción manual del resumen para la PLACA (por si la IA no lo hace ahí)
    resumen_es = "NUBOSIDAD VARIABLE" if "cloudy" in curr['summary'].lower() else curr['summary'].upper()
    color_clima = "#e67e22" if curr['temperature'] > 25 else "#3498db"

    html_final = f"""
    <div style="max-width:700px; margin:auto; font-family: 'Georgia', serif; line-height: 1.8; color: #333;">
        <div style="background: {color_clima}; color: white; padding: 40px 20px; text-align: center; border-radius: 10px; margin-bottom: 25px;">
            <span style="text-transform: uppercase; font-weight: bold; font-family: sans-serif; opacity: 0.9;">Reporte Meteorológico - {TARGET_CITY}</span>
            <div style="font-size: 80px; font-weight: bold; margin: 10px 0;">{curr['temperature']}°C</div>
            <p style="font-size: 22px; margin: 0; font-weight: bold;">{resumen_es}</p>
        </div>
        
        <div style="font-size: 19px; background: white;">
            {cuerpo_final}
        </div>
        
        <div style="margin-top: 30px; padding: 15px; background: #f4f4f4; border-left: 5px solid #333; font-style: italic;">
            Este reporte se actualiza automáticamente con datos de estaciones meteorológicas regionales.
        </div>
    </div>
    """

    # 4. Envío a WordPress
    print(f"Enviando a WordPress: {titulo_final}")
    wp_api = f"{WORDPRESS_URL}/wp-json/wp/v2/posts"
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    
    post_data = {{
        'title': titulo_final,
        'content': html_final,
        'status': 'draft'
    }}

    res_wp = requests.post(wp_api, json=post_data, auth=auth)
    
    if res_wp.status_code == 201:
        print(f"✅ ÉXITO: Nota '{titulo_final}' creada correctamente.")
    else:
        print(f"❌ Error WP: {res_wp.text}")

if __name__ == "__main__":
    main()

import os
import requests
import unicodedata
import google.generativeai as genai

# CONFIGURACIÓN
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# Inicialización con la librería estable
genai.configure(api_key=GEMINI_API_KEY)

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def main():
    # 1. Obtener clima
    print(f"Obteniendo datos de precisión para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    url = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(url)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Redacción Profesional con Gemini 1.5 Pro
    print("Redactando nota editorial con Gemini 1.5 Pro...")
    
    # Usamos gemini-1.5-pro para máxima calidad SEO y Discover
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = f"""
    Eres el Director Editorial de un diario líder en Neuquén. 
    Escribe una noticia de alto impacto para Google Discover sobre el clima hoy en {TARGET_CITY}.

    DATOS CLAVE:
    - Temperatura actual: {curr['temperature']}°C
    - Estado: {curr['summary']} (Traducir al español profesionalmente)
    - Máxima: {day['temperature_max']}°C | Mínima: {day['temperature_min']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS SEO Y PERIODÍSTICOS:
    1. TITULAR: Atractivo para clics, profesional, que mencione a {TARGET_CITY} y la alerta principal (viento o calor).
    2. CUERPO: Al menos 4 párrafos largos y fluidos.
    3. FORMATO HTML: Usa <h3> para subtítulos y <strong> para datos importantes.
    4. ESTILO: Analiza el impacto del viento en el Alto Valle y da consejos prácticos. Todo en ESPAÑOL.
    5. SEO: Repite de forma natural palabras como "pronóstico", "clima" y "Neuquén".
    """

    try:
        response = model.generate_content(prompt)
        texto_ia = response.text
    except Exception as e:
        print(f"Error crítico en IA: {e}")
        return

    # 3. Formateo y Placa
    # Separar título de cuerpo
    lineas = texto_ia.strip().split('\n')
    titulo_final = lineas[0].replace('#', '').replace('*', '').strip()
    cuerpo_final = '<p>' + '</p><p>'.join(lineas[1:]) + '</p>'
    
    color_clima = "#e67e22" if curr['temperature'] > 26 else "#2980b9"

    html_final = f"""
    <div style="max-width:700px; margin:auto; font-family: 'Georgia', serif; line-height: 1.8; color: #2c3e50;">
        <div style="background: {color_clima}; color: white; padding: 40px 20px; text-align: center; border-radius: 12px; margin-bottom: 30px;">
            <h2 style="font-family: sans-serif; text-transform: uppercase; font-size: 14px; letter-spacing: 2px; margin:0;">Pronóstico Regional</h2>
            <div style="font-size: 85px; font-weight: bold; margin: 5px 0;">{curr['temperature']}°C</div>
            <p style="font-size: 22px; font-weight: bold; text-transform: uppercase; margin:0;">{curr['summary']}</p>
            <div style="margin-top: 20px; display: flex; justify-content: center; gap: 25px; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 15px; font-size: 14px;">
                <span>MÍN: {day['temperature_min']}°C</span>
                <span>VIENTO: {curr['wind']['speed']} km/h</span>
                <span>MÁX: {day['temperature_max']}°C</span>
            </div>
        </div>
        <div style="font-size: 19px; background: white;">
            {cuerpo_final}
        </div>
    </div>
    """

    # 4. Envío a WordPress
    print(f"Publicando en WordPress: {titulo_final}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {{
        'title': titulo_final,
        'content': html_final,
        'status': 'draft'
    }}

    res = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post_data, auth=auth)
    
    if res.status_code == 201:
        print("✅ ¡LOGRADO! Nota Pro creada con éxito.")
    else:
        print(f"❌ Error WP: {res.text}")

if __name__ == "__main__":
    main()

import os
import requests
import unicodedata
import json

# CONFIGURACIÓN
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# DICCIONARIO DE TRADUCCIÓN (Para la placa visual)
TRADUCCIONES = {
    "sunny": "Soleado",
    "mostly sunny": "Mayormente Soleado",
    "partly sunny": "Parcialmente Soleado",
    "mostly cloudy": "Mayormente Nublado",
    "cloudy": "Nublado",
    "overcast": "Cubierto",
    "rain": "Lluvia",
    "light rain": "Lluvia Débil",
    "heavy rain": "Lluvia Intensa",
    "snow": "Nieve",
    "thunderstorm": "Tormenta",
    "clear": "Despejado",
    "fog": "Niebla",
    "mist": "Neblina"
}

def traducir_estado(texto_ingles):
    """Traduce el estado del clima o lo devuelve en mayúsculas si no lo encuentra."""
    texto_lower = texto_ingles.lower().strip()
    return TRADUCCIONES.get(texto_lower, texto_ingles).upper()

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def intentar_generar_con_modelo(modelo, prompt):
    """Intenta conectar con un modelo específico de Gemini."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    
    try:
        print(f"🔄 Probando conexión con modelo: {modelo}...")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Falló {modelo} (Error {response.status_code})")
            return None
    except Exception as e:
        print(f"⚠️ Error de red con {modelo}: {e}")
        return None

def obtener_texto_ia(prompt):
    # LISTA DE MODELOS A PROBAR (En orden de preferencia)
    # Si falla el Pro, va al Flash, si falla va al Pro antiguo.
    modelos_a_probar = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"]
    
    for modelo in modelos_a_probar:
        texto = intentar_generar_con_modelo(modelo, prompt)
        if texto:
            print(f"✅ ¡Conexión exitosa con {modelo}!")
            return texto
    
    return None

def main():
    # 1. Obtener clima
    print(f"Obteniendo datos para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    # 2. Traducción manual (Corrección del 'Mostly Cloudy')
    estado_es = traducir_estado(curr['summary'])

    # 3. Redacción con IA (Estrategia Multi-Modelo)
    print("Iniciando redacción periodística...")
    
    prompt = f"""
    Actúa como un periodista experto de Neuquén. Escribe una NOTICIA LARGA (SEO) sobre el clima.
    
    DATOS:
    - Ciudad: {TARGET_CITY}
    - Estado: {estado_es}
    - Temperatura: {curr['temperature']}°C
    - Mín: {day['temperature_min']}°C | Máx: {day['temperature_max']}°C
    - Viento: {curr['wind']['speed']} km/h

    REQUISITOS OBLIGATORIOS:
    1. Escribe 4 PÁRRAFOS COMPLETOS. No hagas resúmenes cortos.
    2. Usa un tono serio y profesional.
    3. Analiza el viento y da recomendaciones.
    4. Usa etiquetas HTML <h3> para subtítulos y <strong> para resaltar datos.
    5. IDIOMA: ESPAÑOL.
    """
    
    texto_ia = obtener_texto_ia(prompt)

    # Fallback final de emergencia (Solo si los 3 modelos fallan)
    if not texto_ia:
        print("❌ Todos los modelos fallaron. Usando plantilla de emergencia.")
        texto_ia = f"""
        <h3>Reporte Meteorológico para {TARGET_CITY}</h3>
        <p>La ciudad de <strong>{TARGET_CITY}</strong> presenta hoy condiciones de <strong>{estado_es}</strong> con una temperatura actual de <strong>{curr['temperature']}°C</strong>.</p>
        <p>Se espera una temperatura máxima de {day['temperature_max']}°C y una mínima de {day['temperature_min']}°C. El viento sopla a {curr['wind']['speed']} km/h.</p>
        <p>Se recomienda precaución al circular y mantenerse informado sobre las alertas locales.</p>
        <p><em>(Nota generada automáticamente por fallo de conexión con el servicio de redacción).</em></p>
        """

    # 4. Procesamiento de texto
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    
    # Intento de sacar título
    titulo = lineas[0].replace('<h1>', '').replace('</h1>', '').replace('#', '').replace('*', '').strip()
    
    # Validación de título y cuerpo
    if len(titulo) > 100 or "<" in titulo: 
        titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
        cuerpo = texto_limpio
    else:
        cuerpo = "\n".join(lineas[1:])

    # 5. Generación de HTML Final (PLACA CORREGIDA EN ESPAÑOL)
    color_bg = "#e67e22" if curr['temperature'] > 26 else "#2980b9"
    
    html_final = f"""
    <div style="font-family: 'Georgia', serif; font-size: 18px; color: #333; line-height: 1.6;">
        <div style="background: {color_bg}; color: white; padding: 40px; border-radius: 12px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <p style="text-transform: uppercase; font-size: 14px; letter-spacing: 2px; margin:0; opacity:0.9; font-family: sans-serif;">Pronóstico del Tiempo</p>
            <h2 style="font-size: 90px; margin: 5px 0; font-weight: 700; font-family: sans-serif;">{curr['temperature']}°C</h2>
            <p style="font-size: 26px; font-weight: 700; text-transform: uppercase; margin:0; font-family: sans-serif;">{estado_es}</p>
            <div style="margin-top: 25px; border-top: 1px solid rgba(255,255,255,0.4); padding-top: 20px; display: flex; justify-content: center; gap: 30px; font-size: 16px;">
                <span>Min: <strong>{day['temperature_min']}°</strong></span>
                <span>Viento: <strong>{curr['wind']['speed']} km/h</strong></span>
                <span>Max: <strong>{day['temperature_max']}°</strong></span>
            </div>
        </div>

        <div style="background: #fff; padding: 10px;">
            {cuerpo}
        </div>
        
        <div style="margin-top: 30px; padding: 15px; background: #f9f9f9; border-left: 4px solid #333; font-size: 14px; color: #666;">
            <em>Fuente: Meteosource y Redacción Digital Automática.</em>
        </div>
    </div>
    """

    # 6. Publicar
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {'title': titulo, 'content': html_final, 'status': 'draft'}
    
    res = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post_data, auth=auth)
    
    if res.status_code == 201:
        print("✅ ÉXITO: Nota publicada en WordPress.")
    else:
        print(f"❌ Error WP: {res.text}")

if __name__ == "__main__":
    main()

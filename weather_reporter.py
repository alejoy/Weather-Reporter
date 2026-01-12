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

# DICCIONARIO DE TRADUCCIÓN
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
    texto_lower = texto_ingles.lower().strip()
    return TRADUCCIONES.get(texto_lower, texto_ingles).upper()

def normalizar_ciudad(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto

def descubrir_mejor_modelo():
    """Consulta a la API qué modelos están disponibles y elige el mejor."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"⚠️ Error al listar modelos ({res.status_code})")
            return None
        
        modelos = res.json().get('models', [])
        print(f"🔎 Se encontraron {len(modelos)} modelos disponibles.")
        
        # Prioridad de elección: Pro > Flash > Pro Viejo > Cualquiera que genere contenido
        for m in modelos:
            nombre = m['name'] # Viene como 'models/gemini-1.5-pro'
            if 'generateContent' in m['supportedGenerationMethods']:
                if 'gemini-1.5-pro' in nombre:
                    return nombre
        
        # Si no hay Pro, buscamos Flash
        for m in modelos:
            nombre = m['name']
            if 'generateContent' in m['supportedGenerationMethods']:
                if 'gemini-1.5-flash' in nombre:
                    return nombre

        # Si no, cualquiera que sea Gemini
        for m in modelos:
            nombre = m['name']
            if 'generateContent' in m['supportedGenerationMethods'] and 'gemini' in nombre:
                return nombre
                
        return None
    except Exception as e:
        print(f"⚠️ Error de red al descubrir modelos: {e}")
        return None

def generar_noticia(modelo_completo, prompt):
    """Usa el nombre exacto del modelo descubierto."""
    # El modelo_completo ya viene como 'models/gemini-1.5-pro', así que ajustamos la URL
    # La URL base espera: .../v1beta/models/gemini-1.5-pro:generateContent
    # Si 'modelo_completo' ya tiene 'models/', no lo repetimos en la f-string si la logica lo requiere.
    
    # La API endpoint es: https://generativelanguage.googleapis.com/v1beta/{NAME}:generateContent
    url = f"https://generativelanguage.googleapis.com/v1beta/{modelo_completo}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    
    try:
        print(f"🚀 Enviando petición a: {modelo_completo}...")
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Falló generación ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ Error crítico: {e}")
        return None

def main():
    # 1. Obtener clima
    print(f"Obteniendo clima para {TARGET_CITY}...")
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    curr = data['current']
    day = data['daily']['data'][0]['all_day']

    estado_es = traducir_estado(curr['summary'])

    # 2. Descubrir y Redactar
    print("Iniciando proceso de IA...")
    nombre_modelo = descubrir_mejor_modelo()
    
    texto_ia = None
    if nombre_modelo:
        prompt = f"""
        Actúa como Periodista Senior de Neuquén. Escribe una NOTICIA EXTENSA (SEO) sobre el clima.
        
        DATOS:
        - Estado: {estado_es}
        - Temp: {curr['temperature']}°C
        - Mín: {day['temperature_min']}°C | Máx: {day['temperature_max']}°C
        - Viento: {curr['wind']['speed']} km/h

        REQUISITOS (HTML):
        1. Escribe 4 PÁRRAFOS LARGOS Y DETALLADOS.
        2. Tono serio, informativo y de servicio.
        3. Analiza el impacto del viento.
        4. Usa <h3> para subtítulos y <strong> para datos.
        5. IDIOMA: Español.
        """
        texto_ia = generar_noticia(nombre_modelo, prompt)
    else:
        print("❌ No se encontraron modelos disponibles en tu cuenta.")

    # Fallback si todo falla
    if not texto_ia:
        texto_ia = f"""
        <h3>Reporte Meteorológico {TARGET_CITY}</h3>
        <p>Condiciones actuales: <strong>{estado_es}</strong> con <strong>{curr['temperature']}°C</strong>.</p>
        <p>Se espera una máxima de {day['temperature_max']}°C y vientos de {curr['wind']['speed']} km/h.</p>
        <p><em>Nota: Sistema de redacción en mantenimiento.</em></p>
        """

    # 3. Procesamiento de texto
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    titulo = lineas[0].replace('<h1>', '').replace('</h1>', '').replace('#', '').strip()
    
    if len(titulo) > 100 or "<" in titulo: 
        titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
        cuerpo = texto_limpio
    else:
        cuerpo = "\n".join(lineas[1:])

    # 4. HTML Final
    color_bg = "#e67e22" if curr['temperature'] > 26 else "#2980b9"
    
    html_final = f"""
    <div style="font-family: 'Georgia', serif; font-size: 18px; color: #333; line-height: 1.6;">
        <div style="background: {color_bg}; color: white; padding: 40px; border-radius: 12px; text-align: center; margin-bottom: 30px;">
            <p style="text-transform: uppercase; font-size: 14px; letter-spacing: 2px; margin:0; opacity:0.9; font-family: sans-serif;">Reporte Oficial</p>
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
    </div>
    """

    # 5. Publicar
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post_data = {'title': titulo, 'content': html_final, 'status': 'draft'}
    
    res = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post_data, auth=auth)
    
    if res.status_code == 201:
        print("✅ ÉXITO: Nota publicada.")
    else:
        print(f"❌ Error WP: {res.text}")

if __name__ == "__main__":
    main()

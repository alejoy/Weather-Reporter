import os
import requests
import unicodedata
import json

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
TARGET_CITY = os.environ.get("TARGET_CITY", "Neuquen")

# Diccionario para traducir estados del clima (para la placa)
TRADUCCIONES = {
    "sunny": "Soleado", "mostly sunny": "Mayormente Soleado", "partly sunny": "Parcialmente Soleado",
    "mostly cloudy": "Mayormente Nublado", "cloudy": "Nublado", "overcast": "Cubierto",
    "rain": "Lluvia", "light rain": "Lluvia Débil", "heavy rain": "Lluvia Intensa",
    "snow": "Nieve", "thunderstorm": "Tormenta", "clear": "Despejado", "fog": "Niebla", "mist": "Neblina"
}

def traducir_estado(texto):
    return TRADUCCIONES.get(texto.lower().strip(), texto).upper()

def normalizar_ciudad(texto):
    texto = texto.lower()
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

# --- LÓGICA DE AUTO-DESCUBRIMIENTO DE MODELO ---
def obtener_mejor_modelo():
    """Consulta a la API qué modelos están habilitados para tu clave."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"⚠️ Error al listar modelos: {response.text}")
            return "gemini-1.5-flash" # Fallback seguro

        modelos = response.json().get('models', [])
        print(f"🔎 Analizando {len(modelos)} modelos disponibles...")

        # Buscamos el mejor modelo en orden de prioridad
        preferidos = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro']
        
        for pref in preferidos:
            for m in modelos:
                # Verificamos si el nombre contiene el modelo preferido y soporta generación de contenido
                if pref in m['name'] and 'generateContent' in m['supportedGenerationMethods']:
                    nombre_real = m['name'].split('/')[-1] # Limpiamos 'models/'
                    print(f"✅ Modelo seleccionado: {nombre_real}")
                    return nombre_real
        
        # Si no encuentra coincidencia exacta, toma el primero que sea 'gemini'
        for m in modelos:
             if 'generateContent' in m['supportedGenerationMethods'] and 'gemini' in m['name']:
                 return m['name'].split('/')[-1]

        return "gemini-1.5-flash" # Si no encuentra ninguno preferido
    except Exception as e:
        print(f"⚠️ Error de red: {e}")
        return "gemini-1.5-flash"

def generar_noticia_rest(prompt):
    # 1. Descubrimos el nombre correcto
    modelo = obtener_mejor_modelo()
    
    # 2. Hacemos la petición directa
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ Error IA ({res.status_code}): {res.text}")
            return None
    except Exception as e:
        print(f"⚠️ Excepción IA: {e}")
        return None

def main():
    print(f"--- INICIANDO REPORTE PARA {TARGET_CITY} ---")
    
    # 1. Clima
    city_id = normalizar_ciudad(TARGET_CITY)
    url_w = f"https://www.meteosource.com/api/v1/free/point?place_id={city_id}&sections=current,daily&key={METEOSOURCE_API_KEY}&units=metric"
    res_w = requests.get(url_w)
    res_w.raise_for_status()
    data = res_w.json()
    
    curr = data['current']
    day = data['daily']['data'][0]['all_day']
    estado_es = traducir_estado(curr['summary'])

    # 2. Redacción
    prompt = f"""
    Actúa como Periodista de Neuquén. Escribe una NOTICIA SEO DETALLADA.
    DATOS: Ciudad {TARGET_CITY}, Estado {estado_es}, Temp {curr['temperature']}°C, Viento {curr['wind']['speed']} km/h.
    
    REQUISITOS (HTML):
    - Título H1 impactante.
    - 4 párrafos de análisis.
    - Usa <h3> para subtítulos.
    - IDIOMA: Español.
    """
    
    texto_ia = generar_noticia_rest(prompt)

    # Fallback
    if not texto_ia:
        texto_ia = f"<h3>Reporte {TARGET_CITY}</h3><p>Condiciones actuales: {estado_es}, {curr['temperature']}°C.</p>"

    # 3. Limpieza y HTML Final
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    lineas = texto_limpio.split('\n')
    
    # Extraer título si la IA lo puso
    titulo = f"Pronóstico {TARGET_CITY}: {estado_es} y {curr['temperature']}°C"
    cuerpo = texto_limpio
    
    # Intento simple de extraer título si viene en la primera línea
    if len(lineas) > 0 and ("<h1>" in lineas[0] or "#" in lineas[0] or len(lineas[0]) < 100):
         titulo_posible = lineas[0].replace('<h1>','').replace('</h1>','').replace('#','').replace('*','').strip()
         if len(titulo_posible) > 5: # Validar que no sea vacío
            titulo = titulo_posible
            cuerpo = "\n".join(lineas[1:])

    color_bg = "#e67e22" if curr['temperature'] > 26 else "#2980b9"
    
    html_post = f"""
    <div style="font-family:'Georgia',serif; font-size:18px; line-height:1.6; color:#333;">
        <div style="background:{color_bg}; color:white; padding:30px; border-radius:10px; text-align:center; margin-bottom:20px;">
            <p style="text-transform:uppercase; font-size:14px; opacity:0.8; margin:0; font-family:sans-serif;">Reporte del Tiempo</p>
            <h2 style="font-size:80px; margin:5px 0; font-weight:700; font-family:sans-serif;">{curr['temperature']}°C</h2>
            <p style="font-size:24px; font-weight:600; text-transform:uppercase; margin:0; font-family:sans-serif;">{estado_es}</p>
            <div style="margin-top:20px; border-top:1px solid rgba(255,255,255,0.3); padding-top:15px; display:flex; justify-content:center; gap:20px;">
                <span>Min: <b>{day['temperature_min']}°</b></span>
                <span>Viento: <b>{curr['wind']['speed']} km/h</b></span>
                <span>Max: <b>{day['temperature_max']}°</b></span>
            </div>
        </div>
        <div style="background:#fff; padding:10px;">{cuerpo}</div>
    </div>
    """

    # 4. Publicar
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_post, 'status': 'draft'}
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

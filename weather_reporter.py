import os
import requests
import json
import time
from datetime import datetime
import re
import markdown

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# --- 1. DATOS CLIMÁTICOS ---
def obtener_clima_neuquen():
    url = "https://www.meteosource.com/api/v1/free/point"
    params = {
        "place_id": "neuquen", "sections": "current,daily",
        "language": "en", "units": "metric", "key": METEOSOURCE_API_KEY
    }
    
    try:
        print("👉 Consultando Meteosource...", end=" ")
        res = requests.get(url, params=params)
        data = res.json()

        if 'daily' not in data or 'data' not in data['daily']: return None

        current = data.get('current', {})
        daily = data['daily']['data'][0]
        all_day = daily.get('all_day', {})
        
        # Datos básicos
        temp_actual = current.get('temperature', 0)
        temp_min = all_day.get('temperature_min', 0)
        temp_max = all_day.get('temperature_max', 0)
        
        # Viento
        wind_data = all_day.get('wind', {})
        viento_speed = wind_data.get('speed', 0)
        viento_gusts = wind_data.get('gusts', current.get('wind', {}).get('gusts', viento_speed))

        # Lluvia
        precip_data = all_day.get('precipitation', {})
        lluvia_total = precip_data.get('total', 0)
        lluvia_prob = precip_data.get('probability', 0)
        
        # Estado del cielo (En inglés)
        resumen_en = daily.get('summary', 'Cloudy')
        
        # Diccionario simple para traducir búsqueda de imagen
        traduccion_clima = {
            "Sunny": "dia soleado despejado", "Cloudy": "nublado", "Rain": "lluvia", 
            "Storm": "tormenta electrica", "Windy": "viento fuerte polvo", "Snow": "nieve",
            "Partly cloudy": "parcialmente nublado", "Clear": "cielo despejado"
        }
        # Buscamos la traducción o usamos el original si no está
        condicion_busqueda = next((v for k, v in traduccion_clima.items() if k in resumen_en), "clima")

        # Alertas e Índice UV (Si la API no da UV, simulamos según clima)
        uv_index = current.get('uv_index', 0) # A veces viene en current
        
        alerta_nivel = ""
        fenomenos = []
        if viento_gusts > 70:
            alerta_nivel = "Naranja"
            fenomenos.append(f"Viento extremo ({viento_gusts} km/h)")
        elif lluvia_total > 15:
            alerta_nivel = "Amarilla"
            fenomenos.append(f"Lluvia intensa ({lluvia_total}mm)")
        elif temp_max > 35:
            alerta_nivel = "Amarilla"
            fenomenos.append("Ola de calor")

        return {
            "temp_actual": temp_actual, "temp_min": temp_min, "temp_max": temp_max,
            "viento_promedio": viento_speed, "viento_rafagas": viento_gusts,
            "resumen_cielo": resumen_en, "lluvia_prob": lluvia_prob,
            "uv_index": uv_index, "alerta": alerta_nivel, 
            "fenomenos_alerta": ", ".join(fenomenos),
            "condicion_busqueda": condicion_busqueda
        }

    except Exception as e:
        print(f"❌ Error API: {e}")
        return None

# --- 2. FECHA ---
def obtener_fecha_formato():
    dias = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    meses = {'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril', 'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'}
    now = datetime.now()
    return f"{dias.get(now.strftime('%A'))} {now.day} de {meses.get(now.strftime('%B'))}"

# --- 3. IMAGEN ---
def buscar_imagen_clima(condicion_texto):
    # Buscamos algo visualmente atractivo: "Paisaje Neuquen dia soleado"
    query = f"Paisaje Neuquen {condicion_texto} ciudad"
    print(f"👉 Buscando imagen: {query}...", end=" ")
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "searchType": "image", "imgSize": "large", "num": 4, "safe": "active"}
        res = requests.get(url, params=params)
        data = res.json()
        if "items" in data:
            # Filtramos Facebook/Instagram para evitar enlaces rotos
            for item in data["items"]:
                if "facebook" not in item["displayLink"] and "instagram" not in item["displayLink"]:
                    print("✅")
                    return item["link"]
    except: pass
    return None

def subir_imagen_wordpress(img_url):
    if not img_url: return None
    try:
        res_img = requests.get(img_url)
        if res_img.status_code == 200:
            filename = f"clima-{int(time.time())}.jpg"
            url_up = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
            headers = {"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"}
            auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
            res_wp = requests.post(url_up, headers=headers, data=res_img.content, auth=auth)
            if res_wp.status_code == 201: return res_wp.json()['id']
    except: pass
    return None

# --- 4. REDACCIÓN CON TIPS ---
def generar_pronostico_ia(datos_clima, fecha_hoy):
    input_json = {
        "ubicacion": "Neuquén Capital",
        "fecha": fecha_hoy,
        "temp_min": f"{datos_clima['temp_min']}°C",
        "temp_max": f"{datos_clima['temp_max']}°C",
        "viento": f"Ráfagas de {datos_clima['viento_rafagas']} km/h",
        "alerta": datos_clima['alerta'],
        "uv_index": datos_clima['uv_index'], # Pasamos el índice UV si existe
        "cielo": datos_clima['resumen_cielo']
    }
    input_str = json.dumps(input_json, ensure_ascii=False, indent=2)

    prompt = f"""
    ROL: Redactor de Clima del Diario "Redacción Servicios".
    
    DATOS DEL DÍA:
    {input_str}

    ESTRUCTURA OBLIGATORIA (Usa Markdown):
    
    1. TÍTULO (#): Impactante. Si hay alerta, inclúyela.
       Ej: "Alerta en Neuquén: ráfagas de 80 km/h y polvo en suspensión".
       Ej: "Domingo ideal: 28°C y sol pleno en el Alto Valle".
    
    2. BAJADA: Resumen corto citando al SMN.
    
    3. DESARROLLO (## Subtítulos):
       - "## Temperaturas": Mínima y máxima.
       - "## Viento y Cielo": Detalles del viento.
    
    4. RECOMENDACIONES (## Tips para hoy): <--- ESTO ES IMPORTANTE
       Genera 3 consejos prácticos basados en los datos:
       - Si temp_max > 30 o UV alto: "Usar protector solar factor 50", "Hidratarse", "Evitar sol directo al mediodía".
       - Si hay viento fuerte: "No dejar macetas sueltas en balcones", "Precaución al manejar en ruta".
       - Si hace frío: "Salir abrigado por capas".
       - Si llueve: "Salir con paraguas", "Manejar despacio".

    FORMATO:
    - Usa negritas (**texto**) para datos duros.
    - Tono de servicio y utilidad.
    - Idioma: Español Argentino.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    try:
        print("🤖 Generando nota con tips...", end=" ")
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return None

# --- MAIN ---
def main():
    fecha_hoy = obtener_fecha_formato()
    print(f"--- CLIMA CON TIPS: {fecha_hoy} ---")
    
    datos = obtener_clima_neuquen()
    if not datos: return

    # Generamos Texto (Markdown)
    texto_md = generar_pronostico_ia(datos, fecha_hoy)
    if not texto_md: return

    # Limpieza
    texto_md = texto_md.replace('```markdown', '').replace('```', '').strip()
    
    # Separamos Título
    if texto_md.startswith('#'):
        partes = texto_md.split('\n', 1)
        titulo = partes[0].replace('#', '').strip()
        cuerpo_md = partes[1].strip() if len(partes) > 1 else ""
    else:
        titulo = f"Pronóstico: {fecha_hoy}"
        cuerpo_md = texto_md

    # Convertimos a HTML (Soluciona el problema de negritas)
    cuerpo_html = markdown.markdown(cuerpo_md)

    # Imagen
    img_url = buscar_imagen_clima(datos['condicion_busqueda'])
    media_id = subir_imagen_wordpress(img_url)

    # HTML Final
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        {cuerpo_html}
        <hr>
        <div style="background: #eef9fd; padding: 15px; border-left: 5px solid #2980b9; font-size: 16px;">
            ℹ️ <strong>Fuente:</strong> Servicio Meteorológico Nacional y AIC.
        </div>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_final, 'status': 'draft', 'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id}
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    if r.status_code == 201: print("✅ Nota publicada con éxito.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

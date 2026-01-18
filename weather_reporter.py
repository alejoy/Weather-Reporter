import os
import requests
import json
import time
from datetime import datetime
import re

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# --- 1. DATOS CLIMÁTICOS (Corrección de Estructura) ---
def obtener_clima_neuquen():
    """Consulta la API de Meteosource con extracción segura de datos."""
    url = "https://www.meteosource.com/api/v1/free/point"
    params = {
        "place_id": "neuquen",
        "sections": "current,daily",
        "language": "en",
        "units": "metric",
        "key": METEOSOURCE_API_KEY
    }
    
    try:
        print("👉 Consultando Meteosource...", end=" ")
        res = requests.get(url, params=params)
        data = res.json()
        
        # Validación básica
        if 'daily' not in data or 'data' not in data['daily']:
            print("❌ Estructura de API desconocida.")
            return None

        current = data.get('current', {})
        daily = data['daily']['data'][0] # Pronóstico de hoy
        all_day = daily.get('all_day', {})
        
        # --- EXTRACCIÓN SEGURA (Evita el KeyError 'wind') ---
        # Temperaturas
        temp_actual = current.get('temperature', 0)
        temp_min = all_day.get('temperature_min', 0)
        temp_max = all_day.get('temperature_max', 0)
        
        # Viento (Aquí estaba el error: accedemos seguro dentro de all_day)
        wind_data = all_day.get('wind', {})
        viento_speed = wind_data.get('speed', 0)
        # Si no hay ráfagas en el daily, usamos las del current o estimamos
        viento_gusts = wind_data.get('gusts', current.get('wind', {}).get('gusts', viento_speed))

        # Lluvia
        precip_data = all_day.get('precipitation', {})
        lluvia_total = precip_data.get('total', 0)
        lluvia_prob = precip_data.get('probability', 0)
        
        # Cielo
        resumen_cielo = daily.get('summary', 'Algo nublado')

        # --- DETECCIÓN DE ALERTAS ---
        alerta_nivel = ""
        fenomenos = []
        
        if viento_gusts > 70:
            alerta_nivel = "Amarilla/Naranja"
            fenomenos.append(f"Viento fuerte ({viento_gusts} km/h)")
        elif lluvia_total > 15:
            alerta_nivel = "Amarilla"
            fenomenos.append(f"Lluvia intensa ({lluvia_total}mm)")
        elif temp_max > 38:
            alerta_nivel = "Naranja"
            fenomenos.append("Ola de calor extrema")

        datos_finales = {
            "temp_actual": temp_actual,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "viento_promedio": viento_speed,
            "viento_rafagas": viento_gusts,
            "resumen_cielo": resumen_cielo,
            "lluvia_prob": lluvia_prob,
            "alerta": alerta_nivel,
            "fenomenos_alerta": ", ".join(fenomenos)
        }
        print("✅ Datos obtenidos correctamente.")
        return datos_finales

    except Exception as e:
        print(f"❌ Error API Clima Genérico: {e}")
        return None

# --- 2. FECHA ---
def obtener_fecha_formato():
    dias = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    meses = {'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril', 'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'}
    now = datetime.now()
    return f"{dias.get(now.strftime('%A'))} {now.day} de {meses.get(now.strftime('%B'))}"

# --- 3. IMAGEN ---
def buscar_imagen_clima(condicion):
    query = f"Clima Neuquen {condicion} paisaje"
    print(f"👉 Buscando imagen para: {query}...", end=" ")
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "searchType": "image", "imgSize": "large", "num": 3, "safe": "active"}
        res = requests.get(url, params=params)
        if "items" in res.json():
            print("✅")
            return res.json()["items"][0]["link"]
    except: pass
    print("❌")
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

# --- 4. REDACCIÓN (Prompt Ajustado) ---
def generar_pronostico_ia(datos_clima, fecha_hoy):
    input_json = {
        "ubicacion": "Neuquén Capital y Alto Valle",
        "fecha": fecha_hoy,
        "temp_min": f"{datos_clima['temp_min']}°C",
        "temp_max": f"{datos_clima['temp_max']}°C",
        "cielo": datos_clima['resumen_cielo'],
        "viento": f"Promedio {datos_clima['viento_promedio']} km/h, Ráfagas {datos_clima['viento_rafagas']} km/h",
        "alerta": datos_clima['alerta'],
        "fenomenos_alerta": datos_clima['fenomenos_alerta'],
        "contexto_temporal": "hoy"
    }
    input_str = json.dumps(input_json, ensure_ascii=False, indent=2)

    prompt = f"""
    ROL: Actúa como un Generador de Notas de Clima (GEMS) para un diario digital.

    INPUT DE DATOS REALES:
    <input_usuario>
    {input_str}
    </input_usuario>

    REGLAS DE ESTILO OBLIGATORIAS:
    1. TÍTULO (#):
       - Estructura: [Fenómeno Principal] en [Lugar]: [Dato Duro], [Pregunta de enganche].
       - Ejemplo: "Calor extremo en Neuquén: 38°C de máxima, ¿cuándo llega el alivio?"
       - Si el campo "alerta" tiene datos, LA ALERTA DEBE ESTAR EN EL TÍTULO.

    2. BAJADA:
       - Cita siempre al "Servicio Meteorológico Nacional (SMN)" o "AIC".
       - Cierre: "Mirá el detalle del pronóstico."

    3. CUERPO:
       - Usa negritas para temperaturas y vientos (ej: **35°C**, **ráfagas de 60 km/h**).
       - Párrafos cortos.
       - Usa subtítulos (##) con preguntas (ej: ## ¿Cómo estará la tarde?).

    4. IDIOMA: Español Argentino Neutro.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    try:
        print("🤖 Generando texto...", end=" ")
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"❌ Error IA: {res.status_code}")
            return None
    except: return None

# --- MAIN ---
def main():
    fecha_hoy = obtener_fecha_formato()
    print(f"--- REPORTE CLIMA: {fecha_hoy} ---")
    
    datos = obtener_clima_neuquen()
    if not datos: return

    texto_nota = generar_pronostico_ia(datos, fecha_hoy)
    if not texto_nota: return

    # Limpieza
    texto_nota = texto_nota.replace('```markdown', '').replace('```', '').strip()
    if texto_nota.startswith('#'):
        # Separar título del cuerpo
        partes = texto_nota.split('\n', 1)
        titulo = partes[0].replace('#', '').strip()
        cuerpo = partes[1].strip() if len(partes) > 1 else ""
    else:
        titulo = f"Clima: {fecha_hoy}"
        cuerpo = texto_nota

    # Imagen
    img_url = buscar_imagen_clima(datos['resumen_cielo'])
    media_id = subir_imagen_wordpress(img_url)

    # HTML Final
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        {cuerpo}
        <hr>
        <p style="font-size:14px; color:#777;">⚠️ <em>Fuente: Datos automáticos. Consultar fuentes oficiales ante alertas.</em></p>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_final, 'status': 'draft', 'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id}
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    if r.status_code == 201: print("✅ Nota publicada.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

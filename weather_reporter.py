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

# --- 1. DATOS CLIMÁTICOS (Meteosource) ---
def obtener_clima_neuquen():
    """Consulta la API de Meteosource para Neuquén Capital."""
    url = "https://www.meteosource.com/api/v1/free/point"
    params = {
        "place_id": "neuquen",
        "sections": "current,daily",
        "language": "en", # La API free suele ser mejor en inglés, luego traducimos
        "units": "metric",
        "key": METEOSOURCE_API_KEY
    }
    
    try:
        print("👉 Consultando Meteosource...", end=" ")
        res = requests.get(url, params=params)
        data = res.json()
        
        current = data['current']
        daily = data['daily']['data'][0] # El pronóstico de hoy
        
        # Detectar alertas básicas (Meteosource Free no da alertas complejas, inferimos por intensidad)
        alerta_nivel = ""
        fenomenos = []
        
        if daily['wind']['gusts'] > 70:
            alerta_nivel = "Amarilla/Naranja"
            fenomenos.append(f"Viento extremo ({daily['wind']['gusts']} km/h)")
        elif daily['all_day']['precipitation']['total'] > 15:
            alerta_nivel = "Amarilla"
            fenomenos.append("Lluvia intensa")
        
        datos = {
            "temp_actual": current['temperature'],
            "temp_min": daily['all_day']['temperature_min'],
            "temp_max": daily['all_day']['temperature_max'],
            "viento_promedio": daily['all_day']['wind']['speed'],
            "viento_rafagas": daily['wind']['gusts'],
            "resumen_cielo": daily['summary'], # Ej: "Sunny", "Cloudy"
            "lluvia_prob": daily['all_day']['precipitation']['probability'],
            "alerta": alerta_nivel,
            "fenomenos_alerta": ", ".join(fenomenos)
        }
        print("✅ Datos obtenidos.")
        return datos
    except Exception as e:
        print(f"❌ Error API Clima: {e}")
        return None

# --- 2. FECHA EN ESPAÑOL ---
def obtener_fecha_formato():
    dias = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    meses = {'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril', 'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'}
    
    now = datetime.now()
    dia_str = dias.get(now.strftime("%A"), "")
    mes_str = meses.get(now.strftime("%B"), "")
    return f"{dia_str} {now.day} de {mes_str}"

# --- 3. IMAGEN DEL CLIMA (Google Search) ---
def buscar_imagen_clima(condicion):
    """Busca una imagen que represente el clima de hoy (Ej: Lluvia Neuquen)."""
    query = f"Clima Neuquen {condicion} paisaje"
    print(f"👉 Buscando imagen para: {query}...", end=" ")
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "searchType": "image", "imgSize": "large", "num": 3, "safe": "active"}
        
        res = requests.get(url, params=params)
        data = res.json()
        
        if "items" in data:
            # Filtro simple de dominios malos
            for item in data["items"]:
                if "facebook" not in item["displayLink"] and "instagram" not in item["displayLink"]:
                    print("✅ Encontrada.")
                    return item["link"]
    except: pass
    print("❌ No encontrada (usando default).")
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

# --- 4. CEREBRO IA (Tu Prompt Nuevo) ---
def generar_pronostico_ia(datos_clima, fecha_hoy):
    
    # Preparamos el JSON de entrada exactamente como lo pide tu prompt
    input_json = {
        "ubicacion": "Neuquén y Alto Valle",
        "fecha": fecha_hoy,
        "temp_min": f"{datos_clima['temp_min']}°C",
        "temp_max": f"{datos_clima['temp_max']}°C",
        "cielo": datos_clima['resumen'], # Gemini traducirá "Cloudy" a español por contexto
        "viento": f"Promedio {datos_clima['viento_promedio']} km/h, Ráfagas {datos_clima['viento_rafagas']} km/h",
        "alerta": datos_clima['alerta'],
        "fenomenos_alerta": datos_clima['fenomenos_alerta'],
        "contexto_temporal": "hoy"
    }
    
    input_str = json.dumps(input_json, ensure_ascii=False, indent=2)

    prompt = f"""
    ROL:
    Actúa como un Generador de Notas de Clima (GEMS) de la redacción de un Diario.

    REGLAS DE ESTILO
    1. TÍTULOS (#):
       - Estructura: [Fenómeno] en [Lugar]: [Dato clave], [Pregunta de enganche].
       - Ejemplo: "Tormenta en el Alto Valle: ráfagas de 90 km/h, ¿a qué hora llega la lluvia?"
       - Si hay ALERTA, debe figurar en el título.

    2. BAJADA:
       - Menciona siempre al "Servicio Meteorológico Nacional (SMN)".
       - Cierra con la invitación: "Mirá el detalle del pronóstico." o similar.

    3. CUERPO Y TONO:
       - Párrafos cortos de máximo 60 palabras.
       - Si hay ALERTAS, cita frases textuales técnicas del SMN (ej: "abundante caída de agua").
       - Subtítulos (##): Usa preguntas directas cuando sea relevante (ej: ## ¿Cuándo para la lluvia?).
       - Usa negritas (texto) para temperaturas y datos duros.

    4. ADAPTACIÓN TEMPORAL:
       - "hoy": Redacta para toda la jornada.

    -------------------------------------------------------------------------
    FEW-SHOT EXAMPLES (REFERENCIA)
    -------------------------------------------------------------------------
    [Aquí la IA ya tiene interiorizados tus ejemplos 1 y 2 por instrucción interna]

    -------------------------------------------------------------------------
    TU TAREA ACTUAL:
    Genera la nota basada en este INPUT REAL:
    <input_usuario>
    {input_str}
    </input_usuario>
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        print("🤖 Generando texto con Gemini...", end=" ")
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"❌ Error {res.status_code}: {res.text}")
            return None
    except Exception as e:
        print(f"⚠️ Error IA: {e}")
        return None

# --- MAIN ---
def main():
    fecha_hoy = obtener_fecha_formato()
    print(f"--- REPORTE CLIMA: {fecha_hoy} ---")
    
    # 1. Obtener Datos
    datos = obtener_clima_neuquen()
    if not datos: return

    # 2. Generar Texto
    texto_nota = generar_pronostico_ia(datos, fecha_hoy)
    if not texto_nota: return

    # 3. Limpieza y Formato
    texto_nota = texto_nota.replace('```markdown', '').replace('```', '').strip()
    
    # Extraer Título (Busca el primer #)
    titulo_match = re.search(r'^#\s*(.+)$', texto_nota, re.MULTILINE)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        # Borramos el título del cuerpo para no duplicarlo
        cuerpo = texto_nota.replace(titulo_match.group(0), '', 1).strip()
    else:
        titulo = f"El tiempo en Neuquén: {fecha_hoy}"
        cuerpo = texto_nota

    # 4. Imagen
    img_url = buscar_imagen_clima(datos['resumen_cielo'])
    media_id = subir_imagen_wordpress(img_url)

    # 5. Publicar
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        {cuerpo}
        <hr>
        <p style="font-size:14px; color:#777;">⚠️ <em>Fuente: Datos procesados automáticamante via API.</em></p>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 'content': html_final, 'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id
    }
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    if r.status_code == 201: print("✅ Nota del clima publicada.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

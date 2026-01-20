import os
import requests
import json
import time
from datetime import datetime
import re
import markdown

# --- CONFIGURACIÓN ---
# Ya no necesitamos METEOSOURCE_API_KEY
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# --- 1. CONEXIÓN AL SMN (La Fuente de la Verdad) ---

def obtener_datos_smn():
    """
    Obtiene datos directamente de los webservices del SMN Argentina.
    Retorna un diccionario con el estado actual y, lo más importante, LAS ALERTAS REALES.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    datos_finales = {
        "estado": None,
        "pronostico": [],
        "alertas": []
    }

    print("🇦🇷 Consultando Servicio Meteorológico Nacional...")

    # A) ESTADO ACTUAL (Estación Neuquén Aero)
    try:
        res = requests.get("https://ws.smn.gob.ar/map_items/weather", headers=headers, timeout=10)
        estaciones = res.json()
        # Buscamos la estación de Neuquén
        estacion_nqn = next((e for e in estaciones if "Neuquén" in e['name']), None)
        
        if estacion_nqn:
            w = estacion_nqn['weather']
            datos_finales["estado"] = {
                "temp": f"{w['temp']}°C",
                "humedad": f"{w['humidity']}%",
                "cielo": w['description'], # Ej: "Cielo despejado"
                "viento": f"del {w['wing_deg']} a {w['wind_speed']} km/h"
            }
            print(f"✅ Estado actual: {datos_finales['estado']['temp']} - {datos_finales['estado']['cielo']}")
    except Exception as e:
        print(f"⚠️ Error obteniendo estado: {e}")

    # B) PRONÓSTICO (1 día)
    try:
        res = requests.get("https://ws.smn.gob.ar/map_items/forecast/1", headers=headers, timeout=10)
        pronosticos = res.json()
        # Buscamos pronóstico para Neuquén
        pro_nqn = next((p for p in pronosticos if "Neuquén" in p['name']), None)
        
        if pro_nqn:
            # El SMN da pronóstico a la mañana (morning) y tarde/noche (afternoon)
            m = pro_nqn['weather']['morning']
            a = pro_nqn['weather']['afternoon']
            
            datos_finales["pronostico"] = {
                "manana": {
                    "temp": f"{m['temp']}°C",
                    "cielo": m['description'],
                    "viento": f"{m['wind_dir']} ({m['wind_speed']} km/h)"
                },
                "tarde": {
                    "temp": f"{a['temp']}°C",
                    "cielo": a['description'],
                    "viento": f"{a['wind_dir']} ({a['wind_speed']} km/h)"
                },
                "temp_min": f"{pro_nqn['weather']['min_temp']}°C",
                "temp_max": f"{pro_nqn['weather']['max_temp']}°C"
            }
            print("✅ Pronóstico obtenido.")
    except Exception as e:
        print(f"⚠️ Error obteniendo pronóstico: {e}")

    # C) ALERTAS (CRÍTICO: Solo si existen en el sistema oficial)
    try:
        res = requests.get("https://ws.smn.gob.ar/alerts/type/AL", headers=headers, timeout=10)
        todas_alertas = res.json()
        
        # Filtramos alertas que afecten a la zona "Confluencia" o "Neuquén"
        for alerta in todas_alertas:
            zonas_afectadas = [z['name'] for z in alerta['zones'].get('07', [])] # 07 es código de Neuquén? Revisamos texto.
            # Buscamos en el texto de las zonas
            if any("Confluencia" in z or "Neuquén" in z for z in alerta.get('zones', {}).values()): 
                 # En la API del SMN las zonas a veces vienen agrupadas. Buscamos en todo el objeto.
                 pass

            # Método más seguro: Buscar texto "Neuquén" en el título o zonas del JSON
            json_str = json.dumps(alerta, ensure_ascii=False)
            if "Confluencia" in json_str or ("Neuquén" in json_str and "Cordillera" not in json_str): 
                # Excluimos Cordillera si queremos solo Valle, o lo dejamos si cubres toda la provincia.
                # Asumimos cobertura Capital/Valle:
                if "Confluencia" in json_str or "Este de Añelo" in json_str:
                    datos_finales["alertas"].append({
                        "titulo": alerta['title'], # Ej: "Alerta por viento"
                        "nivel": alerta['severity'], # Ej: "Amarilla"
                        "descripcion": alerta['description'] or "Sin detalle"
                    })
        
        if datos_finales["alertas"]:
            print(f"🚨 ALERTA DETECTADA: {datos_finales['alertas'][0]['titulo']}")
        else:
            print("✅ Sin alertas vigentes.")

    except Exception as e:
        print(f"⚠️ Error chequeando alertas: {e}")

    return datos_finales

# --- 2. FECHA Y AUXILIARES ---
def obtener_fecha_formato():
    dias = {'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'}
    meses = {'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril', 'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'}
    now = datetime.now()
    return f"{dias.get(now.strftime('%A'))} {now.day} de {meses.get(now.strftime('%B'))}"

def buscar_imagen_clima(condicion_texto):
    query = f"Paisaje Neuquen {condicion_texto} ciudad"
    print(f"👉 Buscando imagen: {query}...", end=" ")
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "searchType": "image", "imgSize": "large", "num": 4, "safe": "active"}
        res = requests.get(url, params=params)
        data = res.json()
        if "items" in data:
            for item in data["items"]:
                if "facebook" not in item["displayLink"]:
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

# --- 3. REDACCIÓN ESTRICTA (Sin Alucinaciones) ---
def generar_pronostico_ia(datos_smn, fecha_hoy):
    
    # Si no hay alertas en el JSON del SMN, Gemini TIENE PROHIBIDO inventar una.
    alertas_str = json.dumps(datos_smn['alertas'], ensure_ascii=False) if datos_smn['alertas'] else "NO HAY ALERTAS VIGENTES. NO INVENTES NINGUNA."
    
    input_str = json.dumps(datos_smn, ensure_ascii=False, indent=2)

    prompt = f"""
    ROL: Periodista de Clima que redacta ÚNICAMENTE basándose en datos oficiales del SMN Argentina.

    DATOS OFICIALES (FUENTE DE VERDAD):
    <input_usuario>
    {input_str}
    </input_usuario>

    INSTRUCCIONES CRÍTICAS SOBRE ALERTAS:
    1. Revisa el campo "alertas" en el input.
    2. SI ESTÁ VACÍO ("[]"): **ESTÁ PROHIBIDO** usar la palabra "Alerta" en el título o texto. Di "Tiempo bueno", "Estable", "Sin alertas".
    3. SI HAY DATOS: Usa la información exacta (Nivel Amarillo/Naranja, zona afectada).

    ESTRUCTURA DE LA NOTA (Markdown):
    
    1. TÍTULO (#):
       - Si hay alerta: "Alerta [Nivel] en Neuquén: [Fenómeno], recomendaciones".
       - Si NO hay alerta: "Pronóstico en Neuquén: [Temp Max] y [Condición de cielo], ¿cómo sigue la semana?".
    
    2. BAJADA: Resumen citando al Servicio Meteorológico Nacional.
    
    3. CUERPO (## Subtítulos):
       - "## Estado actual": Describe temperatura y sensación.
       - "## Pronóstico para hoy": Mañana y Tarde (Usa los datos del JSON).
       - "## Recomendaciones": 3 tips útiles.
    
    FORMATO:
    - Usa negritas (**texto**) para números.
    - Idioma: Español Argentino.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    try:
        print("🤖 Redactando nota oficial...", end=" ")
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return None

# --- MAIN ---
def main():
    fecha_hoy = obtener_fecha_formato()
    print(f"--- REPORTE OFICIAL SMN: {fecha_hoy} ---")
    
    # 1. Obtener Datos OFICIALES
    datos = obtener_datos_smn()
    
    # Validación mínima
    if not datos['estado'] and not datos['pronostico']:
        print("❌ Error: No se pudo conectar con el SMN.")
        return

    # 2. Generar Texto
    texto_md = generar_pronostico_ia(datos, fecha_hoy)
    if not texto_md: return

    # Limpieza
    texto_md = texto_md.replace('```markdown', '').replace('```', '').strip()
    
    if texto_md.startswith('#'):
        partes = texto_md.split('\n', 1)
        titulo = partes[0].replace('#', '').strip()
        cuerpo_md = partes[1].strip() if len(partes) > 1 else ""
    else:
        titulo = f"Clima: {fecha_hoy}"
        cuerpo_md = texto_md

    cuerpo_html = markdown.markdown(cuerpo_md)

    # 3. Imagen
    condicion_cielo = datos['estado']['cielo'] if datos['estado'] else "neuquen clima"
    img_url = buscar_imagen_clima(condicion_cielo)
    media_id = subir_imagen_wordpress(img_url)

    # 4. Publicar
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        {cuerpo_html}
        <hr>
        <div style="background: #eef9fd; padding: 15px; border-left: 5px solid #2980b9; font-size: 16px;">
            ℹ️ <strong>Fuente Oficial:</strong> <a href="https://www.smn.gob.ar" target="_blank">Servicio Meteorológico Nacional (SMN)</a>.
        </div>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {'title': titulo, 'content': html_final, 'status': 'draft', 'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id}
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    if r.status_code == 201: print("✅ Nota publicada con datos oficiales.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

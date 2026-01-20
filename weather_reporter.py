import os
import requests
import json
import time
from datetime import datetime
import re
import markdown

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# --- 1. DISEÑO VISUAL (CSS + ICONOS) ---
def generar_placa_html(datos, fecha):
    """Genera una tarjeta HTML/CSS moderna según el clima."""
    
    estado = datos['estado']
    if not estado: return ""
    
    # Lógica de Colores e Iconos
    condicion = estado['cielo'].lower()
    es_noche = datetime.now().hour > 20 or datetime.now().hour < 6
    
    # Defaults
    icono = "⛅"
    fondo = "linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)" # Azul cielo
    color_texto = "#fff"
    
    # Personalización según clima
    if "despejado" in condicion or "sol" in condicion:
        if es_noche:
            icono = "🌙"
            fondo = "linear-gradient(135deg, #2c3e50 0%, #3498db 100%)" # Noche azulada
        else:
            icono = "☀️"
            fondo = "linear-gradient(135deg, #f6d365 0%, #fda085 100%)" # Naranja soleado
            color_texto = "#333"
            
    elif "nublado" in condicion or "cubierto" in condicion:
        icono = "☁️"
        fondo = "linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%)" # Gris plomo
        
    elif "lluvia" in condicion or "llovizna" in condicion or "chaparron" in condicion:
        icono = "🌧️"
        fondo = "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)" # Azul lluvia
        
    elif "tormenta" in condicion:
        icono = "⛈️"
        fondo = "linear-gradient(135deg, #434343 0%, #000000 100%)" # Negro tormenta
    
    elif "viento" in condicion:
        icono = "🍃"
        fondo = "linear-gradient(135deg, #D7D2CC 0%, #304352 100%)" # Gris Viento

    # Si hay Alerta, la placa se pone "Picante" (Roja/Naranja)
    alerta_html = ""
    if datos['alertas']:
        fondo = "linear-gradient(135deg, #cb2d3e 0%, #ef473a 100%)" # Rojo Alerta
        icono = "⚠️"
        alerta_msg = datos['alertas'][0]['titulo']
        alerta_html = f"""
        <div style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px; margin-top: 15px; font-weight: bold; font-size: 14px; text-align: center; border: 1px solid rgba(255,255,255,0.4);">
            🚨 {alerta_msg}
        </div>
        """

    # HTML DE LA PLACA
    placa = f"""
    <div style="
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        background: {fondo};
        color: {color_texto};
        border-radius: 20px;
        padding: 25px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        max-width: 500px;
        margin: 0 auto 30px auto;
        position: relative;
        overflow: hidden;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; opacity: 0.9; font-size: 0.9em; margin-bottom: 15px;">
            <span>📍 Neuquén Capital</span>
            <span>📅 {fecha}</span>
        </div>

        <div style="text-align: center; margin: 20px 0;">
            <div style="font-size: 4em; margin-bottom: 10px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.2));">{icono}</div>
            <div style="font-size: 3.5em; font-weight: 800; line-height: 1;">{estado['temp']}</div>
            <div style="font-size: 1.2em; font-weight: 500; margin-top: 5px; text-transform: capitalize; opacity: 0.95;">{estado['cielo']}</div>
        </div>

        <div style="
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 10px; 
            background: rgba(255,255,255,0.15); 
            border-radius: 12px; 
            padding: 15px;
            backdrop-filter: blur(5px);
        ">
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">💨</span>
                <div style="font-size: 0.8em; opacity: 0.8;">Viento</div>
                <div style="font-weight: bold;">{estado['viento_vel']}</div>
            </div>
            <div style="text-align: center;">
                <span style="font-size: 1.2em;">💧</span>
                <div style="font-size: 0.8em; opacity: 0.8;">Humedad</div>
                <div style="font-weight: bold;">{estado['humedad']}</div>
            </div>
        </div>

        {alerta_html}
    </div>
    """
    return placa

# --- 2. CONEXIÓN AL SMN ---
def obtener_datos_smn():
    headers = {'User-Agent': 'Mozilla/5.0'}
    datos_finales = {"estado": None, "pronostico": [], "alertas": []}

    print("🇦🇷 Consultando SMN...")
    
    # A) Estado Actual
    try:
        res = requests.get("https://ws.smn.gob.ar/map_items/weather", headers=headers, timeout=10)
        estaciones = res.json()
        estacion_nqn = next((e for e in estaciones if "Neuquén" in e['name']), None)
        
        if estacion_nqn:
            w = estacion_nqn['weather']
            datos_finales["estado"] = {
                "temp": f"{w['temp']}°C",
                "humedad": f"{w['humidity']}%",
                "cielo": w['description'],
                "viento_vel": f"{w['wind_speed']} km/h",
                "viento_full": f"del {w['wing_deg']} a {w['wind_speed']} km/h"
            }
    except: pass

    # B) Alertas
    try:
        res = requests.get("https://ws.smn.gob.ar/alerts/type/AL", headers=headers, timeout=10)
        todas = res.json()
        for alerta in todas:
            # Búsqueda laxa de "Neuquén" o "Confluencia"
            json_str = json.dumps(alerta, ensure_ascii=False)
            if "Confluencia" in json_str or ("Neuquén" in json_str and "Cordillera" not in json_str):
                 datos_finales["alertas"].append({
                    "titulo": alerta['title'],
                    "nivel": alerta['severity'],
                    "descripcion": alerta['description']
                })
    except: pass
    
    # C) Pronóstico (Texto para la IA)
    try:
        res = requests.get("https://ws.smn.gob.ar/map_items/forecast/1", headers=headers, timeout=10)
        for p in res.json():
            if "Neuquén" in p['name']:
                datos_finales["pronostico"] = p['weather']
                break
    except: pass

    return datos_finales

# --- 3. IMAGEN Y FECHA ---
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

# --- 4. REDACCIÓN IA ---
def generar_pronostico_ia(datos_smn, fecha_hoy):
    alertas_str = json.dumps(datos_smn['alertas'], ensure_ascii=False) if datos_smn['alertas'] else "NO HAY ALERTAS VIGENTES. NO INVENTAR."
    input_str = json.dumps(datos_smn, ensure_ascii=False, indent=2)

    prompt = f"""
    ROL: Periodista de Clima (SMN Oficial).
    
    DATOS OFICIALES:
    <input_usuario>
    {input_str}
    </input_usuario>

    ESTRUCTURA (Markdown):
    1. TÍTULO (#):
       - SI HAY ALERTA: "Alerta [Nivel] en Neuquén: [Fenómeno] y recomendaciones".
       - SI NO: "El tiempo en Neuquén: [Temp] y [Cielo], ¿cómo sigue el día?".
    
    2. BAJADA: Breve resumen. Citar al SMN.
    
    3. CUERPO (## Subtítulos):
       - "## Estado actual": Datos de ahora.
       - "## Pronóstico": Mañana y tarde.
       - "## Recomendaciones": 3 tips útiles basados en el clima (Si hay viento: cuidado al manejar. Si hay sol: protector).

    FORMATO:
    - Negritas (**texto**) para datos duros.
    - Idioma: Español Argentino.
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    try:
        print("🤖 Redactando...", end=" ")
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return None

# --- MAIN ---
def main():
    fecha_hoy = obtener_fecha_formato()
    print(f"--- REPORTE OFICIAL SMN + PLACA: {fecha_hoy} ---")
    
    datos = obtener_datos_smn()
    if not datos['estado']:
        print("❌ Error de datos SMN.")
        return

    # 1. Generar Placa HTML
    placa_html = generar_placa_html(datos, fecha_hoy)
    
    # 2. Generar Texto IA
    texto_md = generar_pronostico_ia(datos, fecha_hoy)
    if not texto_md: return

    # Limpieza y Markdown -> HTML
    texto_md = texto_md.replace('```markdown', '').replace('```', '').strip()
    if texto_md.startswith('#'):
        partes = texto_md.split('\n', 1)
        titulo = partes[0].replace('#', '').strip()
        cuerpo_md = partes[1].strip() if len(partes) > 1 else ""
    else:
        titulo = f"Clima: {fecha_hoy}"
        cuerpo_md = texto_md

    cuerpo_html = markdown.markdown(cuerpo_md)

    # 3. Imagen Destacada (Google)
    img_url = buscar_imagen_clima(datos['estado']['cielo'])
    media_id = subir_imagen_wordpress(img_url)

    # 4. HTML FINAL (Placa + Nota)
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        
        {placa_html}

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
    if r.status_code == 201: print("✅ Nota + Placa publicadas.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

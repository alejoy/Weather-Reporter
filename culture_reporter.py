import os
import requests
import json
import time
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# --- 1. FECHAS Y CALCULADORA ---
def obtener_proximo_finde():
    """Calcula viernes, sábado y domingo próximos."""
    hoy = datetime.now()
    dias_para_viernes = (4 - hoy.weekday() + 7) % 7
    viernes = hoy + timedelta(days=dias_para_viernes)
    sabado = viernes + timedelta(days=1)
    domingo = sabado + timedelta(days=1)
    
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    def fmt(d): return f"{d.day} de {meses[d.month-1]}"
    
    return {
        "viernes": fmt(viernes),
        "sabado": fmt(sabado),
        "domingo": fmt(domingo),
        "short_date": f"{viernes.day}/{viernes.month}",
        "query_date": f"{meses[viernes.month-1]} {viernes.year}"
    }

# --- 2. FUENTES DE INFORMACIÓN ---
def scrapear_web_oficial():
    url = "https://www.neuquencapital.gov.ar/agenda-de-actividades/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    print(f"👉 Leyendo web oficial: {url}...")
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
                tag.decompose()
            texto = soup.get_text(separator=' ').strip()
            # Limpiamos exceso de espacios
            texto = re.sub(r'\s+', ' ', texto)
            return {"contenido": texto[:12000], "url": url} # Aumentamos límite a 12k
    except Exception as e:
        print(f"⚠️ Error scraping oficial: {e}")
    return None

def buscar_eventos_google(fechas):
    print("👉 Buscando eventos complementarios en Google...")
    queries = [
        f"Agenda cultural Neuquén fin de semana {fechas['viernes']}",
        "Cartelera Cine Teatro Español Neuquén horarios",
        "MNBA Neuquén actividades fin de semana",
        "Paseo de la Costa Neuquén eventos hoy"
    ]
    resultados = []
    for q in queries:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"q": q, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "num": 2}
            res = requests.get(url, params=params)
            data = res.json()
            if "items" in data:
                for item in data["items"]:
                    resultados.append(f"- {item['title']} ({item['link']}): {item['snippet']}")
        except: pass
        time.sleep(0.5)
    return resultados

# --- 3. IMÁGENES ---
def buscar_y_subir_imagen(query):
    print(f"👉 Buscando imagen para: {query}...", end=" ")
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        BLACK_LIST = ["instagram", "facebook", "twitter", "pinterest"]
        params = {"q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "searchType": "image", "imgSize": "large", "num": 6, "safe": "active"}
        
        res = requests.get(url, params=params)
        data = res.json()
        
        if "items" not in data: 
            print("❌ No encontrada.")
            return None

        img_url = None
        for item in data["items"]:
            if not any(bl in item["displayLink"] for bl in BLACK_LIST):
                img_url = item["link"]
                break
        
        if not img_url: return None

        print(f"✅ Encontrada. Subiendo a WP...")
        res_img = requests.get(img_url, timeout=10)
        if res_img.status_code == 200:
            filename = f"cultura-{int(time.time())}.jpg"
            url_up = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
            headers = {"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"}
            auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
            res_wp = requests.post(url_up, headers=headers, data=res_img.content, auth=auth)
            if res_wp.status_code == 201: return res_wp.json()['id']
            
    except Exception as e:
        print(f"⚠️ Error imagen: {e}")
    return None

# --- 4. REDACCIÓN ROBUSTA (MULTIMODELO) ---
def llamar_api_gemini(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    # Ajustes de seguridad relajados para evitar bloqueos falsos
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": safety_settings,
        "generationConfig": {"temperature": 0.5}
    }

    try:
        print(f"🤖 Probando redacción con {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if res.status_code == 200:
            data = res.json()
            if 'candidates' in data and data['candidates']:
                print("✅ ÉXITO.")
                return data['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"⚠️ Bloqueo o respuesta vacía: {data.get('promptFeedback', 'Desconocido')}")
        else:
            print(f"❌ Error HTTP {res.status_code}")
    except Exception as e:
        print(f"⚠️ Excepción: {e}")
    return None

def redactar_agenda_seo(info_oficial, info_google, fechas):
    # Prompt optimizado
    texto_oficial = info_oficial['contenido'] if info_oficial else "No disponible."
    link_oficial = info_oficial['url'] if info_oficial else ""
    texto_google = "\n".join(info_google)

    prompt = f"""
    Eres Editor de Cultura en Neuquén. Escribe la AGENDA CULTURAL ({fechas['viernes']} al {fechas['domingo']}).
    
    FUENTES:
    1. MUNICIPALIDAD (Oficial): {link_oficial}
    DATOS: {texto_oficial[:8000]} 
    
    2. WEB:
    {texto_google}

    REGLAS ESTRICTAS:
    - NO INVENTES EVENTOS. Si no hay datos, recomienda: Paseo de la Costa, MNBA (Museo Bellas Artes), Parque Norte.
    - INSERTA ENLACES: Si citas un evento de la Muni, pon <a href="{link_oficial}">Más info aquí</a>.
    - SEO: Título H1 clickbait ético. Estructura H2 y H3 clara.
    - IDIOMA: Español Argentino.
    - FORMATO: HTML limpio (sin ```html).
    """

    # Lista de modelos para probar en orden
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    
    for m in modelos:
        texto = llamar_api_gemini(m, prompt)
        if texto: return texto
        time.sleep(1)
    
    return None

# --- MAIN ---
def main():
    fechas = obtener_proximo_finde()
    print(f"--- AGENDA CULTURAL: {fechas['short_date']} ---")
    
    # 1. Datos
    oficial = scrapear_web_oficial()
    google = buscar_eventos_google(fechas)
    
    # 2. Imagen
    media_id = buscar_y_subir_imagen(f"Agenda Cultural Neuquen {fechas['query_date']}")
    
    # 3. Redacción
    texto_html = redactar_agenda_seo(oficial, google, fechas)
    
    if not texto_html:
        print("❌ ERROR CRÍTICO: Ningún modelo pudo redactar la nota.")
        return

    # 4. Limpieza
    texto_html = texto_html.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    if "<h1>" in texto_html: texto_html = texto_html[texto_html.find("<h1>"):]
    
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto_html, re.IGNORECASE)
    titulo = titulo_match.group(1).strip() if titulo_match else f"Agenda Neuquén: Planes para el finde"
    cuerpo = re.sub(r'<h1>.*?</h1>', '', texto_html, count=1, flags=re.IGNORECASE).strip()

    # 5. Publicar
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333;">
        {cuerpo}
        <hr style="margin: 40px 0; border-top: 1px solid #eee;">
        <div style="background: #f9f9f9; padding: 20px; font-size: 14px; color: #666;">
            <strong>⚠️ Aviso:</strong> Información recopilada de fuentes públicas. Los horarios pueden cambiar. Chequeá los enlaces oficiales.
        </div>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 'content': html_final, 'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id
    }
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    if r.status_code == 201: print("✅ Agenda publicada.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

import os
import requests
import json
import time
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup # Necesario para leer la web oficial

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# --- 1. FECHAS ---
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
        "query_date": f"{meses[viernes.month-1]} {viernes.year}"
    }

# --- 2. FUENTES DE INFORMACIÓN ---

def scrapear_web_oficial():
    """Intenta leer la web de la Muni directamente."""
    url = "https://www.neuquencapital.gov.ar/agenda-de-actividades/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    print(f"👉 Leyendo web oficial: {url}...")
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Eliminamos scripts y estilos para que no confundan a la IA
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()
                
            texto = soup.get_text(separator=' ')
            # Limpieza de espacios extra
            lines = (line.strip() for line in texto.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            texto_limpio = '\n'.join(chunk for chunk in chunks if chunk)
            
            # Cortamos para no saturar a Gemini (primeros 8000 caracteres suelen tener lo importante)
            print("✅ Web oficial leída correctamente.")
            return texto_limpio[:8000]
        else:
            print(f"⚠️ Web oficial devolvió estado {res.status_code}")
    except Exception as e:
        print(f"⚠️ Error leyendo web oficial: {e}")
    
    return ""

def buscar_eventos_google(fechas):
    """Busca en Google Search como respaldo y complemento."""
    url = "https://www.googleapis.com/customsearch/v1"
    
    # Truco: Buscamos específicamente dentro del sitio oficial también
    queries = [
        f"site:neuquencapital.gov.ar/agenda-de-actividades/ eventos {fechas['query_date']}",
        f"Agenda cultural Neuquén fin de semana {fechas['viernes']}",
        "Cartelera Cine Teatro Español Neuquén horarios",
        "MNBA Neuquén muestras actuales"
    ]
    
    resultados = ""
    print("👉 Consultando Google Search API...")
    
    for q in queries:
        params = {"q": q, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "num": 2}
        try:
            res = requests.get(url, params=params)
            data = res.json()
            if "items" in data:
                for item in data["items"]:
                    resultados += f"- {item['title']}: {item['snippet']}\n"
        except: pass

    return resultados

# --- 3. IMAGEN Y SUBIDA ---
def buscar_imagen_cultura():
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": "Teatro Eventos Culturales Neuquen", "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY,
        "searchType": "image", "imgSize": "large", "num": 3, "safe": "active"
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        if "items" in data:
            return {"url": data["items"][0]["link"], "origen": data["items"][0]["displayLink"]}
    except: return None

def subir_imagen_wordpress(img_data):
    if not img_data: return None
    try:
        res_img = requests.get(img_data['url'])
        if res_img.status_code != 200: return None
        
        filename = f"agenda-cultura-{int(time.time())}.jpg"
        url_upload = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
        headers = {"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"}
        auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
        
        res_wp = requests.post(url_upload, headers=headers, data=res_img.content, auth=auth)
        if res_wp.status_code == 201: return res_wp.json()['id']
    except: pass
    return None

# --- 4. REDACCIÓN ---
def redactar_agenda(texto_oficial, resultados_google, fechas):
    prompt = f"""
    Actúa como Periodista de Cultura del diario "Redacción Servicios" de Neuquén.
    Escribe la AGENDA CULTURAL para el fin de semana ({fechas['viernes']} al {fechas['domingo']}).
    
    FUENTE 1 (OFICIAL - PRIORIDAD):
    {texto_oficial}
    
    FUENTE 2 (BÚSQUEDA WEB):
    {resultados_google}
    
    INSTRUCCIONES CLAVE:
    1. Prioriza los eventos encontrados en la Fuente 1 (Web Oficial).
    2. Si hay horarios y precios exactos, ponlos. Si no, pon "Consultar horarios".
    3. Si la información es escasa, completa recomendando clásicos (Paseo de la Costa, MNBA, Parque Norte).
    
    ESTRUCTURA HTML:
    - H1: Título atractivo (Ej: "Agenda NQN: Música, teatro y aire libre para este finde").
    - H2: Bajada resumen.
    - H3: "Viernes", "Sábado", "Domingo" (Divide las actividades por día).
    - H3: "Otras opciones" (Cine, museos).
    - Cierre con recomendación climática breve.
    
    TONO: Entusiasta, útil y preciso.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: return None

# --- MAIN ---
def main():
    fechas = obtener_proximo_finde()
    print(f"--- AGENDA CULTURAL: {fechas['viernes']} ---")
    
    # 1. Obtener Datos
    oficial = scrapear_web_oficial()
    google = buscar_eventos_google(fechas)
    
    if len(oficial) < 50 and len(google) < 50:
        print("⚠️ Poca info encontrada, redactando genérico...")
        oficial = "No hay eventos destacados. Recomendar actividades al aire libre y visitas a museos permanentes."

    # 2. Redactar
    texto_ia = redactar_agenda(oficial, google, fechas)
    if not texto_ia: return

    # 3. Limpieza
    texto_ia = texto_ia.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    if "<h1>" in texto_ia: texto_ia = texto_ia[texto_ia.find("<h1>"):]
    
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto_ia, re.IGNORECASE)
    titulo = titulo_match.group(1).strip() if titulo_match else f"Agenda Finde: {fechas['viernes']}"
    cuerpo = re.sub(r'<h1>.*?</h1>', '', texto_ia, count=1, flags=re.IGNORECASE).strip()

    # 4. Imagen Destacada
    img_data = buscar_imagen_cultura()
    media_id = subir_imagen_wordpress(img_data)

    # 5. Publicar
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333;">
        <div class="contenido-nota">{cuerpo}</div>
        <div style="margin-top: 30px; background: #f0f0f0; padding: 15px; font-size: 14px;">
            ℹ️ <em>Fuente: Municipalidad de Neuquén y relevamiento propio. Sujeto a cambios.</em>
        </div>
    </div>
    """
    
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 'content': html_post, 'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID),
        'featured_media': media_id
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201: print("✅ Agenda publicada.")
    else: print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

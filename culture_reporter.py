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

# --- 1. FECHAS ---
def obtener_proximo_finde():
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

# --- 2. DATOS ---
def scrapear_web_oficial():
    url = "https://www.neuquencapital.gov.ar/agenda-de-actividades/"
    print(f"👉 Leyendo web oficial: {url}...")
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer"]): tag.decompose()
            texto = re.sub(r'\s+', ' ', soup.get_text(separator=' ').strip())
            return {"contenido": texto[:12000], "url": url}
    except: pass
    return None

def buscar_eventos_google(fechas):
    print("👉 Buscando datos extra en Google...")
    queries = [
        f"Agenda cultural Neuquén fin de semana {fechas['viernes']}",
        "Cartelera Cine Teatro Español Neuquén",
        "MNBA Neuquén muestras actuales"
    ]
    resultados = []
    for q in queries:
        try:
            params = {"q": q, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "num": 2}
            res = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
            data = res.json()
            if "items" in data:
                for item in data["items"]:
                    resultados.append(f"- {item['title']} ({item['link']}): {item['snippet']}")
        except: pass
    return resultados

# --- 3. IMÁGENES BLINDADAS (Anti-Starbucks) ---
def buscar_y_subir_imagen_segura():
    # Buscamos términos muy específicos de edificios culturales
    query = "Cine Teatro Español Neuquen Fachada MNBA" 
    print(f"👉 Buscando imagen CULTURAL estricta: {query}...", end=" ")
    
    try:
        params = {
            "q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY,
            "searchType": "image", "imgSize": "large", "num": 8, "safe": "active"
        }
        res = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
        data = res.json()
        
        if "items" not in data: return None

        # FILTROS ESTRICTOS
        KEYWORDS_PERMITIDAS = ["teatro", "museo", "mnba", "centro cultural", "parque", "monumento", "cine", "orquesta", "escenario"]
        KEYWORDS_PROHIBIDAS = ["starbucks", "mc donalds", "café", "restaurante", "menu", "oferta", "burguer", "logo"]
        
        img_url = None
        
        for item in data["items"]:
            titulo = item["title"].lower()
            link_origen = item["displayLink"].lower()
            
            # 1. Chequeo de Lista Negra (Si dice Starbucks, chau)
            if any(bad in titulo for bad in KEYWORDS_PROHIBIDAS):
                continue
            
            # 2. Chequeo de Lista Blanca (Debe decir Teatro, Museo, etc.)
            if any(good in titulo for good in KEYWORDS_PERMITIDAS):
                img_url = item["link"]
                print(f"✅ Imagen Aprobada: {titulo}")
                break # Encontramos la correcta
        
        if not img_url:
            print("⚠️ Ninguna imagen pasó el filtro estricto. Usando imagen por defecto.")
            return None # Devolver None hará que no suba nada (o podríamos poner una URL fija de backup)

        # Subida
        res_img = requests.get(img_url, timeout=10)
        if res_img.status_code == 200:
            filename = f"cultura-nqn-{int(time.time())}.jpg"
            url_up = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
            headers = {"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"}
            auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
            res_wp = requests.post(url_up, headers=headers, data=res_img.content, auth=auth)
            if res_wp.status_code == 201: return res_wp.json()['id']

    except Exception as e:
        print(f"⚠️ Error imagen: {e}")
    return None

# --- 4. REDACCIÓN CON ENLACES DESTACADOS ---
def llamar_api_gemini(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4} # Baja temperatura para ser preciso
    }
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    return None

def redactar_agenda_seo(info_oficial, info_google, fechas):
    texto_oficial = info_oficial['contenido'] if info_oficial else ""
    link_oficial = info_oficial['url'] if info_oficial else ""
    
    prompt = f"""
    Eres Editor de Cultura en Neuquén. Escribe la AGENDA ({fechas['viernes']} al {fechas['domingo']}).
    
    DATOS OFICIALES (Muni): {texto_oficial[:6000]} (Fuente: {link_oficial})
    DATOS EXTRA: {" | ".join(info_google)}

    REGLAS DE FORMATO Y ESTILO:
    1. **ENLACES RESALTADOS**: Cada vez que menciones una fuente o "más info", usa este formato HTML EXACTO: 
       <br>👉 <strong><a href="URL_AQUI" target="_blank">MÁS INFORMACIÓN / CONSULTAR HORARIOS</a></strong><br>
       (Usa el link oficial {link_oficial} si corresponde).
    
    2. **TITULO (H1)**: SEO Clickbait Ético. Ej: "Neuquén Cultural: los 5 planes para este fin de semana".
    
    3. **ESTRUCTURA**:
       - H2 (Bajada).
       - H3 (Viernes, Sábado, Domingo).
       - Si faltan datos, recomienda el MNBA o Paseo de la Costa.
       - NO INVENTES HORARIOS.

    IDIOMA: Español Argentino.
    """
    
    for m in ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]:
        texto = llamar_api_gemini(m, prompt)
        if texto: return texto
        time.sleep(1)
    return None

# --- MAIN ---
def main():
    fechas = obtener_proximo_finde()
    print(f"--- AGENDA: {fechas['short_date']} ---")
    
    # Datos
    oficial = scrapear_web_oficial()
    google = buscar_eventos_google(fechas)
    
    # Imagen (Con filtro anti-starbucks)
    media_id = buscar_y_subir_imagen_segura()
    
    # Redacción
    texto_html = redactar_agenda_seo(oficial, google, fechas)
    if not texto_html: return

    # Limpieza
    texto_html = texto_html.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    if "<h1>" in texto_html: texto_html = texto_html[texto_html.find("<h1>"):]
    
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto_html, re.IGNORECASE)
    titulo = titulo_match.group(1).strip() if titulo_match else f"Agenda Finde: {fechas['viernes']}"
    cuerpo = re.sub(r'<h1>.*?</h1>', '', texto_html, count=1, flags=re.IGNORECASE).strip()

    # Publicar (Agregando estilos CSS básicos para los enlaces)
    estilo_enlaces = """
    <style>
        .contenido-nota a { color: #d35400; text-decoration: underline; font-weight: bold; }
        .contenido-nota h3 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-top: 20px; }
    </style>
    """
    
    html_final = f"""
    {estilo_enlaces}
    <div class="contenido-nota" style="font-family: Arial, sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        {cuerpo}
        <hr>
        <p style="font-size:14px; color:#777;">⚠️ <em>Datos verificados al momento de redacción.</em></p>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 'content': html_final, 'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID), 'featured_media': media_id
    }
    
    requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    print("✅ Agenda publicada.")

if __name__ == "__main__":
    main()

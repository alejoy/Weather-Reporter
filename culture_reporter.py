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

# --- 2. FUENTES DE INFORMACIÓN (Con URLs) ---

def scrapear_web_oficial():
    """Lee la web oficial y retorna Texto + URL Fuente."""
    url = "https://www.neuquencapital.gov.ar/agenda-de-actividades/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    print(f"👉 Leyendo web oficial: {url}...")
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Limpiamos para obtener texto útil
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            
            texto = soup.get_text(separator=' ').strip()
            # Devolvemos un diccionario con el texto y la fuente para que la IA pueda citar
            return {
                "contenido": texto[:10000], # Limitamos caracteres
                "url": url,
                "nombre": "Municipalidad de Neuquén"
            }
    except Exception as e:
        print(f"⚠️ Error scraping oficial: {e}")
    
    return None

def buscar_eventos_google(fechas):
    """Busca en Google y guarda URLs para citar."""
    print("👉 Buscando eventos complementarios en Google...")
    
    queries = [
        f"Agenda cultural Neuquén fin de semana {fechas['viernes']}",
        "Cartelera Cine Teatro Español Neuquén horarios",
        "MNBA Neuquén actividades fin de semana",
        "Agenda cultural Cipolletti Neuquén"
    ]
    
    resultados = []
    
    for q in queries:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": q, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "num": 2}
        try:
            res = requests.get(url, params=params)
            data = res.json()
            if "items" in data:
                for item in data["items"]:
                    resultados.append({
                        "titulo": item['title'],
                        "snippet": item['snippet'],
                        "link": item['link'] # Guardamos el link para citar
                    })
        except: pass
        time.sleep(0.5)

    return resultados

# --- 3. IMÁGENES (Subida a WP) ---
def buscar_y_subir_imagen(query="Cultura Eventos Neuquen"):
    """Busca imagen segura, la sube a WP y devuelve el ID."""
    print(f"👉 Buscando imagen destacada para: {query}...")
    url_api = "https://www.googleapis.com/customsearch/v1"
    
    # Filtro de dominios rotos
    BLACK_LIST = ["instagram.com", "facebook.com", "twitter.com", "pinterest.com"]

    params = {
        "q": query, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY,
        "searchType": "image", "imgSize": "large", "num": 5, "safe": "active"
    }
    
    img_url_final = None
    img_origen = ""
    
    try:
        res = requests.get(url_api, params=params)
        data = res.json()
        if "items" in data:
            for item in data["items"]:
                es_valido = True
                for bl in BLACK_LIST:
                    if bl in item["displayLink"]: es_valido = False
                
                if es_valido:
                    img_url_final = item["link"]
                    img_origen = item["displayLink"]
                    break # Encontramos una buena
    except: pass

    if not img_url_final: return None

    # Subir a WordPress
    try:
        print(f"⬆️ Subiendo imagen a WordPress...")
        res_img = requests.get(img_url_final, timeout=10)
        if res_img.status_code == 200:
            filename = f"agenda-{int(time.time())}.jpg"
            url_upload = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
            headers = {"Content-Type": "image/jpeg", "Content-Disposition": f"attachment; filename={filename}"}
            auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
            
            res_wp = requests.post(url_upload, headers=headers, data=res_img.content, auth=auth)
            if res_wp.status_code == 201:
                return res_wp.json()['id']
    except Exception as e:
        print(f"⚠️ Error subida WP: {e}")
    
    return None

# --- 4. CEREBRO IA (Redacción SEO) ---
def redactar_agenda_seo(info_oficial, info_google, fechas):
    # Preparamos el texto de entrada para la IA con las URLs explícitas
    contexto_google = ""
    for r in info_google:
        contexto_google += f"- INFO: {r['snippet']} | FUENTE: {r['titulo']} | URL: {r['link']}\n"
    
    texto_oficial_clean = info_oficial['contenido'] if info_oficial else "No disponible"
    url_oficial = info_oficial['url'] if info_oficial else ""

    prompt = f"""
    Actúa como Editor de Cultura de un medio digital en Neuquén.
    Escribe la AGENDA CULTURAL para el fin de semana del {fechas['viernes']} al {fechas['domingo']}.

    DATOS RECOLECTADOS (Usar solo información confirmada):
    --- FUENTE OFICIAL MUNICIPALIDAD ---
    URL PARA CITAR: {url_oficial}
    CONTENIDO: {texto_oficial_clean}
    ------------------------------------
    --- OTRAS FUENTES GOOGLE ---
    {contexto_google}
    ------------------------------------

    REGLAS DE ORO (PERIODISMO DE PRECISIÓN):
    1. NO INVENTES HORARIOS NI LUGARES. Si no dice hora exacta, pon "Horario a confirmar" o "Consultar en web oficial".
    2. CITAS OBLIGATORIAS: Si recomiendas un evento y no tienes todos los detalles, DEBES poner: "Más info en [Nombre Fuente]".
    3. ENLACES: Si la información viene de la Muni, agrega un enlace: <a href="{url_oficial}" target="_blank">Web oficial</a>.
    4. RELLENO INTELIGENTE: Si hay pocos eventos específicos, completa con "Clásicos de siempre" (Paseo de la Costa, MNBA, Parque Norte), aclarando que son paseos libres.

    ESTRUCTURA SEO & GOOGLE DISCOVER:
    1. TÍTULO H1: Clickbait Ético (Que genere curiosidad pero sea verdad). Ej: "Neuquén: 5 planes imperdibles para este fin de semana".
    2. BAJADA H2: Resumen potente de 2 líneas.
    3. CUERPO (H3 por día):
       - Viernes: [Lista de eventos]
       - Sábado: [Lista de eventos]
       - Domingo: [Lista de eventos]
    4. CIERRE ÚTIL: Link a la farmacia de turno o pronóstico breve si aplica.

    IDIOMA: Español Argentino.
    FORMATO: HTML limpio (sin doctype, sin body).
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"⚠️ Error IA: {e}")
        return None

# --- MAIN ---
def main():
    fechas = obtener_proximo_finde()
    print(f"--- GENERANDO AGENDA: {fechas['short_date']} ---")
    
    # 1. Recolección de Datos
    oficial = scrapear_web_oficial()
    google = buscar_eventos_google(fechas)
    
    # 2. Buscar Foto Destacada (Genérica o específica si hay un evento muy grande)
    # Intentamos buscar "Agenda Cultural Neuquen" + mes actual
    media_id = buscar_y_subir_imagen(f"Agenda Cultural Neuquen {fechas['query_date']}")
    
    # 3. Redacción IA
    texto_html = redactar_agenda_seo(oficial, google, fechas)
    
    if not texto_html:
        print("❌ Error crítico en generación de texto.")
        return

    # 4. Limpieza y Extracción de Título
    texto_html = texto_html.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    
    # Extraer H1
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto_html, re.IGNORECASE)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        cuerpo = re.sub(r'<h1>.*?</h1>', '', texto_html, count=1, flags=re.IGNORECASE).strip()
    else:
        titulo = f"Agenda Neuquén: Qué hacer del {fechas['viernes']} al {fechas['domingo']}"
        cuerpo = texto_html

    # 5. Publicar en WordPress
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333;">
        {cuerpo}
        
        <hr style="margin: 40px 0; border: 0; border-top: 1px solid #eee;">
        <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; font-size: 14px; color: #666;">
            <strong>⚠️ Importante:</strong> <em>Redacción Servicios</em> recopila esta información de fuentes públicas. Los organizadores pueden modificar horarios sin previo aviso. Recomendamos siempre hacer clic en los enlaces oficiales antes de salir.
        </div>
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 
        'content': html_final, 
        'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID),
        'featured_media': media_id # Asignamos la imagen destacada subida
    }
    
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Agenda Cultural publicada y optimizada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

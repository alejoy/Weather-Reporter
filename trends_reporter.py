import os
import requests
import json
import time
from datetime import datetime
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

# --- 1. OBTENER TENDENCIAS (Scraping Trends24) ---
def obtener_top_tendencias():
    """Obtiene el Top 10 de Argentina desde Trends24."""
    url = "https://trends24.in/argentina/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'}
    
    print(f"👉 Scrapeando tendencias de: {url}...")
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Trends24 tiene listas por hora. Tomamos la primera lista (la más reciente)
            lista_actual = soup.find("ol", class_="trend-card__list")
            
            tendencias = []
            if lista_actual:
                for item in lista_actual.find_all("li")[:8]: # Tomamos las top 8
                    tag = item.find("a").text
                    tendencias.append(tag)
            
            print(f"✅ Tendencias encontradas: {tendencias}")
            return tendencias
    except Exception as e:
        print(f"⚠️ Error Trends24: {e}")
    return []

# --- 2. INVESTIGAR CONTEXTO (Google Search) ---
def investigar_tendencia(trend):
    """Busca en Google por qué esto es tendencia."""
    print(f"🕵️ Investigando: {trend}...")
    
    # 1. Buscamos noticias recientes para entender el contexto
    query_news = f"{trend} qué pasó noticia argentina"
    contexto = ""
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"q": query_news, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "num": 3}
        res = requests.get(url, params=params)
        data = res.json()
        
        if "items" in data:
            for item in data["items"]:
                contexto += f"- {item['title']}: {item['snippet']}\n"
    except: pass

    # 2. Buscamos UN tweet viral específico para embeber
    tweet_url = None
    try:
        # Buscamos solo en twitter.com
        query_tweet = f"site:twitter.com {trend}"
        params_t = {"q": query_tweet, "cx": GOOGLE_SEARCH_CX, "key": GOOGLE_SEARCH_API_KEY, "num": 1}
        res_t = requests.get(url, params=params_t)
        data_t = res_t.json()
        if "items" in data_t:
            tweet_url = data_t["items"][0]["link"]
    except: pass

    return {"nombre": trend, "contexto": contexto, "tweet_url": tweet_url}

# --- 3. SELECCIÓN IA ---
def seleccionar_mejor_historia(lista_tendencias_investigadas):
    """Le da a Gemini la lista y le pide que elija la más noticiable."""
    
    datos_texto = ""
    for t in lista_tendencias_investigadas:
        datos_texto += f"TENDENCIA: {t['nombre']}\nCONTEXTO: {t['contexto']}\n---\n"

    prompt = f"""
    Eres un Editor de Viral de un diario. Analiza estas tendencias de Twitter Argentina y elige LA MEJOR para hacer una nota.
    
    CRITERIOS DE SELECCIÓN:
    1. Que sea una noticia real o polémica (política, espectáculo, deporte).
    2. DESCARTA hashtags genéricos como "Buen Lunes", "Feliz Cumpleaños" (a menos que sea un famoso) o spam de K-Pop.
    3. Debe haber suficiente contexto para escribir 3 párrafos.

    LISTA:
    {datos_texto}

    RESPONDE SOLO CON EL NOMBRE EXACTO DE LA TENDENCIA ELEGIDA. Si ninguna sirve, responde "NINGUNA".
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        eleccion = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        print(f"🤖 La IA eligió: {eleccion}")
        return eleccion
    except: return "NINGUNA"

# --- 4. REDACCIÓN ---
def redactar_nota_viral(trend_data):
    tweet_embed = f'\n\n[embed]{trend_data["tweet_url"]}[/embed]' if trend_data["tweet_url"] else ""
    
    prompt = f"""
    Escribe una NOTA CORTA Y VIRAL sobre la tendencia: "{trend_data['nombre']}".
    
    CONTEXTO ENCONTRADO EN GOOGLE:
    {trend_data['contexto']}

    ESTRUCTURA (HTML):
    1. TÍTULO H1: Muy llamativo, estilo "Explicado: por qué todos hablan de X".
    2. CUERPO:
       - Párrafo 1: Qué está pasando ahora mismo en redes.
       - Párrafo 2: Explicación del contexto (qué pasó, quién dijo qué).
       - Párrafo 3: Reacciones de la gente (memes, enojo, risa).
    
    IMPORTANTE:
    - No inventes. Si el contexto es poco, haz la nota corta.
    - Estilo informal y rápido.
    - Idioma Español Argentino.
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        res = requests.post(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        texto = res.json()['candidates'][0]['content']['parts'][0]['text']
        return texto + tweet_embed # Agregamos el tweet al final
    except: return None

# --- MAIN ---
def main():
    print("--- BUSCANDO VIRALES ---")
    
    # 1. Obtener lista cruda
    raw_trends = obtener_top_tendencias()
    if not raw_trends: return

    # 2. Investigar las primeras 4 (para ahorrar cuota y tiempo)
    investigadas = []
    for t in raw_trends[:4]:
        data = investigar_tendencia(t)
        if len(data['contexto']) > 50: # Solo si encontró noticias reales
            investigadas.append(data)
        time.sleep(1)
    
    if not investigadas:
        print("❌ Ninguna tendencia tiene contexto noticioso hoy.")
        return

    # 3. Elegir la ganadora
    ganadora_nombre = seleccionar_mejor_historia(investigadas)
    if "NINGUNA" in ganadora_nombre:
        print("❌ La IA decidió que no hay nada interesante.")
        return
        
    # Recuperar datos de la ganadora
    datos_ganadora = next((item for item in investigadas if item["nombre"] in ganadora_nombre), None)
    
    if not datos_ganadora:
        datos_ganadora = investigadas[0] # Fallback a la primera

    # 4. Redactar
    print(f"✍️ Redactando sobre: {datos_ganadora['nombre']}")
    texto_html = redactar_nota_viral(datos_ganadora)
    if not texto_html: return

    # 5. Limpieza
    texto_html = texto_html.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    if "<h1>" in texto_html: texto_html = texto_html[texto_html.find("<h1>"):]
    
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto_html, re.IGNORECASE)
    titulo = titulo_match.group(1).strip() if titulo_match else f"Viral: {datos_ganadora['nombre']}"
    cuerpo = re.sub(r'<h1>.*?</h1>', '', texto_html, count=1, flags=re.IGNORECASE).strip()

    # 6. Publicar
    html_final = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.6; color: #333;">
        <span style="background: #000; color: #fff; padding: 4px 8px; font-size: 12px; font-weight: bold; border-radius: 4px;">TENDENCIA AHORA</span>
        <br><br>
        {cuerpo}
    </div>
    """
    
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 'content': html_final, 'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID)
    }
    requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    print("✅ Nota viral publicada.")

if __name__ == "__main__":
    main()

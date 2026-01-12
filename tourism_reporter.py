import os
import requests
import json
import time
from datetime import datetime
import re

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1")

# LISTA DE DESTINOS
DESTINOS = [
    "Villa La Angostura", "San Martín de los Andes", "Villa Pehuenia", 
    "Caviahue", "Ruta de los Siete Lagos", "Parque Nacional Lanín", 
    "Lago Nahuel Huapi", "Volcán Lanín", "Junín de los Andes", "Villa Traful",
    "Cerro Chapelco", "Río Limay", "El Chocón", "Lago Huechulafquen",
    "Moquehue", "Paso Córdoba Neuquén", "Lago Aluminé", "Volcán Batea Mahuida"
]

def seleccionar_destino_por_semana():
    semana_actual = datetime.now().isocalendar()[1]
    indice = semana_actual % len(DESTINOS)
    return DESTINOS[indice]

def buscar_imagen_google(query):
    """Busca imagen evitando Instagram/Facebook."""
    url = "https://www.googleapis.com/customsearch/v1"
    BLACK_LIST = ["instagram.com", "facebook.com", "pinterest.com", "x.com", "twitter.com"]
    
    params = {
        "q": f"{query} paisaje turismo neuquen", 
        "cx": GOOGLE_SEARCH_CX,
        "key": GOOGLE_SEARCH_API_KEY,
        "searchType": "image",
        "imgSize": "large", # Pedimos grande para que sirva de portada
        "imgType": "photo",
        "num": 5,
        "safe": "active"
    }
    
    try:
        print(f"👉 Buscando imagen para: {query}...", end=" ")
        res = requests.get(url, params=params)
        data = res.json()
        
        if "items" not in data:
            print("❌ No encontrada.")
            return None
            
        for item in data["items"]:
            origen = item["displayLink"].lower()
            es_valido = True
            for dominio_prohibido in BLACK_LIST:
                if dominio_prohibido in origen:
                    es_valido = False
                    break
            
            if es_valido:
                print(f"✅ Encontrada en: {origen}")
                return {
                    "url": item["link"],
                    "contexto": item["title"],
                    "origen": item["displayLink"]
                }
        return None
    except Exception as e:
        print(f"⚠️ Error Search: {e}")
        return None

def subir_imagen_wordpress(img_data, titulo_destino):
    """
    Descarga la imagen de la web y la sube a la biblioteca de WordPress.
    Devuelve el ID de la imagen para usarla como destacada.
    """
    image_url = img_data['url']
    print(f"⬆️ Subiendo imagen a WordPress: {titulo_destino}...")
    
    try:
        # 1. Descargar imagen a memoria
        res_img = requests.get(image_url)
        if res_img.status_code != 200:
            print("❌ Error al descargar imagen fuente.")
            return None
        
        imagen_binaria = res_img.content
        nombre_archivo = f"{titulo_destino.lower().replace(' ', '-')}.jpg"

        # 2. Subir a WordPress API
        url_upload = f"{WORDPRESS_URL}/wp-json/wp/v2/media"
        headers = {
            "Content-Type": "image/jpeg",
            "Content-Disposition": f"attachment; filename={nombre_archivo}"
        }
        auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
        
        res_wp = requests.post(url_upload, headers=headers, data=imagen_binaria, auth=auth)
        
        if res_wp.status_code == 201:
            media_id = res_wp.json()['id']
            print(f"✅ Imagen subida con ID: {media_id}")
            return media_id
        else:
            print(f"❌ Error subiendo a WP: {res_wp.text}")
            return None

    except Exception as e:
        print(f"⚠️ Excepción subida: {e}")
        return None

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5}
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        if res.status_code == 200:
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        return None
    except:
        return None

def generar_nota_turismo(destino):
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    prompt = f"""
    Actúa como un Guía de Turismo Responsable. Escribe un ARTÍCULO PERIODÍSTICO sobre: {destino}.
    
    ESTRUCTURA OBLIGATORIA (HTML):
    1. TÍTULO (H1): Atractivo. Ej: "Turismo en Neuquén: guía para visitar {destino}".
    2. BAJADA (H2): Resumen periodístico.
    3. CUERPO (H3 para secciones):
       - "El paisaje": Descripción realista.
       - "Actividades": Qué hacer.
       - "Datos útiles": Cómo llegar y época.
       
    4. SECCIÓN OBLIGATORIA (H3 "Turismo Responsable"):
       - Párrafo FUERTE: Prohibido hacer fuego, llevarse la basura, cuidar fauna.
    
    5. TONO: Informativo, serio, sin saludar.
    """

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto: return texto
        time.sleep(1)
    return None

def limpiar_respuesta(texto, destino_hoy):
    texto = texto.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    
    if "<h1>" in texto:
        indice = texto.find("<h1>")
        texto = texto[indice:]
    
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto, re.IGNORECASE)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        cuerpo = re.sub(r'<h1>.*?</h1>', '', texto, count=1, flags=re.IGNORECASE).strip()
    else:
        titulo = f"Destino recomendado: {destino_hoy}"
        cuerpo = texto
        
    return titulo, cuerpo

def main():
    destino_hoy = seleccionar_destino_por_semana()
    print(f"--- TURISMO: {destino_hoy} ---")
    
    # 1. Buscar Imagen
    img_data = buscar_imagen_google(destino_hoy)
    if not img_data:
        print("❌ Sin imagen, cancelando.")
        return

    # 2. SUBIR IMAGEN A WORDPRESS (NUEVO PASO)
    media_id = subir_imagen_wordpress(img_data, destino_hoy)
    # Nota: Si falla la subida, media_id será None, pero igual intentaremos publicar la nota sin foto destacada.

    # 3. Redactar
    texto_crudo = generar_nota_turismo(destino_hoy)
    if not texto_crudo: return

    titulo, cuerpo = limpiar_respuesta(texto_crudo, destino_hoy)
    if len(titulo) < 5: titulo = f"Descubrí {destino_hoy}"

    # 4. HTML Cuerpo (Ya no necesitamos poner la <img> al principio, porque será destacada)
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333; max-width: 800px; margin: auto;">
        
        <div class="contenido-nota">
            {cuerpo}
        </div>
        
        <div style="margin-top: 40px; padding: 20px; background: #fff3cd; border-left: 5px solid #ffc107; font-size: 16px; color: #856404;">
            🔥 <strong>Prevención:</strong> En Patagonia el fuego solo está permitido en campings habilitados. Cuidemos el bosque.
            <br><small style="color: #999;">Foto de portada: {img_data['origen']}</small>
        </div>
    </div>
    """

    # 5. Publicar con Featured Media
    print(f"Publicando nota...")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 
        'content': html_post, 
        'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID),
        'featured_media': media_id if media_id else None # AQUÍ SE ASIGNA LA FOTO DESTACADA
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota publicada con Imagen Destacada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

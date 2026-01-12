import os
import requests
import json
import time
from datetime import datetime
import re

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Credenciales para Google Images
GOOGLE_SEARCH_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.environ.get("GOOGLE_SEARCH_CX")

WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')
WORDPRESS_AUTHOR_ID = os.environ.get("WORDPRESS_AUTHOR_ID", "1") # Default ID 1 (Admin)

# LISTA DE DESTINOS (Rotación Semanal)
DESTINOS = [
    "Villa La Angostura", "San Martín de los Andes", "Villa Pehuenia", 
    "Caviahue", "Ruta de los Siete Lagos", "Parque Nacional Lanín", 
    "Lago Nahuel Huapi", "Volcán Lanín", "Junín de los Andes", "Villa Traful",
    "Cerro Chapelco", "Río Limay", "El Chocón", "Lago Huechulafquen",
    "Moquehue", "Paso Córdoba Neuquén", "Lago Aluminé", "Volcán Batea Mahuida"
]

def seleccionar_destino_por_semana():
    """Elige destino según número de semana para no repetir."""
    semana_actual = datetime.now().isocalendar()[1]
    indice = semana_actual % len(DESTINOS)
    destino = DESTINOS[indice]
    print(f"📅 Semana {semana_actual}: Destino '{destino}'")
    return destino

def buscar_imagen_google(query):
    """Busca una imagen real en Google Images."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": f"{query} paisaje turismo neuquen", # Contexto para que salgan fotos lindas
        "cx": GOOGLE_SEARCH_CX,
        "key": GOOGLE_SEARCH_API_KEY,
        "searchType": "image",
        "imgSize": "large", # Pedimos fotos grandes
        "imgType": "photo", # Solo fotos, no dibujos
        "num": 1,
        "safe": "active"
    }
    
    try:
        print(f"👉 Buscando imagen en Google para: {query}...", end=" ")
        res = requests.get(url, params=params)
        data = res.json()
        
        if "items" in data:
            item = data["items"][0]
            print("✅")
            return {
                "url": item["link"],
                "contexto": item["title"],
                "origen": item["displayLink"] # Para dar crédito
            }
        else:
            print("❌ No encontrada.")
            return None
    except Exception as e:
        print(f"⚠️ Error Google Search: {e}")
        return None

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5}
    }

    try:
        print(f"👉 Generando texto con {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print("❌")
            return None
    except:
        return None

def generar_nota_turismo(destino):
    # Priorizamos el Lite que funciona bien
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    
    prompt = f"""
    Actúa como un Guía de Turismo Responsable de la Provincia de Neuquén.
    Escribe un ARTÍCULO PERIODÍSTICO sobre: {destino}.
    
    ESTRUCTURA OBLIGATORIA (HTML):
    1. TÍTULO (H1): Atractivo. Ejemplo: "Turismo en Neuquén: guía para visitar {destino}".
    2. BAJADA (H2): Resumen periodístico.
    3. CUERPO (Secciones con <h3>):
       - "El paisaje": Descripción realista.
       - "Actividades": Qué se puede hacer.
       - "Datos útiles": Cómo llegar y época recomendada.
       
    4. SECCIÓN OBLIGATORIA DE CONCIENTIZACIÓN (H3 "Turismo Responsable"):
       - Si es zona de bosques/montaña/lagos: Escribe un párrafo FUERTE recordando que está **prohibido hacer fuego** fuera de campings habilitados, regresar con la basura y cuidar la fauna.
       - Menciona el riesgo de incendios forestales si aplica.
    
    5. TONO: Informativo, serio pero invitando a viajar.
    6. IDIOMA: Español Argentino.
    """

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto: return texto
        time.sleep(1)
    return None

def limpiar_respuesta(texto):
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
    print(f"--- NOTA TURISMO: {destino_hoy} ---")
    
    # Buscar Foto Real en Google
    img_data = buscar_imagen_google(destino_hoy)
    if not img_data:
        print("❌ Sin imagen, cancelando.")
        return

    # Redactar Nota
    texto_crudo = generar_nota_turismo(destino_hoy)
    if not texto_crudo:
        print("❌ Sin texto, cancelando.")
        return

    titulo, cuerpo = limpiar_respuesta(texto_crudo)
    if len(titulo) < 5: titulo = f"Descubrí {destino_hoy}: naturaleza pura"

    # HTML Final
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333; max-width: 800px; margin: auto;">
        
        <figure style="margin: 0 0 30px 0;">
            <img src="{img_data['url']}" alt="Paisaje de {destino_hoy}" style="width: 100%; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <figcaption style="font-size: 12px; color: #888; text-align: right; margin-top: 5px;">
                Imagen ilustrativa (Fuente: {img_data['origen']})
            </figcaption>
        </figure>

        <div class="contenido-nota">
            {cuerpo}
        </div>
        
        <div style="margin-top: 40px; padding: 20px; background: #fff3cd; border-left: 5px solid #ffc107; font-size: 16px; color: #856404;">
            🔥 <strong>Prevención de Incendios:</strong> Recordá que en la Patagonia el fuego solo está permitido en lugares habilitados. Si ves humo, llamá urgente al 105 o 911.
        </div>
    </div>
    """

    # Publicar con Autor Específico
    print(f"Publicando como Autor ID {WORDPRESS_AUTHOR_ID}: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 
        'content': html_post, 
        'status': 'draft',
        'author': int(WORDPRESS_AUTHOR_ID) # Aquí asignamos el autor
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

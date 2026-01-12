import os
import requests
import json
import random
import time

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')

# LISTA DE DESTINOS (Puedes agregar más)
DESTINOS = [
    "Villa La Angostura", "San Martín de los Andes", "Villa Pehuenia", 
    "Caviahue", "Copahue", "Ruta de los Siete Lagos", "Parque Nacional Lanín", 
    "Lago Nahuel Huapi", "Volcán Lanín", "Junín de los Andes", "Villa Traful",
    "Cerro Chapelco", "Río Limay", "El Chocón", "Lago Huechulafquen"
]

def obtener_imagen_unsplash(query):
    """Busca una foto HD en Unsplash y devuelve URL + Créditos."""
    url = f"https://api.unsplash.com/search/photos"
    params = {
        "query": f"{query} patagonia argentina", # Agregamos contexto para no traer fotos de otro lado
        "client_id": UNSPLASH_ACCESS_KEY,
        "orientation": "landscape",
        "per_page": 1,
        "order_by": "relevant"
    }
    
    try:
        res = requests.get(url, params=params)
        data = res.json()
        
        if data['results']:
            foto = data['results'][0]
            return {
                "url": foto['urls']['regular'], # Calidad óptima para web
                "autor": foto['user']['name'],
                "link_autor": foto['user']['links']['html'],
                "descripcion": foto['alt_description'] or query
            }
        else:
            # Fallback si no encuentra el lugar exacto, busca "Patagonia"
            print(f"⚠️ No se encontró foto para {query}, buscando genérico...")
            return obtener_imagen_unsplash("Patagonia Landscape")
            
    except Exception as e:
        print(f"⚠️ Error Unsplash: {e}")
        return None

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
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
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    
    prompt = f"""
    Actúa como un Editor de Viajes experto en la Patagonia (tipo Lonely Planet o TripAdvisor).
    Escribe un ARTÍCULO SEO (Google Discover) sobre por qué visitar: {destino}.
    
    ESTRUCTURA OBLIGATORIA (HTML):
    1. TÍTULO (H1): Clickbait ético. Ejemplo: "Escapada soñada: por qué {destino} es el paraíso de Neuquén".
    2. BAJADA (H2): Resumen inspirador de una frase.
    3. CUERPO (4 Secciones con <h3>):
       - "El encanto del lugar": Descripción sensorial (paisajes, clima).
       - "Qué hacer": 3 actividades imperdibles (trekking, comida, relax).
       - "Cuándo ir": Mejor época y consejos de ropa.
       - "Cómo llegar": Tips breves de ruta.
    
    4. ESTILO: Inspirador, visual, que den ganas de viajar YA.
    5. IDIOMA: Español Argentino.
    """

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto: return texto
        time.sleep(1)
    return None

def limpiar_respuesta(texto):
    texto = texto.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    # Extraer título
    import re
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto, re.IGNORECASE)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        cuerpo = re.sub(r'<h1>.*?</h1>', '', texto, count=1, flags=re.IGNORECASE).strip()
    else:
        titulo = "Guía de Viaje Patagonia"
        cuerpo = texto
    return titulo, cuerpo

def main():
    # 1. Elegir Destino Random
    destino_hoy = random.choice(DESTINOS)
    print(f"--- GENERANDO NOTA TURISMO: {destino_hoy} ---")
    
    # 2. Buscar Foto
    img_data = obtener_imagen_unsplash(destino_hoy)
    if not img_data:
        print("❌ Error crítico: No hay imagen.")
        return

    # 3. Redactar Nota
    texto_crudo = generar_nota_turismo(destino_hoy)
    if not texto_crudo:
        print("❌ Error crítico: No hay texto.")
        return

    titulo, cuerpo = limpiar_respuesta(texto_crudo)
    if len(titulo) < 5: titulo = f"Descubrí {destino_hoy}: la joya de la Patagonia"

    # 4. Armar HTML Final (Foto + Texto + Créditos)
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333; max-width: 800px; margin: auto;">
        
        <figure style="margin: 0 0 30px 0;">
            <img src="{img_data['url']}" alt="{img_data['descripcion']}" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <figcaption style="font-size: 12px; color: #777; text-align: right; margin-top: 5px;">
                Foto: <a href="{img_data['link_autor']}?utm_source=WeatherReporter&utm_medium=referral" target="_blank" style="color: #777;">{img_data['autor']}</a> en <a href="https://unsplash.com/?utm_source=WeatherReporter&utm_medium=referral" style="color: #777;">Unsplash</a>
            </figcaption>
        </figure>

        <div class="contenido-nota">
            {cuerpo}
        </div>
        
        <div style="margin-top: 40px; padding: 20px; background: #f0f8ff; border-left: 5px solid #3498db; font-size: 16px;">
            🚗 <strong>Tip de Viajero:</strong> Antes de salir a la ruta, recordá chequear el <a href="#">estado del clima</a> para disfrutar tu viaje seguro.
        </div>
    </div>
    """

    # 5. Publicar
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 
        'content': html_post, 
        'status': 'draft' # O 'publish' si te animas directo
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota de turismo publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

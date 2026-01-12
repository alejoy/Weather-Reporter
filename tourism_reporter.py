import os
import requests
import json
import time
from datetime import datetime
import re

# --- CONFIGURACIÓN ---
METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')

# LISTA DE DESTINOS (Ordenados para la rotación semanal)
# Agrega todos los que quieras. El script recorrerá 1 por semana.
DESTINOS = [
    "Villa La Angostura", 
    "San Martín de los Andes", 
    "Villa Pehuenia", 
    "Caviahue", 
    "Ruta de los Siete Lagos", 
    "Parque Nacional Lanín", 
    "Lago Nahuel Huapi", 
    "Volcán Lanín", 
    "Junín de los Andes", 
    "Villa Traful",
    "Cerro Chapelco", 
    "Río Limay", 
    "El Chocón", 
    "Lago Huechulafquen",
    "Moquehue",
    "Paso Córdoba Neuquén",
    "Lago Aluminé",
    "Volcán Batea Mahuida"
]

def seleccionar_destino_por_semana():
    """
    Elige un destino basado en el número de semana del año.
    Esto evita repeticiones y garantiza rotación perfecta sin base de datos.
    """
    semana_actual = datetime.now().isocalendar()[1] # Devuelve número 1-52
    indice = semana_actual % len(DESTINOS) # Matemáticas de módulo para rotar
    destino = DESTINOS[indice]
    print(f"📅 Semana {semana_actual}: Toca destino '{destino}' (Índice {indice})")
    return destino

def obtener_imagen_unsplash(query):
    """Busca una foto HD específica en Unsplash."""
    url = f"https://api.unsplash.com/search/photos"
    # Ajustamos la query para ser más precisos con la geografía
    params = {
        "query": f"{query} landscape", 
        "client_id": UNSPLASH_ACCESS_KEY,
        "orientation": "landscape",
        "per_page": 1,
        "order_by": "relevant" # Relevant suele dar la foto más icónica
    }
    
    try:
        res = requests.get(url, params=params)
        data = res.json()
        
        if data['results']:
            foto = data['results'][0]
            return {
                "url": foto['urls']['regular'],
                "autor": foto['user']['name'],
                "link_autor": foto['user']['links']['html'],
                "descripcion": foto['alt_description'] or query
            }
        else:
            print(f"⚠️ No se encontró foto exacta para {query}. Intentando fallback...")
            # Si falla, buscamos algo un poco más genérico pero de la zona
            if "Neuquén" not in query:
                return obtener_imagen_unsplash(f"{query} Neuquen")
            return None
            
    except Exception as e:
        print(f"⚠️ Error Unsplash: {e}")
        return None

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.6} # Bajamos temp para que alucine menos
    }

    try:
        print(f"👉 Generando texto con {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"❌ (Error {res.status_code})")
            return None
    except:
        return None

def generar_nota_turismo(destino):
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    
    prompt = f"""
    Actúa como un Editor de Viajes experto en la Patagonia.
    Escribe un ARTÍCULO SEO para Google Discover sobre: {destino}.
    
    INSTRUCCIONES ESTRICTAS (NO SALUDES, EMPIEZA DIRECTO CON HTML):
    1. TÍTULO (H1): Atractivo y con palabra clave. Ejemplo: "Escapada a {destino}: guía completa".
    2. BAJADA (H2): Resumen inspirador en una frase.
    3. ESTRUCTURA DE CONTENIDO (Usa <h3>):
       - "Por qué ir": Descripción del paisaje y la magia del lugar.
       - "Qué hacer": 3 actividades concretas.
       - "Cuándo ir": Mejor época.
       - "Cómo llegar": Rutas principales (menciona rutas de Neuquén).
    
    4. TONO: Periodístico, inspirador, sin frases de relleno como "¡Absolutamente!".
    5. IDIOMA: Español Argentino.
    """

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto: return texto
        time.sleep(1)
    return None

def limpiar_respuesta(texto):
    """
    Limpia el texto basura de la IA.
    Elimina todo lo que esté antes del primer <h1>.
    """
    # 1. Quitar markdown de código
    texto = texto.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    
    # 2. Buscar dónde empieza el H1 y cortar todo lo anterior
    if "<h1>" in texto:
        indice_inicio = texto.find("<h1>")
        texto = texto[indice_inicio:]
    
    # 3. Extraer título para WordPress
    titulo_match = re.search(r'<h1>(.*?)</h1>', texto, re.IGNORECASE)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        cuerpo = re.sub(r'<h1>.*?</h1>', '', texto, count=1, flags=re.IGNORECASE).strip()
    else:
        titulo = f"Descubrí {destino}"
        cuerpo = texto
        
    return titulo, cuerpo

def main():
    # 1. Rotación de Destino (Sin azar)
    destino_hoy = seleccionar_destino_por_semana()
    print(f"--- GENERANDO NOTA TURISMO: {destino_hoy} ---")
    
    # 2. Buscar Foto
    img_data = obtener_imagen_unsplash(destino_hoy)
    if not img_data:
        print("❌ Error crítico: No hay imagen. Abortando.")
        return

    # 3. Redactar Nota
    texto_crudo = generar_nota_turismo(destino_hoy)
    if not texto_crudo:
        print("❌ Error crítico: No hay texto.")
        return

    # 4. Limpieza Profunda
    titulo, cuerpo = limpiar_respuesta(texto_crudo)
    
    # Validación final de título
    if len(titulo) < 5: 
        titulo = f"Guía de viaje: {destino_hoy}, la joya de Neuquén"

    # 5. Armar HTML Final
    html_post = f"""
    <div style="font-family: 'Arial', sans-serif; font-size: 18px; line-height: 1.8; color: #333; max-width: 800px; margin: auto;">
        
        <figure style="margin: 0 0 30px 0;">
            <img src="{img_data['url']}" alt="{img_data['descripcion']}" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <figcaption style="font-size: 12px; color: #777; text-align: right; margin-top: 5px;">
                Foto: <a href="{img_data['link_autor']}?utm_source=WeatherReporter&utm_medium=referral" target="_blank" style="color: #777;">{img_data['autor']}</a> en Unsplash
            </figcaption>
        </figure>

        <div class="contenido-nota">
            {cuerpo}
        </div>
        
        <div style="margin-top: 40px; padding: 20px; background: #e8f8f5; border-left: 5px solid #1abc9c; font-size: 16px;">
            🎒 <strong>Tip de Viajero:</strong> Neuquén tiene paisajes únicos. Recordá siempre llevarte tu basura y cuidar el medio ambiente.
        </div>
    </div>
    """

    # 6. Publicar
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 
        'content': html_post, 
        'status': 'draft',
        # 'categories': [ID_CATEGORIA_TURISMO] # Opcional
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Nota publicada.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

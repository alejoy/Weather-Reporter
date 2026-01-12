import os
import requests
import json
import time
from datetime import datetime
import locale

# --- CONFIGURACIÓN ---
# Usamos las mismas claves que ya tienes configuradas
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')

# Configurar fecha en español
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass # Si falla en el servidor, usamos default

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8} # Un poco más creativo para el horóscopo
    }

    try:
        print(f"👉 Probando: {modelo}...", end=" ")
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        if res.status_code == 200:
            print("✅")
            return res.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"❌ Error {res.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error red: {e}")
        return None

def generar_horoscopo_ia(fecha_hoy):
    modelos = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    
    prompt = f"""
    Actúa como una Astróloga experta y mística (estilo Ludovica Squirru o similar).
    Escribe el HORÓSCOPO COMPLETO para hoy: {fecha_hoy}.
    
    INSTRUCCIONES DE FORMATO (HTML):
    1. TÍTULO H1: "Horóscopo de hoy: {fecha_hoy}"
    2. INTRODUCCIÓN (H2): Un breve párrafo sobre la energía cósmica del día (movimientos planetarios generales).
    3. SIGNOS: Debes escribir un párrafo para CADA UNO de los 12 signos.
       - Formato por signo:
         <h3>♈ ARIES</h3>
         <p>Predicción sobre amor, trabajo y dinero...</p>
         
         <h3>♉ TAURO</h3>
         <p>Predicción...</p>
         
         (Y así con Géminis, Cáncer, Leo, Virgo, Libra, Escorpio, Sagitario, Capricornio, Acuario, Piscis).
    
    4. ESTILO: Místico pero directo. Positivo.
    5. IDIOMA: Español.
    """

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto: return texto
        time.sleep(1)
    return None

def main():
    fecha_hoy = datetime.now().strftime("%A %d de %B de %Y")
    print(f"--- GENERANDO HORÓSCOPO PARA: {fecha_hoy} ---")

    texto_ia = generar_horoscopo_ia(fecha_hoy)

    if not texto_ia:
        print("❌ Falló la generación.")
        return

    # Limpieza básica
    texto_limpio = texto_ia.replace('```html', '').replace('```', '').strip()
    
    # Extracción de título
    lines = texto_limpio.split('\n')
    titulo = f"Horóscopo del día: {fecha_hoy}"
    cuerpo = texto_limpio
    
    if "<h1>" in lines[0]:
        titulo = lines[0].replace('<h1>','').replace('</h1>','').strip()
        cuerpo = "\n".join(lines[1:])

    # Diseño HTML Místico
    html_final = f"""
    <div style="font-family: 'Georgia', serif; font-size: 18px; line-height: 1.7; color: #2c3e50; max-width: 800px; margin: auto;">
        
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 15px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <p style="text-transform: uppercase; letter-spacing: 2px; font-size: 14px; margin: 0; opacity: 0.8;">Astrología Diaria</p>
            <h2 style="font-size: 40px; margin: 10px 0; font-family: sans-serif;">Los Astros Hoy</h2>
            <div style="font-size: 18px; font-style: italic;">{fecha_hoy}</div>
        </div>

        <div class="contenido-horoscopo" style="background: white; padding: 20px;">
            {cuerpo}
        </div>

        <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-left: 4px solid #764ba2; font-size: 14px; color: #666;">
            <em>Recuerda: Los astros inclinan, pero no obligan. Tu destino lo construyes tú.</em>
        </div>
    </div>
    """

    # Publicar
    print(f"Publicando: {titulo}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo, 
        'content': html_final, 
        'status': 'draft',
        'categories': [] # Aquí podrías poner el ID de la categoría "Horóscopo" si lo sabes
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Horóscopo publicado.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

import os
import requests
import json
import time
from datetime import datetime
import re

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL").rstrip('/')

# --- TRADUCCIÓN MANUAL DE FECHAS (INFALIBLE) ---
DIAS_SEMANA = {
    'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
    'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
}
MESES = {
    'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
    'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
    'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
}

def obtener_fecha_en_espanol():
    """Genera la fecha en español manualmente sin depender del sistema operativo."""
    now = datetime.now()
    dia_ing = now.strftime("%A") # Monday
    mes_ing = now.strftime("%B") # January
    dia_num = now.strftime("%d")
    anio = now.strftime("%Y")
    
    # Traducimos
    dia_es = DIAS_SEMANA.get(dia_ing, dia_ing)
    mes_es = MESES.get(mes_ing, mes_ing)
    
    return f"{dia_es} {dia_num} de {mes_es} de {anio}"

def llamar_api_directa(modelo, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 2000
        }
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
    Actúa como una Astróloga experta. Escribe el HORÓSCOPO para hoy: {fecha_hoy}.
    
    REGLAS ESTRICTAS (HTML):
    1. NO saludes, NO digas "Aquí tienes tu horóscopo". Empieza DIRECTO con la etiqueta <h1>.
    2. TÍTULO (H1): "Horóscopo del día: {fecha_hoy}"
    3. INTRO (H2): "Energía Cósmica de Hoy" (Breve resumen planetario).
    4. SIGNOS: Escribe un párrafo para CADA UNO de los 12 signos usando <h3> para el nombre del signo (con su emoji) y <p> para la predicción.
       Orden: Aries, Tauro, Géminis, Cáncer, Leo, Virgo, Libra, Escorpio, Sagitario, Capricornio, Acuario, Piscis.
    5. TONO: Místico, inspirador y útil.
    6. IDIOMA: Español Neutro.
    """

    for modelo in modelos:
        texto = llamar_api_directa(modelo, prompt)
        if texto: return texto
        time.sleep(1)
    return None

def limpiar_respuesta(texto):
    """Elimina saludos de la IA y extrae el título."""
    texto = texto.replace('```html', '').replace('```', '').replace('<!DOCTYPE html>', '').strip()
    
    # Si la IA empieza saludando, buscamos donde empieza el primer <h1>
    if "<h1>" in texto:
        inicio = texto.find("<h1>")
        texto = texto[inicio:] # Cortamos todo lo que esté antes del H1

    titulo_match = re.search(r'<h1>(.*?)</h1>', texto, re.IGNORECASE)
    if titulo_match:
        titulo = titulo_match.group(1).strip()
        cuerpo = re.sub(r'<h1>.*?</h1>', '', texto, count=1, flags=re.IGNORECASE).strip()
    else:
        titulo = f"Horóscopo del día"
        cuerpo = texto
        
    return titulo, cuerpo

def main():
    fecha_hoy = obtener_fecha_en_espanol()
    print(f"--- GENERANDO HORÓSCOPO PARA: {fecha_hoy} ---")

    texto_ia = generar_horoscopo_ia(fecha_hoy)

    if not texto_ia:
        print("❌ Falló la generación.")
        return

    # Limpieza inteligente
    titulo_final, cuerpo_final = limpiar_respuesta(texto_ia)
    
    # Asegurar fecha correcta en el título si la IA falló
    if len(titulo_final) < 5 or "DOCTYPE" in titulo_final:
        titulo_final = f"Horóscopo de hoy: {fecha_hoy}"

    # Diseño HTML Místico
    html_final = f"""
    <div style="font-family: 'Georgia', serif; font-size: 18px; line-height: 1.7; color: #2c3e50; max-width: 800px; margin: auto;">
        
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 15px; text-align: center; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <p style="text-transform: uppercase; letter-spacing: 2px; font-size: 14px; margin: 0; opacity: 0.8;">Astrología Diaria</p>
            <h2 style="font-size: 36px; margin: 10px 0; font-family: sans-serif;">Los Astros Hoy</h2>
            <div style="font-size: 20px; font-weight: 300; margin-top: 5px;">{fecha_hoy}</div>
        </div>

        <div class="contenido-horoscopo" style="background: white; padding: 10px;">
            {cuerpo_final}
        </div>

        <div style="margin-top: 40px; padding: 20px; background: #f8f9fa; border-left: 4px solid #764ba2; font-size: 14px; color: #666; text-align: center;">
            ✨ <em>"Los astros inclinan, pero no obligan."</em> ✨
        </div>
    </div>
    """

    # Publicar
    print(f"Publicando: {titulo_final}")
    auth = (WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    post = {
        'title': titulo_final, 
        'content': html_final, 
        'status': 'draft'
    }
    r = requests.post(f"{WORDPRESS_URL}/wp-json/wp/v2/posts", json=post, auth=auth)
    
    if r.status_code == 201:
        print("✅ ÉXITO: Horóscopo publicado.")
    else:
        print(f"❌ Error WP: {r.text}")

if __name__ == "__main__":
    main()

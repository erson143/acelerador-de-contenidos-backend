# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v2.0
# Este archivo es el cerebro de tu aplicación. Se instala en Google Cloud
# y se encarga de todo el trabajo pesado de forma segura.
# -----------------------------------------------------------------------------

# --- Importaciones de Librerías ---
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import yt_dlp
import os
import sys
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

# --- CONFIGURACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)
# Habilita CORS para permitir que tu frontend en Hostinger se comunique con este backend.
CORS(app) 

# --- CONFIGURACIÓN DE LA API KEY (SEGURA) ---
# El backend ahora lee la API Key directamente de las variables de entorno seguras de Google Cloud.
# Ya no se pide al usuario.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    # Si la clave no se encuentra, el servidor registrará un error crítico al arrancar.
    print("ERROR CRÍTICO: La variable de entorno GEMINI_API_KEY no fue encontrada.", file=sys.stderr)

# --- PROMPTS MAESTROS ---
# (Estos prompts se mantienen igual, son el "cerebro creativo" de la IA)
PROMPT_PARA_AUDIO = """
Actúa como un experto estratega de marketing de contenidos de Forteza11. Tu primera tarea es transcribir el audio proporcionado con máxima precisión. Una vez transcrito, analiza el texto y transfórmalo en las siguientes piezas de contenido:

1.  **Transcripción Completa:** El texto completo del audio.
2.  **Resumen Ejecutivo (50-100 palabras):** Un resumen potente de la esencia del video.
3.  **Puntos Clave | Insights Estratégicos (Lista):** 5-7 ideas o "insights" accionables del video.
4.  **Publicación para Blog/Artículo (300-400 palabras):** Un borrador para blog expandiendo las ideas principales.
5.  **Guion para Short/Reel/TikTok:** Un guion breve y dinámico para video vertical.
6.  **Hilo para Twitter/X (3-5 tweets):** Un hilo para generar conversación.
7.  **Sugerencias de Títulos Optimizados:** 5 títulos alternativos para el video.
"""

PROMPT_PARA_TEXTO = """
Actúa como un experto estratega de marketing de contenidos de Forteza11. Analiza la siguiente transcripción de un video de YouTube y transfórmala en estas piezas de contenido:

1.  **Resumen Ejecutivo (50-100 palabras):** Un resumen potente de la esencia del video.
2.  **Puntos Clave | Insights Estratégicos (Lista):** 5-7 ideas o "insights" accionables del video.
3.  **Publicación para Blog/Artículo (300-400 palabras):** Un borrador para blog expandiendo las ideas principales.
4.  **Guion para Short/Reel/TikTok:** Un guion breve y dinámico para video vertical.
5.  **Hilo para Twitter/X (3-5 tweets):** Un hilo para generar conversación.
6.  **Sugerencias de Títulos Optimizados:** 5 títulos alternativos para el video.

Aquí está la transcripción:
---
{transcript_text}
---
"""

# --- FUNCIONES LÓGICAS DEL BACKEND ---

def obtener_id_video(url):
    try:
        if 'youtu.be' in url: return url.split('/')[-1].split('?')[0]
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get('v', [None])[0]
    except Exception: return None

def descargar_audio_youtube(url):
    print(f"⚙️ Motor Principal: Intentando descargar audio de: {url}...")
    try:
        opciones = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'outtmpl': '/tmp/audio_descargado.%(ext)s', 'quiet': True, 'ignoreerrors': True, 'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(opciones) as ydl: ydl.download([url])
        ruta_audio = "/tmp/audio_descargado.mp3"
        if os.path.exists(ruta_audio):
            print(f"✅ Motor Principal: Audio descargado exitosamente.")
            return ruta_audio
        else:
            raise FileNotFoundError("El archivo de audio no se creó.")
    except Exception as e:
        print(f"⚠️ Motor Principal: Falló la descarga de audio. ({e})")
        return None

def obtener_transcripcion_api(video_id, idioma='es'):
    print(f"⚙️ Motor de Respaldo: Intentando obtener subtítulos para el video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[idioma])
        transcript_text = " ".join([item['text'] for item in transcript_list])
        print("✅ Motor de Respaldo: Subtítulos obtenidos exitosamente.")
        return transcript_text
    except Exception as e:
        print(f"⚠️ Motor de Respaldo: No se encontraron subtítulos. ({e})")
        return None

def generar_contenido_ia(prompt, media=None):
    if not GEMINI_API_KEY:
        raise ValueError("La API Key de Gemini no está configurada en el servidor.")
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("🤖 Enviando información a la IA de Gemini para su análisis...")
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        
        args = [prompt]
        if media:
            if isinstance(media, str) and os.path.exists(media):
                print("🤖 Subiendo archivo de audio a la API de Gemini...")
                audio_file = genai.upload_file(path=media)
                args.append(audio_file)
            else: 
                args[0] = prompt.format(transcript_text=media)

        response = model.generate_content(args)
        print("🎉 ¡Contenido generado exitosamente!")
        return response.text
    except Exception as e:
        print(f"❌ Ocurrió un error al contactar con la API de Gemini: {e}")
        raise e
    finally:
        if media and isinstance(media, str) and os.path.exists(media):
            os.remove(media)
            print(f"🗑️ Archivo temporal '{media}' eliminado.")


# --- EL ENDPOINT PRINCIPAL DE LA API ---
# Esta es la única "puerta de entrada" que el frontend puede usar.
@app.route('/process_video', methods=['POST'])
def handle_generation():
    # El backend ahora NO espera una API Key del cliente.
    data = request.json
    youtube_url = data.get('video_url')
    
    if not youtube_url:
        return jsonify({"error": "Falta la URL del video."}), 400

    video_id = obtener_id_video(youtube_url)
    if not video_id:
        return jsonify({"error": "La URL del video no es válida."}), 400

    contenido_generado = None
    
    # Intento 1: Motor Principal (Audio)
    ruta_audio = descargar_audio_youtube(youtube_url)
    if ruta_audio:
        try:
            contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=ruta_audio)
        except Exception as e:
            print(f"Error en el motor principal con Gemini: {e}")
            contenido_generado = None

    # Intento 2: Motor de Respaldo (Subtítulos), si el primero falla
    if not contenido_generado:
        print("\n🔄 Conmutando al motor de respaldo...")
        texto_transcripcion = obtener_transcripcion_api(video_id)
        if texto_transcripcion:
            try:
                contenido_generado = generar_contenido_ia(PROMPT_PARA_TEXTO, media=texto_transcripcion)
            except Exception as e:
                return jsonify({"error": f"Error contactando a Gemini con el motor de respaldo: {e}"}), 500

    if contenido_generado:
        # Se devuelve el contenido en un formato JSON claro
        return jsonify({"contenido_generado": contenido_generado})
    else:
        return jsonify({"error": "Fallo Crítico: No se pudo procesar el video. Puede que sea privado, no tenga audio o subtítulos disponibles."}), 500

# --- FUNCIÓN DE INICIO ---
if __name__ == '__main__':
    # El puerto se obtiene de la variable de entorno PORT, que Google Cloud Run asigna automáticamente.
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL)
# Este archivo es el cerebro de tu aplicación. Se instala en tu servidor
# y se encarga de todo el trabajo pesado, eliminando los errores que vimos.
# -----------------------------------------------------------------------------

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import yt_dlp
import os
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs

# --- CONFIGURACIÓN DE LA APLICACIÓN FLASK ---
app = Flask(__name__)
CORS(app) # Permite que el frontend se comunique con este backend

# --- PROMPTS MAESTROS (CENTRALIZADOS EN EL BACKEND) ---
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
            'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'},
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

def generar_contenido_ia(api_key, prompt, media=None):
    try:
        genai.configure(api_key=api_key, client_options={"api_endpoint": "generativelanguage.googleapis.com"})
        print("🤖 Enviando información a la IA de Gemini para su análisis...")
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        args = [prompt]
        if media:
            if isinstance(media, str) and os.path.exists(media): # Es una ruta de archivo
                 print("🤖 Subiendo archivo de audio a la API de Gemini...")
                 audio_file = genai.upload_file(path=media)
                 args.append(audio_file)
            else: # Es texto
                 args[0] = prompt.format(transcript_text=media)

        response = model.generate_content(args)
        print("🎉 ¡Contenido generado exitosamente!")
        return response.text
    except Exception as e:
        print(f"❌ Ocurrió un error al contactar con la API de Gemini: {e}")
        raise e # Relanzamos el error para que el endpoint lo capture
    finally:
        if media and isinstance(media, str) and os.path.exists(media):
            os.remove(media)
            print(f"🗑️ Archivo temporal '{media}' eliminado.")


# --- EL ENDPOINT PRINCIPAL DE LA API ---
@app.route('/api/generate', methods=['POST'])
def handle_generation():
    data = request.json
    api_key = data.get('apiKey')
    youtube_url = data.get('videoUrl')
    
    if not api_key or not youtube_url:
        return jsonify({"error": "Faltan la API Key y/o la URL del video."}), 400

    video_id = obtener_id_video(youtube_url)
    if not video_id:
        return jsonify({"error": "La URL del video no es válida."}), 400

    contenido_generado = None
    
    # Intento 1: Motor Principal (Audio)
    ruta_audio = descargar_audio_youtube(youtube_url)
    if ruta_audio:
        try:
            contenido_generado = generar_contenido_ia(api_key, PROMPT_PARA_AUDIO, media=ruta_audio)
        except Exception as e:
            print(f"Error en el motor principal con Gemini: {e}")
            contenido_generado = None # Aseguramos que se intente el fallback

    # Intento 2: Motor de Respaldo (Subtítulos), si el primero falla
    if not contenido_generado:
        print("\n🔄 Conmutando al motor de respaldo...")
        texto_transcripcion = obtener_transcripcion_api(video_id)
        if texto_transcripcion:
            try:
                contenido_generado = generar_contenido_ia(api_key, PROMPT_PARA_TEXTO, media=texto_transcripcion)
            except Exception as e:
                 return jsonify({"error": f"Error contactando a Gemini con el motor de respaldo: {e}"}), 500

    if contenido_generado:
        return jsonify({"content": contenido_generado})
    else:
        return jsonify({"error": "Fallo Crítico: No se pudo procesar el video con ninguno de los dos motores. El video podría no tener audio, no tener subtítulos, ser privado o estar restringido."}), 500

# --- FUNCIÓN DE INICIO (PARA HOSTINGER) ---
def main():
    # Esta función es para pruebas locales. Hostinger usará el objeto 'app'.
    app.run(debug=True)

if __name__ == '__main__':
    main()
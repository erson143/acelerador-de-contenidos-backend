# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v3.3 - Solución Final CORS
# -----------------------------------------------------------------------------

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import yt_dlp
import os
import sys
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename

app = Flask(__name__)

# CONFIGURACIÓN DE CORS REFORZADA:
# Esta configuración es la correcta. La librería manejará las peticiones OPTIONS automáticamente.
CORS(app, resources={
  r"/process_video": {"origins": "https://ia.forteza11.com"},
  r"/process_audio": {"origins": "https://ia.forteza11.com"}
})

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("ERROR CRÍTICO: La variable de entorno GEMINI_API_KEY no fue encontrada.", file=sys.stderr)

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
        opciones = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'outtmpl': '/tmp/audio_descargado.%(ext)s', 'quiet': True, 'ignoreerrors': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(opciones) as ydl: ydl.download([url])
        ruta_audio = "/tmp/audio_descargado.mp3"
        if os.path.exists(ruta_audio):
            print(f"✅ Motor Principal: Audio descargado exitosamente.")
            return ruta_audio
        else: raise FileNotFoundError("El archivo de audio no se creó.")
    except Exception as e:
        print(f"⚠️ Motor Principal: Falló la descarga de audio. ({e})")
        return None

def obtener_transcripcion_api(video_id, idioma='es'):
    print(f"⚙️ Motor de Respaldo: Intentando obtener subtítulos para video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[idioma])
        transcript_text = " ".join([item['text'] for item in transcript_list])
        print("✅ Motor de Respaldo: Subtítulos obtenidos exitosamente.")
        return transcript_text
    except Exception as e:
        print(f"⚠️ Motor de Respaldo: No se encontraron subtítulos. ({e})")
        return None

def generar_contenido_ia(prompt, media=None):
    if not GEMINI_API_KEY: raise ValueError("La API Key de Gemini no está configurada en el servidor.")
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
            else: args[0] = prompt.format(transcript_text=media)
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

# --- ENDPOINTS DE LA API ---
@app.route('/process_video', methods=['POST', 'OPTIONS'])
def handle_video_generation():
    # La línea 'if request.method == 'OPTIONS'' ha sido ELIMINADA. Flask-CORS lo maneja.
    data = request.json
    youtube_url = data.get('video_url')
    if not youtube_url: return jsonify({"error": "Falta la URL del video."}), 400
    video_id = obtener_id_video(youtube_url)
    if not video_id: return jsonify({"error": "La URL del video no es válida."}), 400
    contenido_generado = None
    ruta_audio = descargar_audio_youtube(youtube_url)
    if ruta_audio:
        try: contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=ruta_audio)
        except Exception as e:
            print(f"Error en el motor principal con Gemini: {e}")
            contenido_generado = None
    if not contenido_generado:
        print("\n🔄 Conmutando al motor de respaldo...")
        texto_transcripcion = obtener_transcripcion_api(video_id)
        if texto_transcripcion:
            try: contenido_generado = generar_contenido_ia(PROMPT_PARA_TEXTO, media=texto_transcripcion)
            except Exception as e: return jsonify({"error": f"Error contactando a Gemini con el motor de respaldo: {e}"}), 500
    if contenido_generado: return jsonify({"contenido_generado": contenido_generado})
    else: return jsonify({"error": "Fallo Crítico: No se pudo procesar el video. Puede que sea privado, no tenga audio o subtítulos disponibles."}), 500

@app.route('/process_audio', methods=['POST', 'OPTIONS'])
def handle_audio_generation():
    # La línea 'if request.method == 'OPTIONS'' ha sido ELIMINADA. Flask-CORS lo maneja.
    if 'audio_file' not in request.files: return jsonify({"error": "No se encontró el archivo de audio en la solicitud."}), 400
    file = request.files['audio_file']
    if file.filename == '': return jsonify({"error": "No se seleccionó ningún archivo."}), 400
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join('/tmp', filename)
        file.save(filepath)
        print(f"⚙️ Archivo de audio '{filename}' recibido y guardado temporalmente.")
        try:
            contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=filepath)
            if contenido_generado: return jsonify({"contenido_generado": contenido_generado})
            else: return jsonify({"error": "La IA no pudo generar contenido a partir del audio."}), 500
        except Exception as e: return jsonify({"error": f"Ocurrió un error al procesar el archivo con la IA: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v5.0 - Escalabilidad Total
# -----------------------------------------------------------------------------
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import yt_dlp
import os
import sys
import datetime
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename
from google.cloud import storage # <-- Nueva librería

app = Flask(__name__)
CORS(app, origins="*")

# --- CONFIGURACIÓN ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
# IMPORTANTE: Reemplaza con el nombre exacto de tu bucket
GCS_BUCKET_NAME = 'forteza11-audio-uploads' 

if not GEMINI_API_KEY:
    print("ERROR CRÍTICO: GEMINI_API_KEY no fue encontrada.", file=sys.stderr)

# ... (TODOS LOS PROMPTS Y FUNCIONES AUXILIARES COMO obtener_id_video, etc., se mantienen igual que antes) ...
PROMPT_PARA_AUDIO = """...""" # (Mantener el mismo prompt de antes)
PROMPT_PARA_TEXTO = """...""" # (Mantener el mismo prompt de antes)
def obtener_id_video(url):
    # (Mantener la misma función de antes)
    try:
        if 'youtu.be' in url: return url.split('/')[-1].split('?')[0]
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get('v', [None])[0]
    except Exception: return None

def descargar_audio_youtube(url):
    # (Mantener la misma función de antes)
    print(f"⚙️ Motor Principal: Intentando descargar audio de: {url}...")
    try:
        opciones = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'outtmpl': '/tmp/audio_descargado.%(ext)s', 'quiet': True, 'ignoreerrors': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(opciones) as ydl: ydl.download([url])
        ruta_audio = "/tmp/audio_descargado.mp3"
        if os.path.exists(ruta_audio): return ruta_audio
        else: raise FileNotFoundError("El archivo de audio no se creó.")
    except Exception as e:
        print(f"⚠️ Motor Principal: Falló la descarga de audio. ({e})")
        return None

def obtener_transcripcion_api(video_id, idioma='es'):
    # (Mantener la misma función de antes)
    print(f"⚙️ Motor de Respaldo: Intentando obtener subtítulos para video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[idioma])
        return " ".join([item['text'] for item in transcript_list])
    except Exception as e:
        print(f"⚠️ Motor de Respaldo: No se encontraron subtítulos. ({e})")
        return None

def generar_contenido_ia(prompt, media=None):
    # (Mantener la misma función de antes)
    if not GEMINI_API_KEY: raise ValueError("La API Key de Gemini no está configurada en el servidor.")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        args = [prompt]
        if media:
            if isinstance(media, str) and os.path.exists(media):
                audio_file = genai.upload_file(path=media)
                args.append(audio_file)
            else: args[0] = prompt.format(transcript_text=media)
        response = model.generate_content(args)
        return response.text
    except Exception as e:
        print(f"❌ Ocurrió un error al contactar con la API de Gemini: {e}")
        raise e
    finally:
        if media and isinstance(media, str) and os.path.exists(media):
            os.remove(media)

# --- NUEVO ENDPOINT PARA GENERAR URL DE SUBIDA ---
@app.route('/generate_upload_url', methods=['POST', 'OPTIONS'])
def generate_upload_url():
    if request.method == 'OPTIONS': return '', 204

    data = request.json
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "Falta el nombre del archivo."}), 400

    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(secure_filename(filename))

    # Genera una URL segura que permite al frontend subir un archivo durante 15 minutos
    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        content_type=request.json.get('contentType', 'application/octet-stream')
    )
    return jsonify({"signed_url": url, "gcs_filename": blob.name})

# --- ENDPOINT DE PROCESAMIENTO DE AUDIO MODIFICADO ---
@app.route('/process_audio', methods=['POST', 'OPTIONS'])
def handle_audio_generation():
    if request.method == 'OPTIONS': return '', 204

    data = request.json
    gcs_filename = data.get('gcs_filename')
    if not gcs_filename:
        return jsonify({"error": "Falta el nombre del archivo en Google Cloud Storage."}), 400

    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_filename)

    # Descarga el archivo desde GCS al entorno temporal de Cloud Run
    filepath = os.path.join('/tmp', gcs_filename)
    blob.download_to_filename(filepath)
    print(f"⚙️ Archivo '{gcs_filename}' descargado de GCS para procesamiento.")

    try:
        contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=filepath)
        # Borra el archivo de GCS después de procesarlo para ahorrar espacio
        blob.delete()
        print(f"🗑️ Archivo '{gcs_filename}' eliminado de Google Cloud Storage.")

        if contenido_generado:
            return jsonify({"contenido_generado": contenido_generado})
        else:
            return jsonify({"error": "La IA no pudo generar contenido a partir del audio."}), 500
    except Exception as e:
        return jsonify({"error": f"Ocurrió un error al procesar el archivo con la IA: {e}"}), 500

# ... (El endpoint /process_video se mantiene igual) ...
@app.route('/process_video', methods=['POST', 'OPTIONS'])
def handle_video_generation():
    if request.method == 'OPTIONS': return '', 204
    # (Mantener la misma función de antes)
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
    else: return jsonify({"error": "Fallo Crítico: No se pudo procesar el video."}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

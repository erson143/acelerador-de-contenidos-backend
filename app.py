# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v7.0 - Corrección Final
# -----------------------------------------------------------------------------
# Esta versión corrige un error de tipeo en la llamada a la función
# 'get_transcript' de la librería YouTubeTranscriptApi.
# -----------------------------------------------------------------------------
import flask, google.generativeai as genai, yt_dlp, os, sys, datetime, json
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename
from google.cloud import storage
from google.cloud.secretmanager_v1 import SecretManagerServiceClient
from google.oauth2 import service_account
from flask_cors import CORS

app = flask.Flask(__name__)
CORS(app)

print("✅ INICIANDO ARRANQUE v7.0 (Listo para recibir peticiones)...", file=sys.stderr)
sys.stderr.flush()

# --- CONFIGURACIÓN GLOBAL Y CACHE PARA CREDENCIALES ---
PROJECT_ID = os.environ.get('GCP_PROJECT')
GCS_BUCKET_NAME = 'forteza11-audio-uploads'
storage_credentials = None
gemini_key_loaded = False

# --- FUNCIÓN DE CARGA DE CREDENCIALES "JUST-IN-TIME" ---
def load_credentials_if_needed():
    global storage_credentials, gemini_key_loaded
    if storage_credentials and gemini_key_loaded:
        return True
    
    print("⚙️ Detectada primera petición. Cargando credenciales...", file=sys.stderr)
    try:
        client = SecretManagerServiceClient()
        
        if not gemini_key_loaded:
            print("  -> Cargando GEMINI_API_KEY...", file=sys.stderr)
            name = f"projects/{PROJECT_ID}/secrets/GEMINI_API_KEY/versions/latest"
            response = client.access_secret_version(name=name)
            gemini_key = response.payload.data.decode("UTF-8")
            genai.configure(api_key=gemini_key)
            gemini_key_loaded = True
            print("  ✅ Credenciales de Gemini cargadas.")

        if not storage_credentials:
            print("  -> Cargando gcs-service-account-key...", file=sys.stderr)
            name = f"projects/{PROJECT_ID}/secrets/gcs-service-account-key/versions/latest"
            response = client.access_secret_version(name=name)
            key_json = json.loads(response.payload.data.decode("UTF-8"))
            storage_credentials = service_account.Credentials.from_service_account_info(key_json)
            print("  ✅ Credenciales de Storage cargadas.")
        
        print("🎉 Credenciales listas.", file=sys.stderr)
        return True
    except Exception as e:
        print(f"❌ ERROR CRÍTICO AL CARGAR CREDENCIALES: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False

# --- PROMPTS Y FUNCIONES AUXILIARES ---
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
        query = urlparse(url).query; params = parse_qs(query)
        return params.get('v', [None])[0]
    except Exception: return None

def descargar_audio_youtube(url):
    print("  -> Intentando descargar audio con yt-dlp...", file=sys.stderr)
    try:
        opciones = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'outtmpl': '/tmp/audio_descargado.%(ext)s', 'quiet': True, 'ignoreerrors': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(opciones) as ydl: ydl.download([url])
        ruta_audio = "/tmp/audio_descargado.mp3"
        if os.path.exists(ruta_audio):
            print("  ✅ Audio descargado exitosamente.", file=sys.stderr)
            return ruta_audio
        else:
            raise FileNotFoundError("El archivo de audio no se creó.")
    except Exception as e:
        print(f"  ⚠️ Fallo al descargar audio: {e}", file=sys.stderr)
        return None

def obtener_transcripcion_api(video_id):
    print("  -> Intentando obtener transcripción con API...", file=sys.stderr)
    try:
        # ------------------- ¡AQUÍ ESTABA EL ERROR! -------------------
        # CORREGIDO: la función se llama get_transcript, no get_transcription
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['es', 'es-419'])
        # -----------------------------------------------------------------
        texto = " ".join([item['text'] for item in transcript_list])
        print("  ✅ Transcripción obtenida exitosamente.", file=sys.stderr)
        return texto
    except (TranscriptsDisabled, NoTranscriptFound):
        print("  ⚠️ Transcripción no disponible para este video.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ⚠️ Error inesperado en la API de transcripción: {e}", file=sys.stderr)
        return None


def generar_contenido_ia(prompt, media=None):
    if not gemini_key_loaded: raise ValueError("La API Key de Gemini no está configurada.")
    print("  -> Generando contenido con la IA de Gemini...", file=sys.stderr)
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        args = [prompt]
        if media and isinstance(media, str) and os.path.exists(media):
            audio_file = genai.upload_file(path=media)
            args.append(audio_file)
        elif media: 
            args[0] = prompt.format(transcript_text=media)
        response = model.generate_content(args)
        print("  ✅ Contenido generado exitosamente.", file=sys.stderr)
        return response.text
    finally:
        if media and isinstance(media, str) and os.path.exists(media):
            os.remove(media)

# --- ENDPOINTS DE LA API (Sin Cambios) ---
@app.route('/generate_upload_url', methods=['POST'])
def generate_upload_url():
    if not load_credentials_if_needed(): return flask.jsonify({"error": "Las credenciales del servidor no se pudieron cargar."}), 500
    data = flask.request.json
    filename = data.get('filename')
    if not filename: return flask.jsonify({"error": "Falta el nombre del archivo."}), 400
    storage_client = storage.Client(credentials=storage_credentials)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(secure_filename(filename))
    url = blob.generate_signed_url(version="v4", expiration=datetime.timedelta(minutes=15), method="PUT", content_type=flask.request.json.get('contentType', 'application/octet-stream'))
    return flask.jsonify({"signed_url": url, "gcs_filename": blob.name})

@app.route('/process_audio', methods=['POST'])
def handle_audio_generation():
    if not load_credentials_if_needed(): return flask.jsonify({"error": "Las credenciales del servidor no se pudieron cargar."}), 500
    data = flask.request.json
    gcs_filename = data.get('gcs_filename')
    if not gcs_filename: return flask.jsonify({"error": "Falta el nombre del archivo en GCS."}), 400
    storage_client = storage.Client(credentials=storage_credentials)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_filename)
    filepath = os.path.join('/tmp', gcs_filename)
    blob.download_to_filename(filepath)
    try:
        contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=filepath)
        blob.delete()
        if contenido_generado: return flask.jsonify({"contenido_gen erado": contenido_generado})
        else: return flask.jsonify({"error": "La IA no pudo generar contenido."}), 500
    except Exception as e: return flask.jsonify({"error": f"Error al procesar con IA: {e}"}), 500

# --- ENDPOINT DE VIDEO MEJORADO ---
@app.route('/process_video', methods=['POST'])
def handle_video_generation():
    if not load_credentials_if_needed(): return flask.jsonify({"error": "Credenciales del servidor no cargadas."}), 500

    data = flask.request.json
    youtube_url = data.get('video_url')
    if not youtube_url: return flask.jsonify({"error": "Falta la URL del video."}), 400
    
    video_id = obtener_id_video(youtube_url)
    if not video_id: return flask.jsonify({"error": "La URL del video no es válida."}), 400
    
    print(f"Procesando video ID: {video_id}")
    contenido_generado = None
    
    # --- MÉTODO 1: API DE TRANSCRIPCIÓN (Ahora es el principal) ---
    texto_transcripcion = obtener_transcripcion_api(video_id)
    if texto_transcripcion:
        try:
            contenido_generado = generar_contenido_ia(PROMPT_PARA_TEXTO, media=texto_transcripcion)
        except Exception as e:
            print(f"  ❌ Fallo al generar contenido desde la transcripción: {e}", file=sys.stderr)
            contenido_generado = None
    
    # --- MÉTODO 2: DESCARGA DE AUDIO (Plan B, si el primero falla) ---
    if not contenido_generado:
        print("Plan A (API de transcripción) falló. Intentando Plan B (Descarga de audio).")
        ruta_audio = descargar_audio_youtube(youtube_url)
        if ruta_audio:
            try: 
                contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=ruta_audio)
            except Exception as e:
                print(f"  ❌ Fallo al generar contenido desde el audio: {e}", file=sys.stderr)

    # --- RESULTADO FINAL ---
    if contenido_generado:
        print("✅ Proceso completado con éxito.")
        return flask.jsonify({"contenido_generado": contenido_generado})
    else:
        print("❌ Fallaron todos los métodos. No se pudo procesar el video.")
        return flask.jsonify({"error": "No se pudo obtener la transcripción ni el audio para este video. Por favor, intenta con otro."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))


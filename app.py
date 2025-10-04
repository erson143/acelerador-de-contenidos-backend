# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v6.1 - Solución Final y Definitiva
# -----------------------------------------------------------------------------
import flask, google.generativeai as genai, yt_dlp, os, sys, datetime, json
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename
from google.cloud import storage, secretmanager
from google.oauth2 import service_account

app = flask.Flask(__name__)

# CONFIGURACIÓN DE CORS CORRECTA:
from flask_cors import CORS
CORS(app, resources={
  r"/process_video": {"origins": "https://ia.forteza11.com"},
  r"/process_audio": {"origins": "https://ia.forteza11.com"},
  r"/generate_upload_url": {"origins": "https://ia.forteza11.com"}
})

# --- CONFIGURACIÓN DE CREDENCIALES (Se mantiene igual) ---
PROJECT_ID = os.environ.get('GCP_PROJECT')
GCS_BUCKET_NAME = 'forteza11-audio-uploads'
storage_credentials = None
try:
    client = secretmanager.SecretManagerServiceClient()
    # Cargar Gemini Key
    name = f"projects/{PROJECT_ID}/secrets/GEMINI_API_KEY/versions/latest"
    response = client.access_secret_version(name=name)
    genai.configure(api_key=response.payload.data.decode("UTF-8"))
    print("✅ Credenciales de Gemini cargadas.")
    # Cargar GCS Key
    name = f"projects/{PROJECT_ID}/secrets/gcs-service-account-key/versions/latest"
    response = client.access_secret_version(name=name)
    key_json = json.loads(response.payload.data.decode("UTF-8"))
    storage_credentials = service_account.Credentials.from_service_account_info(key_json)
    print("✅ Credenciales de Storage cargadas.")
except Exception as e:
    print(f"❌ ERROR CRÍTICO AL CARGAR CREDENCIALES: {e}", file=sys.stderr)

# --- PROMPTS Y FUNCIONES AUXILIARES (Se mantienen igual) ---
PROMPT_PARA_AUDIO = """...""" # Mantener el mismo prompt de antes
PROMPT_PARA_TEXTO = """...""" # Mantener el mismo prompt de antes
def obtener_id_video(url):
    try:
        if 'youtu.be' in url: return url.split('/')[-1].split('?')[0]
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get('v', [None])[0]
    except Exception: return None
def descargar_audio_youtube(url):
    try:
        opciones = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'outtmpl': '/tmp/audio_descargado.%(ext)s', 'quiet': True, 'ignoreerrors': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(opciones) as ydl: ydl.download([url])
        ruta_audio = "/tmp/audio_descargado.mp3"
        if os.path.exists(ruta_audio): return ruta_audio
        else: raise FileNotFoundError("El archivo de audio no se creó.")
    except Exception: return None
def obtener_transcripcion_api(video_id, idioma='es'):
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[idioma])
        return " ".join([item['text'] for item in transcript_list])
    except Exception: return None
def generar_contenido_ia(prompt, media=None):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        args = [prompt]
        if media:
            if isinstance(media, str) and os.path.exists(media):
                audio_file = genai.upload_file(path=media)
                args.append(audio_file)
            else: args[0] = prompt.format(transcript_text=media)
        response = model.generate_content(args)
        return response.text
    finally:
        if media and isinstance(media, str) and os.path.exists(media):
            os.remove(media)

# --- ENDPOINTS DE LA API (CORREGIDOS) ---
@app.route('/generate_upload_url', methods=['POST', 'OPTIONS'])
def generate_upload_url():
    # La línea 'if request.method == 'OPTIONS'' ha sido ELIMINADA.
    if not storage_credentials: return flask.jsonify({"error": "Las credenciales del servidor no están configuradas."}), 500
    data = flask.request.json
    filename = data.get('filename')
    if not filename: return flask.jsonify({"error": "Falta el nombre del archivo."}), 400
    storage_client = storage.Client(credentials=storage_credentials, project=PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(secure_filename(filename))
    url = blob.generate_signed_url(version="v4", expiration=datetime.timedelta(minutes=15), method="PUT", content_type=flask.request.json.get('contentType', 'application/octet-stream'))
    return flask.jsonify({"signed_url": url, "gcs_filename": blob.name})

@app.route('/process_audio', methods=['POST', 'OPTIONS'])
def handle_audio_generation():
    # La línea 'if request.method == 'OPTIONS'' ha sido ELIMINADA.
    data = flask.request.json
    gcs_filename = data.get('gcs_filename')
    if not gcs_filename: return flask.jsonify({"error": "Falta el nombre del archivo en GCS."}), 400
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(gcs_filename)
    filepath = os.path.join('/tmp', gcs_filename)
    blob.download_to_filename(filepath)
    try:
        contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=filepath)
        blob.delete()
        if contenido_generado: return flask.jsonify({"contenido_generado": contenido_generado})
        else: return flask.jsonify({"error": "La IA no pudo generar contenido."}), 500
    except Exception as e: return flask.jsonify({"error": f"Error al procesar con IA: {e}"}), 500

@app.route('/process_video', methods=['POST', 'OPTIONS'])
def handle_video_generation():
    # La línea 'if request.method == 'OPTIONS'' ha sido ELIMINADA.
    data = flask.request.json
    youtube_url = data.get('video_url')
    if not youtube_url: return flask.jsonify({"error": "Falta la URL del video."}), 400
    video_id = obtener_id_video(youtube_url)
    if not video_id: return flask.jsonify({"error": "La URL del video no es válida."}), 400
    contenido_generado = None
    ruta_audio = descargar_audio_youtube(youtube_url)
    if ruta_audio:
        try: contenido_generado = generar_contenido_ia(PROMPT_PARA_AUDIO, media=ruta_audio)
        except Exception as e:
            print(f"Error en motor principal: {e}")
            contenido_generado = None
    if not contenido_generado:
        texto_transcripcion = obtener_transcripcion_api(video_id)
        if texto_transcripcion:
            try: contenido_generado = generar_contenido_ia(PROMPT_PARA_TEXTO, media=texto_transcripcion)
            except Exception as e: return flask.jsonify({"error": f"Error en motor de respaldo: {e}"}), 500
    if contenido_generado: return flask.jsonify({"contenido_generado": contenido_generado})
    else: return flask.jsonify({"error": "Fallo Crítico: No se pudo procesar el video."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

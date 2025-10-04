# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v10.0 - Versión "Tanque"
# -----------------------------------------------------------------------------
import flask, google.generativeai as genai, yt_dlp, os, sys, datetime, json
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename
from google.cloud import storage
from google.cloud.secretmanager_v1 import SecretManagerServiceClient
from google.oauth2 import service_account
from flask_cors import CORS

app = flask.Flask(__name__)
# Aplica CORS de la forma más abierta posible para eliminar esta variable.
CORS(app, resources={r"/*": {"origins": "*"}})

# --- BLOQUE DE ARRANQUE SIMPLIFICADO ---
print("✅ INICIANDO ARRANQUE v10.0...", file=sys.stderr)
PROJECT_ID = None
GCS_BUCKET_NAME = 'forteza11-audio-uploads'
storage_credentials = None
gemini_key_loaded = False

# --- PROMPTS Y FUNCIONES (Sin cambios, pero movidos arriba para claridad) ---
# ... (Pega aquí todos los PROMPTS y todas las funciones: obtener_id_video, descargar_audio_youtube, etc.)

# --- ENDPOINTS DE LA API ---
@app.route('/generate_upload_url', methods=['POST'])
def generate_upload_url():
    global storage_credentials, PROJECT_ID
    try:
        if not storage_credentials:
            print("⚙️ Cargando credenciales de Storage (just-in-time)...", file=sys.stderr)
            client = SecretManagerServiceClient()
            PROJECT_ID = os.environ.get('GCP_PROJECT')
            name = f"projects/{PROJECT_ID}/secrets/gcs-service-account-key/versions/latest"
            response = client.access_secret_version(name=name)
            key_json = json.loads(response.payload.data.decode("UTF-8"))
            storage_credentials = service_account.Credentials.from_service_account_info(key_json)
            print("✅ Credenciales de Storage cargadas.", file=sys.stderr)
        
        # ... (El resto de la función se mantiene igual)
        data = flask.request.json
        filename = data.get('filename')
        # ...

    except Exception as e:
        print(f"❌ ERROR en /generate_upload_url: {e}", file=sys.stderr)
        return flask.jsonify({"error": "Error interno del servidor al generar la URL."}), 500

@app.route('/process_audio', methods=['POST'])
def handle_audio_generation():
    global gemini_key_loaded
    try:
        if not gemini_key_loaded:
            print("⚙️ Cargando credenciales de Gemini (just-in-time)...", file=sys.stderr)
            client = SecretManagerServiceClient()
            PROJECT_ID = os.environ.get('GCP_PROJECT')
            name = f"projects/{PROJECT_ID}/secrets/GEMINI_API_KEY/versions/latest"
            response = client.access_secret_version(name=name)
            genai.configure(api_key=response.payload.data.decode("UTF-8"))
            gemini_key_loaded = True
            print("✅ Credenciales de Gemini cargadas.", file=sys.stderr)

        # ... (El resto de la función se mantiene igual)
        data = flask.request.json
        gcs_filename = data.get('gcs_filename')
        # ...

    except Exception as e:
        print(f"❌ ERROR en /process_audio: {e}", file=sys.stderr)
        return flask.jsonify({"error": "Error interno del servidor al procesar el audio."}), 500

@app.route('/process_video', methods=['POST'])
def handle_video_generation():
    global gemini_key_loaded
    try:
        if not gemini_key_loaded:
            print("⚙️ Cargando credenciales de Gemini (just-in-time)...", file=sys.stderr)
            client = SecretManagerServiceClient()
            PROJECT_ID = os.environ.get('GCP_PROJECT')
            name = f"projects/{PROJECT_ID}/secrets/GEMINI_API_KEY/versions/latest"
            response = client.access_secret_version(name=name)
            genai.configure(api_key=response.payload.data.decode("UTF-8"))
            gemini_key_loaded = True
            print("✅ Credenciales de Gemini cargadas.", file=sys.stderr)
            
        # ... (El resto de la función se mantiene igual)
        data = flask.request.json
        youtube_url = data.get('video_url')
        # ...

    except Exception as e:
        print(f"❌ ERROR en /process_video: {e}", file=sys.stderr)
        return flask.jsonify({"error": "Error interno del servidor al procesar el video."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))


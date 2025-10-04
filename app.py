# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v9.0 - Versión de Diagnóstico
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

# --- CAMBIO 1: La configuración de CORS más abierta y simple posible ---
CORS(app) 

# --- CAMBIO 2: El "espía" que registra CADA petición que llega ---
@app.before_request
def log_request_info():
    print('--- INCOMING REQUEST ---', file=sys.stderr)
    print(f"Method: {flask.request.method}", file=sys.stderr)
    print(f"Path: {flask.request.path}", file=sys.stderr)
    print(f"Origin Header: {flask.request.headers.get('Origin')}", file=sys.stderr)
    print('------------------------', file=sys.stderr)
    sys.stderr.flush()

# --- BLOQUE DE ARRANQUE Y CARGA DE CREDENCIALES (Sin cambios) ---
# ... (Este bloque se mantiene igual que en la v8.0)
PROJECT_ID = os.environ.get('GCP_PROJECT')
GCS_BUCKET_NAME = 'forteza11-audio-uploads'
storage_credentials = None
gemini_key_loaded = False

try:
    client = SecretManagerServiceClient()
    
    # Cargar Gemini Key
    name = f"projects/{PROJECT_ID}/secrets/GEMINI_API_KEY/versions/latest"
    response = client.access_secret_version(name=name)
    gemini_key = response.payload.data.decode("UTF-8")
    genai.configure(api_key=gemini_key)
    gemini_key_loaded = True
    print("✅ Credenciales de Gemini cargadas.", file=sys.stderr)

    # Cargar GCS Key
    name = f"projects/{PROJECT_ID}/secrets/gcs-service-account-key/versions/latest"
    response = client.access_secret_version(name=name)
    key_json = json.loads(response.payload.data.decode("UTF-8"))
    storage_credentials = service_account.Credentials.from_service_account_info(key_json)
    print("✅ Credenciales de Storage (notario) cargadas.", file=sys.stderr)
    
    print("🎉 ARRANQUE COMPLETADO CON ÉXITO.", file=sys.stderr)

except Exception as e:
    print(f"❌ ERROR CRÍTICO DURANTE EL ARRANQUE: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

sys.stderr.flush()
# --- FIN DEL BLOQUE DE ARRANQUE ---

# --- PROMPTS Y FUNCIONES (Sin Cambios) ---
PROMPT_PARA_AUDIO = """..."""
PROMPT_PARA_TEXTO = """..."""
def obtener_id_video(url):
    try:
        if 'youtu.be' in url: return url.split('/')[-1].split('?')[0]
        query = urlparse(url).query; params = parse_qs(query)
        return params.get('v', [None])[0]
    except Exception: return None
# ... (El resto de las funciones se mantienen exactamente igual)

# --- ENDPOINTS (Sin Cambios en la lógica interna) ---
@app.route('/generate_upload_url', methods=['POST', 'OPTIONS'])
def generate_upload_url():
    # ...
    
@app.route('/process_audio', methods=['POST', 'OPTIONS'])
def handle_audio_generation():
    # ...

@app.route('/process_video', methods=['POST', 'OPTIONS'])
def handle_video_generation():
    # ...

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))


# -----------------------------------------------------------------------------
# COMPONENTE 1: EL BACKEND (EL MOTOR CENTRAL) v7.2 - Solución Final 415
# -----------------------------------------------------------------------------
import flask, google.generativeai as genai, yt_dlp, os, sys, datetime, json
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from werkzeug.utils import secure_filename
from google.cloud import storage
from google.cloud.secretmanager import SecretManagerServiceClient
from google.oauth2 import service_account
from flask_cors import CORS

app = flask.Flask(__name__)
CORS(app)

# --- BLOQUE DE ARRANQUE Y CARGA DE CREDENCIALES (Sin cambios) ---
# ... (Todo el bloque de carga de credenciales se mantiene igual) ...
# ...
# --- ENDPOINTS DE LA API (CON LA CORRECCIÓN FINAL) ---

@app.route('/generate_upload_url', methods=['POST', 'OPTIONS'])
def generate_upload_url():
    # CORRECCIÓN: Maneja la petición de sondeo OPTIONS antes de procesar JSON.
    if flask.request.method == 'OPTIONS':
        return '', 204
    # ... (El resto de la función se mantiene igual)
    if not storage_credentials: return flask.jsonify({"error": "Las credenciales del servidor no están configuradas correctamente."}), 500
    data = flask.request.json
    filename = data.get('filename')
    if not filename: return flask.jsonify({"error": "Falta el nombre del archivo."}), 400
    storage_client = storage.Client(credentials=storage_credentials)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(secure_filename(filename))
    url = blob.generate_signed_url(version="v4", expiration=datetime.timedelta(minutes=15), method="PUT", content_type=flask.request.json.get('contentType', 'application/octet-stream'))
    return flask.jsonify({"signed_url": url, "gcs_filename": blob.name})

@app.route('/process_audio', methods=['POST', 'OPTIONS'])
def handle_audio_generation():
    # CORRECCIÓN: Maneja la petición de sondeo OPTIONS antes de procesar JSON.
    if flask.request.method == 'OPTIONS':
        return '', 204
    # ... (El resto de la función se mantiene igual)
    data = flask.request.json
    gcs_filename = data.get('gcs_filename')
    # ...

@app.route('/process_video', methods=['POST', 'OPTIONS'])
def handle_video_generation():
    # CORRECCIÓN: Maneja la petición de sondeo OPTIONS antes de procesar JSON.
    if flask.request.method == 'OPTIONS':
        return '', 204
    # ... (El resto de la función se mantiene igual)
    data = flask.request.json
    youtube_url = data.get('video_url')
    # ...

# (Aquí va el resto completo del archivo app.py que te di en el paso anterior)
# (Asegúrate de pegar todo el archivo, solo he mostrado las partes que se corrigen para explicarlo)

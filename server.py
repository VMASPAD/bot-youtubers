from flask import Flask, send_from_directory
import subprocess
import requests
import os
import random
from pathlib import Path
import time
app = Flask(__name__)

VIDEO_URL = "https://portfoliotavm.com/n8n/meme/video.mp4"
ROUTE_CLIP = "./clip/"
WHISPER_JSON = "./public/"

def download_video(url, destination_path):
    try:
        print(f"Descargando video desde: {url}")
        
        # Realizar la petición con streaming para archivos grandes
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Lanza excepción si hay error HTTP
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        # Escribir el archivo en chunks para manejar archivos grandes
        with open(destination_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        
        print(f"Video descargado exitosamente: {destination_path}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Error al descargar: {e}")
        return False

def get_video_duration(video_path):
    """
    Obtiene la duración del video en segundos usando ffprobe
    """
    try:
        result = subprocess.run([
            'ffprobe', 
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            print(f"Duración del video: {duration} segundos")
            return duration
        else:
            print(f"Error obteniendo duración: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_random_clip(input_video, output_clip, min_duration=30, max_duration=60):
    """
    Genera un clip aleatorio del video usando FFmpeg
    """
    try:
        # Obtener duración del video original
        total_duration = get_video_duration(input_video)
        if not total_duration:
            return False
        
        # Generar duración aleatoria del clip
        clip_duration = random.randint(min_duration, max_duration)
        
        # Calcular tiempo de inicio aleatorio
        # Asegurar que el clip no se salga del video
        max_start_time = total_duration - clip_duration
        if max_start_time <= 0:
            print(f"El video es muy corto. Duración: {total_duration}s, clip requerido: {clip_duration}s")
            # Si el video es más corto que el clip mínimo, usar todo el video
            start_time = 0
            clip_duration = min(total_duration, max_duration)
        else:
            start_time = random.uniform(0, max_start_time)
        
        print(f"Generando clip: inicio={start_time:.2f}s, duración={clip_duration}s")
        
        # Crear directorio de salida si no existe
        os.makedirs(os.path.dirname(output_clip), exist_ok=True)
        
        # Comando FFmpeg para extraer el clip
        command = [
            'ffmpeg',
            '-i', input_video,              # archivo de entrada
            '-ss', str(start_time),         # tiempo de inicio
            '-t', str(clip_duration),       # duración del clip
            '-vf', 'crop=ih*9/16:ih:(iw-ih*9/16)/2:0',  # filtro de crop 9:16 centrado
            '-c:v', 'libx264',              # codec de video
            '-c:a', 'aac',                  # codec de audio
            '-preset', 'fast',              # preset de codificación
            '-y',                           # sobrescribir archivo si existe
            output_clip                     # archivo de salida
        ]
        
        # Ejecutar comando
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Clip generado exitosamente: {output_clip}")
            return True
        else:
            print(f"Error generando clip: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False

@app.route('/generate-clip', methods=['POST'])
def generate_clip():
    """Genera un clip aleatorio del video especificado"""
    try:
        # Descargar el video si no existe localmente
        if not os.path.exists(VIDEO_PATH):
            print(f"Descargando video desde {VIDEO_URL}...")
            if not download_video(VIDEO_URL, VIDEO_PATH):
                return jsonify({"error": "No se pudo descargar el video"}), 500

        # Verificar que el archivo existe
        if not os.path.exists(VIDEO_PATH):
            return jsonify({"error": f"El archivo {VIDEO_PATH} no existe"}), 404
        
        # Verificar que es un archivo MP4
        if not VIDEO_PATH.lower().endswith('.mp4'):
            return jsonify({"error": "Solo se aceptan archivos MP4"}), 400
        
        # Obtener duración del video
        video_duration = get_video_duration(VIDEO_PATH)
        if video_duration is None:
            return jsonify({"error": "No se pudo obtener la duración del video"}), 500
        
        # Verificar que el video es lo suficientemente largo
        if video_duration < 60:
            return jsonify({"error": "El video debe tener al menos 60 segundos"}), 400
        
        # Crear directorio público si no existe
        public_dir = "./public"
        if not os.path.exists(public_dir):
            os.makedirs(public_dir)
        os.remove(os.path.join(public_dir, "sample-video.json"))
        # Crear directorio único para esta sesión (temporal)
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        session_dir = os.path.join(CLIPS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        # Duración aleatoria entre 30-60 segundos
        clip_duration = random.randint(30, 60)
        
        # Tiempo de inicio aleatorio (asegurar que el clip no se salga del video)
        max_start_time = video_duration - clip_duration
        if max_start_time <= 0:
            return jsonify({"error": "El video es demasiado corto para generar un clip de la duración requerida"}), 400
        
        start_time = random.uniform(0, max_start_time)
        
        # Nombre del archivo temporal
        temp_filename = f"clip_temp_{random.randint(1000, 9999)}.mp4"
        temp_path = os.path.join(session_dir, temp_filename)
        
        # Generar el clip en formato 9:16
        success = generate_random_clip(VIDEO_PATH, temp_path, start_time, clip_duration)

        if success:
            # Mover el archivo generado a ./public/sample-video.mp4
            final_path = os.path.join(public_dir, "sample-video.mp4")
            shutil.move(temp_path, final_path)
            
            subprocess.run(["node", "./sub.mjs"])

            # Ejecutar remotion render
            subprocess.run(["npx", "remotion", "render"], check=True)
            
            clip_info = {
                "filename": "sample-video.mp4",
                "start_time": round(start_time, 2),
                "duration": clip_duration,
                "download_url": f"/public/sample-video.mp4",
                "file_path": final_path,
                "aspect_ratio": "9:16",
                "out": "out/CaptionedVideo.mp4"
            }
            
            # Limpiar directorio temporal de la sesión
            shutil.rmtree(session_dir)
            
            response = {
                "success": True,
                "session_id": session_id,
                "video_path": VIDEO_PATH,
                "video_duration": round(video_duration, 2),
                "clip": clip_info,
                "message": "Clip generado en formato 9:16 y guardado en ./public/sample-video.mp4"
            }
        else:
            return {
                "status": "error",
                "message": "Error al generar el clip"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }
    
@app.route('/out/<path:filename>', methods=['GET'])
def serve_captioned_video(filename):
    """
    Sirve el archivo CaptionedVideo.mp4 desde la carpeta ./out/
    """
    try:
        # Ruta de la carpeta donde está el archivo
        folder_path = './out'
        
        return send_from_directory(folder_path, filename)
    except Exception as e:
        return {"error": str(e)}, 500
    
@app.route('/')
def home():
    return {
        "status": "ready"
    }

if __name__ == '__main__':
    Path("clip").mkdir(exist_ok=True)
    Path("public").mkdir(exist_ok=True)
    app.run(host='0.0.0.0', port=7243)

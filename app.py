import os
import tempfile
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import yt_dlp

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "CookingTok API est en ligne !"})

@app.route('/extract', methods=['POST'])
def extract_recipe():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"result": "Erreur : URL manquante."}), 400
        
    tiktok_url = data.get('url')
    
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"result": "Erreur : Clé OPENAI_API_KEY absente."}), 500

        client = OpenAI(api_key=api_key)
        transcript_text = ""

        # Téléchargement de l'audio et transcription via Whisper
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(tiktok_url, download=True)
                    downloaded_files = os.listdir(temp_dir)
                    if downloaded_files:
                        file_path = os.path.join(temp_dir, downloaded_files[0])
                        with open(file_path, "rb") as audio_file:
                            transcript_obj = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file
                            )
                            transcript_text = transcript_obj.text
            except Exception:
                # Fallback sur le titre oEmbed si TikTok bloque le téléchargement direct
                oembed_url = f"https://www.tiktok.com/oembed?url={tiktok_url}"
                res = requests.get(oembed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
                if res.status_code == 200:
                    transcript_text = f"Titre de la vidéo : {res.json().get('title', '')}"

        if not transcript_text:
            return jsonify({"result": "Impossible de récupérer l'audio de la vidéo."}), 200

        # Génération de la recette propre à partir de la vraie transcription audio
        prompt = f"""Voici la transcription exacte de l'audio de la vidéo TikTok :
« {transcript_text} »

À partir de cette transcription réelle, rédige la recette détaillée avec :
- 🍳 **Nom du plat**
- 🛒 **Ingrédients** (avec quantités si mentionnées)
- 👩‍🍳 **Étapes de préparation** détaillées pas à pas."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        return jsonify({"result": response.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"result": f"Erreur serveur : {str(e)}"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

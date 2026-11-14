import os
import subprocess
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

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

        # Extraction des métadonnées et de la description de la vidéo via yt-dlp
        video_info = ""
        try:
            import yt_dlp
            ydl_opts = {'quiet': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(tiktok_url, download=False)
                video_info = f"Titre : {info.get('title', '')}\nDescription : {info.get('description', '')}"
        except Exception:
            # Fallback oEmbed si yt-dlp rencontre un blocage sur Render
            oembed_url = f"https://www.tiktok.com/oembed?url={tiktok_url}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(oembed_url, headers=headers, timeout=3)
            if res.status_code == 200:
                video_info = f"Titre : {res.json().get('title', '')}"

        if not video_info:
            video_info = f"URL de la vidéo : {tiktok_url}"

        client = OpenAI(api_key=api_key)
        prompt = f"Voici les informations extraites d'une vidéo TikTok de cuisine :\n{video_info}\n\nÀ partir de ces éléments, reconstitue la recette complète avec le nom du plat, la liste précise des ingrédients et les étapes de préparation."

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return jsonify({"result": response.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"result": f"Erreur serveur : {str(e)}"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

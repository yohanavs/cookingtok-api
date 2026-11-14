import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

@app.route('/extract', methods=['POST'])
def extract_recipe():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"result": "Erreur : URL manquante."}), 400
        
    tiktok_url = data.get('url')
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"result": "Erreur : Clé GEMINI_API_KEY absente."}), 500

        client = genai.Client(api_key=api_key)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        
        if "vm.tiktok.com" in tiktok_url or "vt.tiktok.com" in tiktok_url:
            res = requests.head(tiktok_url, allow_redirects=True, headers=headers, timeout=10)
            tiktok_url = res.url

        match = re.search(r'/video/(\d+)', tiktok_url)
        video_id = match.group(1) if match else "Inconnu"

        oembed_url = f"https://www.tiktok.com/oembed?url={tiktok_url}"
        oembed_res = requests.get(oembed_url, headers=headers, timeout=10)
        
        video_title = "Non disponible"
        if oembed_res.status_code == 200:
            video_title = oembed_res.json().get('title', 'Non disponible')

        gemini_response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=f"Voici le titre et les informations textuelles d'une vidéo TikTok de cuisine (ID: {video_id}) : « {video_title} ». Extrais ou reconstitue le nom de la recette probable, les ingrédients associés et les étapes de préparation sous forme de liste structurée."
        )
        
        return jsonify({"result": gemini_response.text})
        
    except Exception as e:
        import traceback
        err_details = traceback.format_exc()
        return jsonify({"result": f"Crash Python :\n{err_details}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

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
    video_path = "temp_video.mp4"
    
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"result": "Erreur : La clé GEMINI_API_KEY n'est pas configurée sur Render."}), 500

        client = genai.Client(api_key=api_key)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # Résolution du lien court
        if "vm.tiktok.com" in tiktok_url or "vt.tiktok.com" in tiktok_url:
            res = requests.head(tiktok_url, allow_redirects=True, headers=headers, timeout=10)
            tiktok_url = res.url

        match = re.search(r'/video/(\d+)', tiktok_url)
        if not match:
            return jsonify({"result": "Erreur : Lien TikTok invalide."}), 400
        
        video_id = match.group(1)
        api_url = f"https://www.tikwm.com/api/?url=https://www.tiktok.com/@user/video/{video_id}"
        
        response = requests.get(api_url, headers=headers, timeout=15)
        res_json = response.json()
        
        if res_json.get('code') != 0 or 'data' not in res_json:
            return jsonify({"result": "Erreur : Impossible de récupérer la vidéo."}), 500
            
        video_dl_url = res_json['data']['play']
        video_data = requests.get(video_dl_url, headers=headers, timeout=20).content
        
        with open(video_path, 'wb') as f:
            f.write(video_data)
            
        video_file = client.files.upload(file=video_path)
        
        gemini_response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                video_file, 
                "Analyse cette vidéo de cuisine. Extrais le nom de la recette, les ingrédients précis avec leurs quantités, et les étapes de préparation sous forme de liste structurée."
            ]
        )
        
        return jsonify({"result": gemini_response.text})
        
    except Exception as e:
        return jsonify({"result": f"Erreur serveur : {str(e)}"}), 500
        
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

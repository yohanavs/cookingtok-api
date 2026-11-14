import os
import re
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)
client = genai.Client()

@app.route('/extract', methods=['POST'])
def extract_recipe():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"result": "Erreur : URL manquante."}), 400
        
    tiktok_url = data.get('url')
    video_path = "temp_video.mp4"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        }
        
        # Résolution du lien court si besoin
        if "vm.tiktok.com" in tiktok_url or "vt.tiktok.com" in tiktok_url:
            res = requests.head(tiktok_url, allow_redirects=True, headers=headers)
            tiktok_url = res.url

        match = re.search(r'/video/(\d+)', tiktok_url)
        if not match:
            return jsonify({"result": "Erreur : Lien TikTok invalide."}), 400
        
        video_id = match.group(1)
        
        # Utilisation d'une API web alternative stable pour récupérer le flux mp4
        api_url = f"https://tikwm.com/api/?url=https://www.tiktok.com/@user/video/{video_id}"
        response = requests.get(api_url, headers=headers, timeout=10)
        res_json = response.json()
        
        if res_json.get('code') != 0 or 'data' not in res_json:
            return jsonify({"result": "Erreur : Impossible de récupérer la vidéo via l'extracteur."}), 500
            
        video_dl_url = res_json['data']['play']
        
        # Téléchargement de la vidéo
        video_data = requests.get(video_dl_url, headers=headers, timeout=15).content
        with open(video_path, 'wb') as f:
            f.write(video_data)
            
        # Envoi à Gemini
        video_file = client.files.upload(file=video_path)
        
        gemini_response = client.models.generate_content(
            model='gemini-2.5-flash',
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

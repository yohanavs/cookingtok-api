import os
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
        # Utilisation de l'API alternative pour récupérer le lien direct sans blocage
        api_url = f"https://www.tikwm.com/api/?url={tiktok_url}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        response = requests.get(api_url, headers=headers)
        res_json = response.json()
        
        if res_json.get('code') != 0:
            return jsonify({"result": "Erreur : Impossible de récupérer la vidéo TikTok."}), 400
            
        video_dl_url = res_json['data']['play']
        
        # Téléchargement du fichier vidéo
        video_data = requests.get(video_dl_url, headers=headers).content
        with open(video_path, 'wb') as f:
            f.write(video_data)
            
        # Analyse avec Gemini
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

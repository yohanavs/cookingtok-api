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

        # On tente de récupérer le titre via oEmbed avec un timeout très court, sinon on continue quand même
        video_title = "Non disponible"
        try:
            oembed_url = f"https://www.tiktok.com/oembed?url={tiktok_url}"
            oembed_res = requests.get(oembed_url, headers=headers, timeout=3)
            if oembed_res.status_code == 200:
                video_title = oembed_res.json().get('title', 'Non disponible')
        except Exception:
            pass

        prompt = f"Je souhaite cuisiner la recette de cette vidéo TikTok (URL: {tiktok_url}). Titre récupéré : « {video_title} ». Extrais ou reconstitue le nom de la recette, les ingrédients et les étapes de préparation sous forme de liste structurée."

        gemini_response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt
        )
        
        return jsonify({"result": gemini_response.text})
        
    except Exception as e:
        import traceback
        err_details = traceback.format_exc()
        return jsonify({"result": f"Crash Python :\n{err_details}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

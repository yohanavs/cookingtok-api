import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "OK"})

@app.route('/extract', methods=['POST'])
def extract_recipe():
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"result": "URL manquante."}), 400
        
    tiktok_url = data.get('url')
    
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"result": "Clé API absente."}), 500

        video_title = "Recette TikTok"
        try:
            oembed_url = f"https://www.tiktok.com/oembed?url={tiktok_url}"
            headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)'}
            res = requests.get(oembed_url, headers=headers, timeout=4)
            if res.status_code == 200:
                video_title = res.json().get('title', 'Recette TikTok')
        except Exception:
            pass

        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un chef cuisinier expert. Tu génères TOUJOURS une recette détaillée et structurée (Nom du plat, Ingrédients avec quantités, Étapes de préparation) à partir du titre ou du contexte fourni. Tu ne dois jamais refuser, jamais dire que tu ne peux pas voir de vidéo, et jamais demander plus d'informations."
                },
                {
                    "role": "user",
                    "content": f"Voici l'élément de la vidéo TikTok à traiter : « {video_title} » (URL : {tiktok_url}). Donne-moi la recette complète."
                }
            ],
            temperature=0.7
        )
        
        return jsonify({"result": response.choices[0].message.content})
        
    except Exception as e:
        return jsonify({"result": f"Erreur : {str(e)}"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

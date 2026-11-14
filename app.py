import os
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

@app.route('/extract', methods=['POST'])
def extract_recipe():
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({"result": "Erreur : URL manquante."}), 400
            
        tiktok_url = data.get('url')
        
        # Test de l'initialisation du client Gemini
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"result": "Erreur : La clé GEMINI_API_KEY n'est pas configurée sur Render."}), 500

        client = genai.Client(api_key=api_key)
        
        # Test de réponse simple pour valider le pipeline
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"Donne-moi un faux format de recette de cuisine pour tester ce lien : {tiktok_url}"
        )
        
        return jsonify({"result": response.text})
        
    except Exception as e:
        error_details = traceback.format_exc()
        print(error_details)
        return jsonify({"result": f"Crash Python :\n{error_details}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

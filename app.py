import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
import yt_dlp

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
        ydl_opts = {'format': 'mp4', 'outtmpl': video_path}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([tiktok_url])
            
        video_file = client.files.upload(file=video_path)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                video_file, 
                "Analyse cette vidéo de cuisine. Extrais le nom de la recette, les ingrédients précis avec leurs quantités, et les étapes de préparation sous forme de liste structurée."
            ]
        )
        
        return jsonify({"result": response.text})
        
    except Exception as e:
        return jsonify({"result": f"Erreur serveur : {str5(e) if 'str5' in globals() else str(e)}"}), 500
        
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

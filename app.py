import os
from flask import Flask, request, jsonify
from google import genai
import yt_dlp

app = Flask(__name__)
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

@app.route('/extract', methods=['POST'])
def extract_recipe():
    data = request.json
    tiktok_url = data.get('url')
    
    # 1. Télécharger temporairement la vidéo TikTok
    ydl_opts = {'format': 'mp4', 'outtmpl': 'temp_video.mp4'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([tiktok_url])
        
    # 2. Envoyer le fichier vidéo à Gemini pour analyse audio + image
    video_file = client.files.upload(file="temp_video.mp4")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            video_file, 
            "Analyse cette vidéo de cuisine. Extrais le nom de la recette, les ingrédients précis avec leurs quantités, et les étapes de préparation sous forme de liste structurée JSON."
        ]
    )
    
    # Nettoyage
    os.remove("temp_video.mp4")
    
    return jsonify({"result": response.text})

if __name__ == '__main__':
    app.run(port=5000)

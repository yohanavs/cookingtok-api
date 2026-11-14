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
    tiktok_url = data.get('url')
    
    ydl_opts = {'format': 'mp4', 'outtmpl': 'temp_video.mp4'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([tiktok_url])
        
    video_file = client.files.upload(file="temp_video.mp4")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            video_file, 
            "Analyse cette vidéo de cuisine. Extrais le nom de la recette, les ingrédients précis avec leurs quantités, et les étapes de préparation sous forme de liste structurée JSON."
        ]
    )
    
    os.remove("temp_video.mp4")
    
    return jsonify({"result": response.text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

import base64
import glob
import os
import tempfile

import cv2
import requests
import yt_dlp
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

MAX_FRAMES = 12                      # nombre d'images analysées
MAX_DURATION = 180                   # durée max de la vidéo (secondes)
MAX_AUDIO_BYTES = 24 * 1024 * 1024   # limite Whisper = 25 Mo
VISION_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

SYSTEM_PROMPT = """Tu es un assistant qui retranscrit des recettes de cuisine à partir d'une vidéo TikTok.
Tu reçois : la légende de la vidéo, la transcription de ce qui est dit, et des images clés de la vidéo.

RÈGLES STRICTES :
- Base-toi UNIQUEMENT sur ce qui est dit, écrit à l'écran ou visible dans les images, et sur la légende.
- N'invente jamais un ingrédient ni une quantité. Si une quantité n'est pas donnée, écris « quantité non précisée ».
- Si tu fais une estimation visuelle, marque-la clairement « (estimation) ».
- Si la vidéo ne contient pas de recette, dis-le simplement.
- Réponds en français, en texte brut : pas de markdown (pas de ** ni de #).

FORMAT :
NOM DU PLAT

INGRÉDIENTS
- quantité + ingrédient

PRÉPARATION
1. étape détaillée
2. ...

INFOS (temps de cuisson, température, astuces) : seulement si mentionnés dans la vidéo."""


def reply(text):
    # Toujours 200 pour que l'interface affiche le message
    return jsonify({"result": text}), 200


def get_oembed_title(url):
    try:
        res = requests.get(
            "https://www.tiktok.com/oembed",
            params={"url": url},
            headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)"},
            timeout=5,
        )
        if res.status_code == 200:
            return res.json().get("title", "") or ""
    except Exception as e:
        print("oEmbed échoué :", e)
    return ""


def download_video(url, folder):
    opts = {
        "format": "best[height<=720]/best",
        "outtmpl": os.path.join(folder, "video.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)"
        },
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if (info.get("duration") or 0) > MAX_DURATION:
            raise ValueError("Vidéo trop longue.")
        ydl.download([url])

    files = glob.glob(os.path.join(folder, "video.*"))
    if not files:
        raise ValueError("Fichier vidéo introuvable après téléchargement.")

    caption = info.get("description") or info.get("title") or ""
    return files[0], caption


def transcribe(client, path):
    try:
        if os.path.getsize(path) > MAX_AUDIO_BYTES:
            print("Fichier trop gros pour Whisper")
            return ""
        with open(path, "rb") as f:
            result = client.audio.transcriptions.create(model="whisper-1", file=f)
        return (result.text or "").strip()
    except Exception as e:
        print("Transcription échouée :", e)
        return ""


def extract_frames(path):
    frames = []
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return frames

    for i in range(MAX_FRAMES):
        idx = int(total * (i + 0.5) / MAX_FRAMES)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, img = cap.read()
        if not ok:
            continue
        h, w = img.shape[:2]
        scale = 1024 / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if ok:
            frames.append(base64.b64encode(buf).decode("utf-8"))
    cap.release()
    return frames


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "OK"})


@app.route("/extract", methods=["POST"])
def extract_recipe():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return reply("URL manquante.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return reply("Clé API absente.")

    client = OpenAI(api_key=api_key)

    caption = ""
    transcript = ""
    frames = []
    video_ok = False

    try:
        with tempfile.TemporaryDirectory() as folder:
            try:
                path, caption = download_video(url, folder)
                video_ok = True
            except Exception as e:
                print("Téléchargement échoué :", e)
                caption = get_oembed_title(url)

            if video_ok:
                transcript = transcribe(client, path)
                frames = extract_frames(path)

        if not video_ok and not caption:
            return reply(
                "Impossible de récupérer la vidéo (TikTok bloque peut-être le serveur). "
                "Réessaie dans un moment."
            )

        text = f"Légende TikTok :\n{caption or '(aucune)'}\n\n"
        text += f"Transcription audio :\n{transcript or '(aucune parole détectée)'}\n\n"
        if frames:
            text += f"Voici {len(frames)} images clés de la vidéo, dans l'ordre chronologique."
        else:
            text += "Aucune image disponible."

        content = [{"type": "text", "text": text}]
        for b64 in frames:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}",
                        "detail": "high",
                    },
                }
            )

        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
        )
        result = response.choices[0].message.content

        if not video_ok:
            result = (
                "⚠️ Vidéo non téléchargeable : recette basée uniquement sur la légende, "
                "elle peut être incomplète.\n\n" + result
            )

        return reply(result)

    except Exception as e:
        print("Erreur :", e)
        return reply(f"Erreur : {str(e)}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

import base64
import os
import tempfile

import cv2
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

MAX_UPLOAD_BYTES = 24 * 1024 * 1024
MAX_FRAMES = 12
VISION_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1024 * 1024

SYSTEM_PROMPT_VIDEO = """Tu es un assistant qui retranscrit des recettes de cuisine à partir d'une vidéo.
Tu reçois : la transcription de ce qui est dit dans la vidéo, et des images clés de la vidéo.

RÈGLES STRICTES :
- Base-toi UNIQUEMENT sur ce qui est dit, écrit à l'écran ou visible dans les images.
- Si une quantité n'est pas explicitement donnée ou visible, écris « quantité non précisée » devant l'ingrédient. N'invente rien.
- Réponds en français, en texte brut : pas de markdown (pas de ** ni de #).

FORMAT :
NOM DU PLAT

INGRÉDIENTS
- quantité + ingrédient

PRÉPARATION
1. étape détaillée
2. ...

INFOS : seulement si mentionnés dans la vidéo."""

SYSTEM_PROMPT_FRIDGE = """Tu es un assistant de cuisine. L'utilisateur te donne une liste d'ingrédients de son frigo.
RÈGLES STRICTES :
- Invente une recette simple et équilibrée pour 1 personne.
- Attribue obligatoirement des quantités chiffrées précises pour 1 personne (ex: 80 g de pâtes, 1 filet de poulet de 120 g, etc.).
- Ajoute les basiques nécessaires (sel, poivre, huile, beurre).
- Réponds en français, en texte brut : pas de markdown (pas de ** ni de #).

FORMAT :
NOM DU PLAT

INGRÉDIENTS
- quantité + ingrédient

PRÉPARATION
1. étape détaillée
2. ...

INFOS : temps de cuisson et astuces."""


def reply(text):
    return jsonify({"result": text}), 200


@app.errorhandler(413)
def too_big(_error):
    return reply("Vidéo trop lourde (24 Mo maximum). Choisis une vidéo plus courte.")


def transcribe(client, path):
    try:
        with open(path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1", file=("video.mp4", f)
            )
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
    video = request.files.get("video")
    if not video or not video.filename:
        return reply("Aucune donnée reçue.")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return reply("Clé API absente.")

    client = OpenAI(api_key=api_key)

    try:
        if video.filename == "fridge.txt":
            ingredients = video.read().decode("utf-8")
            prompt = f"J'ai ces ingrédients dans mon frigo : {ingredients}. Invente une recette simple et équilibrée pour 1 personne."
            
            response = client.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_FRIDGE},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            return reply(response.choices[0].message.content)

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "video.mp4")
            video.save(path)

            if os.path.getsize(path) > MAX_UPLOAD_BYTES:
                return reply("Vidéo trop lourde (24 Mo maximum). Choisis une vidéo plus courte.")

            transcript = transcribe(client, path)
            frames = extract_frames(path)

        if not transcript and not frames:
            return reply("Impossible de lire cette vidéo. Essaie un autre fichier.")

        text = f"Transcription audio :\n{transcript or '(aucune parole détectée)'}\n\n"
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
                {"role": "system", "content": SYSTEM_PROMPT_VIDEO},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
        )
        return reply(response.choices[0].message.content)

    except Exception as e:
        print("Erreur :", e)
        return reply(f"Erreur : {str(e)}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

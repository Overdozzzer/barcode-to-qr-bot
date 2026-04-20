import os
import io
import json
import logging
from flask import Flask, request, jsonify
from PIL import Image
import qrcode
import requests
from pyzbar.pyzbar import decode

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
TOKEN = "8339983157:AAEYESCLnRTL6sdwI03-bupB1ID-L7bTh6g"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    logger.info(f"Received webhook: {data.keys() if data else 'None'}")
    
    if not data or "message" not in data:
        return jsonify({"ok": True})
    
    message = data["message"]
    chat_id = message["chat"]["id"]
    
    if "photo" not in message:
        send_message(chat_id, "📸 Отправь фото штрихкода")
        return jsonify({"ok": True})
    
    try:
        file_id = message["photo"][-1]["file_id"]
        photo_bytes = get_file(file_id)
        
        if not photo_bytes:
            send_message(chat_id, "❌ Не удалось получить фото")
            return jsonify({"ok": True})
        
        logger.info(f"Photo size: {len(photo_bytes)} bytes")
        
        img = Image.open(io.BytesIO(photo_bytes))
        decoded_objects = decode(img)
        
        logger.info(f"Decoded objects: {len(decoded_objects)}")
        
        if not decoded_objects:
            send_message(chat_id, "❌ Не удалось распознать штрихкод\n\nПопробуй:\n• Чёткое фото\n• Хорошее освещение\n• Штрихкод по центру")
            return jsonify({"ok": True})
        
        barcode_data = decoded_objects[0].data.decode("utf-8")
        barcode_type = decoded_objects[0].type
        
        send_message(chat_id, f"📦 Распознано: `{barcode_data}`\n📌 Тип: `{barcode_type}`", parse_mode="Markdown")
        
        qr = qrcode.make(barcode_data)
        qr_bytes = io.BytesIO()
        qr.save(qr_bytes, format="PNG")
        qr_bytes.seek(0)
        
        barcode_url = f"https://barcode.tec-it.com/barcode.ashx?data={barcode_data}&code=Code128&dpi=96"
        barcode_bytes = requests.get(barcode_url).content
        
        send_media_group(
            chat_id,
            [
                ("photo", "barcode.png", barcode_bytes, "1️⃣ Сгенерированный штрихкод"),
                ("photo", "qr.png", qr_bytes, "2️⃣ QR-код")
            ]
        )
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        send_message(chat_id, f"❌ Ошибка: {str(e)[:100]}")
    
    return jsonify({"ok": True})

def get_file(file_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getFile?file_id={file_id}"
    resp = requests.get(url).json()
    if not resp.get("ok"):
        return None
    file_path = resp["result"]["file_path"]
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
    return requests.get(file_url).content

def send_message(chat_id, text, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    requests.post(url, json=data)

def send_media_group(chat_id, media_list):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMediaGroup"
    
    files = {}
    media = []
    
    for i, (media_type, filename, file_bytes, caption) in enumerate(media_list):
        files[f"file{i}"] = (filename, file_bytes, "image/png")
        media.append({
            "type": media_type,
            "media": f"attach://file{i}",
            "caption": caption if i == 0 else "",
            "parse_mode": "Markdown"
        })
    
    data = {"chat_id": chat_id, "media": json.dumps(media)}
    requests.post(url, data=data, files=files)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
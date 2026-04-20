import os
import io
import json
import ctypes
import barcode
from barcode.writer import ImageWriter
from flask import Flask, request, jsonify
from PIL import Image
import qrcode
import requests

# Попытка загрузить libzbar для pyzbar (если доступна)
try:
    ctypes.CDLL("libzbar.so.0")
except:
    pass

# Пробуем импортировать pyzbar, если не получается — используем zbar-py
try:
    from pyzbar.pyzbar import decode
except ImportError:
    try:
        from zbar import decode
    except ImportError:
        # Заглушка, если ни одна библиотека не установлена
        def decode(img):
            return []

app = Flask(__name__)
TOKEN = "8339983157:AAEYESCLnRTL6sdwI03-bupB1ID-L7bTh6g"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    
    if "message" not in data:
        return jsonify({"ok": True})
    
    message = data["message"]
    chat_id = message["chat"]["id"]
    
    if "photo" not in message:
        send_message(chat_id, "📸 Отправь фото штрихкода")
        return jsonify({"ok": True})
    
    file_id = message["photo"][-1]["file_id"]
    photo_bytes = get_file(file_id)
    
    if not photo_bytes:
        send_message(chat_id, "❌ Не удалось получить фото")
        return jsonify({"ok": True})
    
    img = Image.open(io.BytesIO(photo_bytes))
    decoded = decode(img)
    
    if not decoded:
        send_message(chat_id, "❌ Не удалось распознать штрихкод")
        return jsonify({"ok": True})
    
    barcode_data = decoded[0].data.decode("utf-8")
    barcode_type = decoded[0].type
    
    send_message(chat_id, f"📦 Распознано: `{barcode_data}`\n📌 Тип: `{barcode_type}`", parse_mode="Markdown")
    
    new_barcode_bytes = generate_barcode(barcode_data, barcode_type)
    qr_bytes = generate_qr(barcode_data)
    
    send_media_group(
        chat_id,
        [
            ("photo", "barcode.png", new_barcode_bytes, "1️⃣ Сгенерированный штрихкод"),
            ("photo", "qr.png", qr_bytes, "2️⃣ QR-код")
        ]
    )
    
    return jsonify({"ok": True})

def generate_barcode(data, barcode_type):
    barcode_bytes = io.BytesIO()
    
    try:
        if barcode_type == "EAN13" and len(data) >= 13:
            barcode_class = barcode.get_barcode_class('ean13')
            bc = barcode_class(data[:13], writer=ImageWriter())
        elif barcode_type == "EAN8" and len(data) >= 8:
            barcode_class = barcode.get_barcode_class('ean8')
            bc = barcode_class(data[:8], writer=ImageWriter())
        elif barcode_type == "UPCA" and len(data) >= 12:
            barcode_class = barcode.get_barcode_class('upca')
            bc = barcode_class(data[:12], writer=ImageWriter())
        else:
            barcode_class = barcode.get_barcode_class('code128')
            bc = barcode_class(data, writer=ImageWriter())
        
        bc.write(barcode_bytes)
    except:
        barcode_class = barcode.get_barcode_class('code128')
        bc = barcode_class(data, writer=ImageWriter())
        bc.write(barcode_bytes)
    
    barcode_bytes.seek(0)
    return barcode_bytes

def generate_qr(data):
    qr = qrcode.make(data)
    qr_bytes = io.BytesIO()
    qr.save(qr_bytes, format="PNG")
    qr_bytes.seek(0)
    return qr_bytes

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
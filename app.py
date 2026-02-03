import os # <--- เพิ่มบรรทัดนี้บนสุด
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# ดึงค่าจาก Environment Variable ที่ตั้งใน Render
line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))

# ... (ส่วน callback เหมือนเดิม) ...
# ใส่ Channel Access Token และ Channel Secret จาก LINE Developers
line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')
handler = WebhookHandler('YOUR_CHANNEL_SECRET')

@app.route("/callback", methods=['POST'])
def callback():
    # รับ Header จาก LINE
    signature = request.headers['X-Line-Signature']
    # รับ Body
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ฟังก์ชันนี้จะทำงานเมื่อมีข้อความเข้ามา
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip() # ข้อความที่ผู้ใช้พิมพ์มา
    
    # Logic การตอบกลับ
    if msg == "ซ่อมคอม":
        reply_text = "รับทราบครับ ขอทราบอาการเสียเบื้องต้นหน่อยครับ?"
    elif msg == "ซ่อมปริ้นเตอร์":
        reply_text = "ปริ้นเตอร์ยี่ห้ออะไร และอาการเป็นอย่างไรครับ?"
    elif msg == "สั่งซื้อ":
        reply_text = "ต้องการสั่งซื้ออุปกรณ์ประเภทไหนครับ?"
    else:
        # กรณีพิมพ์อย่างอื่นที่บอทไม่รู้จัก
        reply_text = "ขออภัยครับ ผมยังไม่เข้าใจคำสั่ง หรือลองกดเมนูเลือกรายการได้เลยครับ"

    # ส่งข้อความกลับหาผู้ใช้
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# ส่วนนี้คือฟังก์ชันที่จะทำงานเมื่อมีข้อความเข้า
@app.route("/")
def hello():
    return "Hello World"

if __name__ == "__main__":
    app.run(port=5000)
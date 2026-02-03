
import os
from dotenv import load_dotenv 

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)
load_dotenv()
channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)
# -----------------------------------------------

print("SECRET:", channel_secret)
print("TOKEN:", channel_access_token)

@app.route("/callback", methods=['GET', 'POST'])
def callback():
    body = request.get_data(as_text=True)
    print("METHOD:", request.method)
    print("BODY:", body)
    return 'OK', 200


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

@app.route("/")
def hello():
    return "Hello World"

if __name__ == "__main__":
    app.run(port=5000)
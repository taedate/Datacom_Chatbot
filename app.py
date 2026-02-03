from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

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

# ส่วนนี้คือฟังก์ชันที่จะทำงานเมื่อมีข้อความเข้า
@app.route("/")
def hello():
    return "Hello World"

if __name__ == "__main__":
    app.run(port=5000)
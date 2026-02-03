import os
from dotenv import load_dotenv 

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

app = Flask(__name__)
load_dotenv()

# ใส่ Token และ Secret ของคุณที่นี่ หรือดึงจาก .env
channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# -----------------------------------------------
# เก็บสถานะ (State) และข้อมูลชั่วคราว (Data)
sessions = {} 
user_data = {} 
# -----------------------------------------------

print("SECRET:", channel_secret)
print("TOKEN:", channel_access_token)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(403)

    return 'OK', 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id 
    
    # ดึงสถานะปัจจุบัน (ถ้าไม่มีให้เป็น IDLE)
    current_state = sessions.get(user_id, 'IDLE')
    reply_msgs = [] # เตรียมตัวแปรสำหรับเก็บข้อความตอบกลับ (เผื่อส่งหลายข้อความ)

    # --- RESET COMMAND ---
    if msg == "ยกเลิก":
        sessions[user_id] = 'IDLE'
        if user_id in user_data: del user_data[user_id]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ยกเลิกรายการแล้วครับ เลือกเมนูใหม่ได้เลย"))
        return

    # =================================================================
    # STATE: IDLE (สถานะว่าง รอเลือกเมนูจาก Rich Menu)
    # =================================================================
    if current_state == 'IDLE':
        
        # 1. ซ่อมคอมพิวเตอร์ ปริ้นเตอร์ อุปกรณ์คอมพิวเตอร์
        if msg == "แจ้งซ่อม": # สมมติว่า Rich Menu ส่งคำว่า "แจ้งซ่อม" หรือตรงกับชื่อปุ่มของคุณ
            sessions[user_id] = 'REPAIR_SELECT_TYPE'
            # สร้างปุ่มให้เลือกประเภท
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="คอมพิวเตอร์", text="คอมพิวเตอร์")),
                QuickReplyButton(action=MessageAction(label="ปริ้นเตอร์", text="ปริ้นเตอร์")),
                QuickReplyButton(action=MessageAction(label="อุปกรณ์อื่นๆ", text="อุปกรณ์คอมพิวเตอร์"))
            ])
            reply_msgs.append(TextSendMessage(text="ต้องการซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=quick_reply))

        # 2. สั่งซื้อหน่วยงาน
        elif msg == "สั่งซื้อหน่วยงาน":
            sessions[user_id] = 'ORG_WAIT_NAME'
            reply_msgs.append(TextSendMessage(text="ขอทราบชื่อหน่วยงานของท่านครับ?"))

        # 3. สอบถามสินค้า
        elif msg == "สอบถามสินค้า":
            sessions[user_id] = 'INQUIRY_WAIT_PRODUCT'
            reply_msgs.append(TextSendMessage(text="ต้องการสอบถามข้อมูลสินค้าตัวไหนครับ?\n(พิมพ์ชื่อสินค้าหรือรุ่นได้เลย)"))

        # 4. ติดตั้งกล้องวงจรปิด
        elif msg == "ติดตั้งกล้องวงจรปิด":
            sessions[user_id] = 'CCTV_SELECT_TYPE'
            # สร้างปุ่มเลือกประเภทกล้อง
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="Smart Camera", text="Smart Camera")),
                QuickReplyButton(action=MessageAction(label="กล้อง Analog", text="กล้อง Analog")),
                QuickReplyButton(action=MessageAction(label="กล้อง IP Camera", text="กล้อง IP Camera")),
                QuickReplyButton(action=MessageAction(label="อื่นๆ", text="อื่นๆ"))
            ])
            reply_msgs.append(TextSendMessage(text="สนใจติดตั้งกล้องประเภทไหนครับ?", quick_reply=quick_reply))
        
        else:
            # กรณีพิมพ์เล่นๆ หรือไม่ตรงคีย์เวิร์ด
            reply_msgs.append(TextSendMessage(text="สวัสดีครับ กรุณาเลือกรายการจากเมนูด้านล่างได้เลยครับ"))

    # =================================================================
    # FLOW 1: แจ้งซ่อม (เลือกประเภท -> บอกอาการ -> จบ)
    # =================================================================
    elif current_state == 'REPAIR_SELECT_TYPE':
        # ผู้ใช้เลือกประเภทมาแล้ว (เช่น คอมพิวเตอร์)
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['repair_type'] = msg
        
        sessions[user_id] = 'REPAIR_WAIT_DETAIL'
        reply_msgs.append(TextSendMessage(text=f"รับเรื่องซ่อม {msg} ครับ\nกรุณาพิมพ์อาการเสียหรือปัญหาที่เจอให้หน่อยครับ"))

    elif current_state == 'REPAIR_WAIT_DETAIL':
        repair_type = user_data[user_id].get('repair_type')
        symptom = msg
        
        # จบ Flow
        summary = f"บันทึกแจ้งซ่อมสำเร็จ\nประเภท: {repair_type}\nอาการ: {symptom}\n\nขอบคุณครับ กรุณารอแอดมินประเมินราคาและติดต่อกลับนะครับ"
        reply_msgs.append(TextSendMessage(text=summary))
        
        # Reset State
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # =================================================================
    # FLOW 2: สั่งซื้อหน่วยงาน (ชื่อหน่วยงาน -> รายการของ -> จบ)
    # =================================================================
    elif current_state == 'ORG_WAIT_NAME':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['org_name'] = msg
        
        sessions[user_id] = 'ORG_WAIT_ITEM'
        reply_msgs.append(TextSendMessage(text=f"ยินดีต้อนรับหน่วยงาน {msg} ครับ\nกรุณาพิมพ์รายการสินค้าที่ต้องการสั่งซื้อได้เลยครับ"))

    elif current_state == 'ORG_WAIT_ITEM':
        org_name = user_data[user_id].get('org_name')
        item_list = msg
        
        # จบ Flow
        summary = f"รับข้อมูลสั่งซื้อเรียบร้อย\nหน่วยงาน: {org_name}\nรายการ: {item_list}\n\nกรุณารอแอดมินตรวจสอบสต็อกและติดต่อกลับนะครับ"
        reply_msgs.append(TextSendMessage(text=summary))
        
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # =================================================================
    # FLOW 3: สอบถามสินค้า (ชื่อสินค้า -> จบ)
    # =================================================================
    elif current_state == 'INQUIRY_WAIT_PRODUCT':
        product_name = msg
        
        # จบ Flow
        summary = f"รับเรื่องสอบถามสินค้า: {product_name}\n\nกรุณารอแอดมินเข้ามาให้ข้อมูลเพิ่มเติมสักครู่นะครับ"
        reply_msgs.append(TextSendMessage(text=summary))
        
        sessions[user_id] = 'IDLE'

    # =================================================================
    # FLOW 4: ติดตั้งกล้องวงจรปิด (เลือกประเภท -> จบ)
    # =================================================================
    elif current_state == 'CCTV_SELECT_TYPE':
        cctv_type = msg
        
        # จบ Flow
        summary = f"สนใจติดตั้ง: {cctv_type}\n\nรับเรื่องเรียบร้อยครับ กรุณารอแอดมินติดต่อกลับเพื่อแนะนำรายละเอียดนะครับ"
        reply_msgs.append(TextSendMessage(text=summary))
        
        sessions[user_id] = 'IDLE'

    # ส่งข้อความทั้งหมดกลับหาผู้ใช้
    if reply_msgs:
        line_bot_api.reply_message(event.reply_token, reply_msgs)

@app.route("/")
def hello():
    return "Hello World"

if __name__ == "__main__":
    app.run(port=5000)
import os
from dotenv import load_dotenv 

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction,
    FlexSendMessage, BubbleContainer, BoxComponent, 
    TextComponent, SeparatorComponent, ImageComponent # <--- เพิ่ม ImageComponent
)

app = Flask(__name__)
load_dotenv()

channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

sessions = {} 
user_data = {} 

# --- ฟังก์ชันสร้าง Flex Message (เพิ่มส่วนใส่รูปภาพ) ---
def create_summary_flex(title, color, items, footer_text, image_url=None):
    """
    image_url: ลิงก์รูปภาพ (ต้องเป็น HTTPS) จะใส่หรือไม่ใส่ก็ได้
    """
    
    # 1. ส่วน Header (หัวข้อสีๆ)
    header_box = BoxComponent(
        layout='vertical',
        backgroundColor=color,
        contents=[TextComponent(text=title, weight='bold', color='#ffffff', size='lg')]
    )

    # 2. ส่วน Hero (รูปภาพหน้าปก) - สร้างเฉพาะถ้ามี URL ส่งมา
    hero_image = None
    if image_url:
        hero_image = ImageComponent(
            url=image_url,
            size='full',
            aspect_ratio='20:13', # สัดส่วนมาตรฐานรูปปก
            aspect_mode='cover'
        )

    # 3. ส่วน Body (เนื้อหา)
    body_contents = []
    # เพิ่ม Title เล็กๆ ก่อนรายการ
    body_contents.append(TextComponent(text='รายละเอียด', weight='bold', size='md', margin='md'))
    
    for label, value in items:
        body_contents.append(BoxComponent(
            layout='baseline',
            spacing='sm',
            margin='sm',
            contents=[
                TextComponent(text=label, color='#aaaaaa', size='sm', flex=2),
                TextComponent(text=value, wrap=True, color='#666666', size='sm', flex=5)
            ]
        ))

    # 4. ประกอบร่าง Bubble
    bubble = BubbleContainer(
        header=header_box,
        hero=hero_image, # ใส่รูปตรงนี้
        body=BoxComponent(layout='vertical', contents=body_contents),
        footer=BoxComponent(
            layout='vertical',
            contents=[
                SeparatorComponent(),
                BoxComponent(
                    layout='vertical',
                    padding_top='md',
                    contents=[TextComponent(text=footer_text, color='#aaaaaa', size='xs', align='center')]
                )
            ]
        )
    )
    return FlexSendMessage(alt_text=title, contents=bubble)

# -----------------------------------------------
# ส่วน Callback และ Handle Message เหมือนเดิม
# แต่จะแก้เฉพาะส่วน logic การเรียกใช้ create_summary_flex ด้านล่าง
# -----------------------------------------------

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
    current_state = sessions.get(user_id, 'IDLE')
    reply_msgs = []

    # --- RESET COMMAND ---
    if msg == "ยกเลิก":
        sessions[user_id] = 'IDLE'
        if user_id in user_data: del user_data[user_id]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อย"))
        return

    # --- STATE: IDLE ---
    if current_state == 'IDLE':
        if msg == "แจ้งซ่อม": 
            sessions[user_id] = 'REPAIR_SELECT_TYPE'
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
                QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
                QuickReplyButton(action=MessageAction(label="⌨️ อุปกรณ์อื่นๆ", text="อุปกรณ์คอมพิวเตอร์"))
            ])
            reply_msgs.append(TextSendMessage(text="🔧 ต้องการซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=quick_reply))

        elif msg == "สั่งซื้อหน่วยงาน":
            sessions[user_id] = 'ORG_WAIT_NAME'
            reply_msgs.append(TextSendMessage(text="🏢 ขอทราบชื่อหน่วยงานของท่านครับ?"))

        elif msg == "สอบถามสินค้า":
            sessions[user_id] = 'INQUIRY_WAIT_PRODUCT'
            reply_msgs.append(TextSendMessage(text="📦 ต้องการสอบถามข้อมูลสินค้าตัวไหนครับ?"))

        elif msg == "ติดตั้งกล้องวงจรปิด":
            sessions[user_id] = 'CCTV_SELECT_TYPE'
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="🏠 Smart Camera", text="Smart Camera")),
                QuickReplyButton(action=MessageAction(label="📹 กล้อง Analog", text="กล้อง Analog")),
                QuickReplyButton(action=MessageAction(label="🌐 IP Camera", text="กล้อง IP Camera")),
                QuickReplyButton(action=MessageAction(label="❓ อื่นๆ", text="อื่นๆ"))
            ])
            reply_msgs.append(TextSendMessage(text="📹 สนใจติดตั้งกล้องประเภทไหนครับ?", quick_reply=quick_reply))
        else:
            reply_msgs.append(TextSendMessage(text="👋 สวัสดีครับ กรุณาเลือกรายการจากเมนูด้านล่าง"))

    # --- FLOW 1: แจ้งซ่อม ---
    elif current_state == 'REPAIR_SELECT_TYPE':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['repair_type'] = msg
        sessions[user_id] = 'REPAIR_WAIT_DETAIL'
        reply_msgs.append(TextSendMessage(text=f"รับเรื่องซ่อม {msg} ครับ\n📝 กรุณาพิมพ์อาการเสียมาได้เลย"))

    elif current_state == 'REPAIR_WAIT_DETAIL':
        repair_type = user_data[user_id].get('repair_type')
        symptom = msg
        
        # ใส่รูปคอมพิวเตอร์ซ่อม (ตัวอย่าง URL)
        img_url = "https://images.unsplash.com/photo-1597872250977-010e7123bf07?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60"
        
        flex_msg = create_summary_flex(
            title="บันทึกแจ้งซ่อม",
            color="#ff9100",
            image_url=img_url, # <--- ใส่รูปตรงนี้
            items=[("ประเภท", repair_type), ("อาการ", symptom), ("สถานะ", "รอประเมินราคา")],
            footer_text="กรุณารอแอดมินประเมินราคา"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # --- FLOW 2: สั่งซื้อหน่วยงาน ---
    elif current_state == 'ORG_WAIT_NAME':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['org_name'] = msg
        sessions[user_id] = 'ORG_WAIT_ITEM'
        reply_msgs.append(TextSendMessage(text=f"ยินดีต้อนรับ {msg} ครับ\n🛒 พิมพ์รายการสินค้าได้เลย"))

    elif current_state == 'ORG_WAIT_ITEM':
        org_name = user_data[user_id].get('org_name')
        item_list = msg
        
        # ใส่รูปกล่องพัสดุ
        img_url = "https://images.unsplash.com/photo-1586769852044-692d6e3703f0?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60"

        flex_msg = create_summary_flex(
            title="คำสั่งซื้อหน่วยงาน",
            color="#007bff",
            image_url=img_url,
            items=[("หน่วยงาน", org_name), ("รายการ", item_list), ("สถานะ", "รอตรวจสอบสต็อก")],
            footer_text="แอดมินจะรีบส่งใบเสนอราคาให้ครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # --- FLOW 3: สอบถามสินค้า ---
    elif current_state == 'INQUIRY_WAIT_PRODUCT':
        product_name = msg
        
        # ใส่รูปเครื่องหมายคำถาม หรือ Customer Service
        img_url = "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60"

        flex_msg = create_summary_flex(
            title="สอบถามสินค้า",
            color="#9c27b0",
            image_url=img_url,
            items=[("สินค้า", product_name), ("สถานะ", "รอแอดมินตอบกลับ")],
            footer_text="กำลังเรียกแอดมินครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'

    # --- FLOW 4: CCTV ---
    elif current_state == 'CCTV_SELECT_TYPE':
        cctv_type = msg
        
        # ใส่รูปกล้องวงจรปิด
        img_url = "https://images.unsplash.com/photo-1557324232-b8917d3c3d63?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60"

        flex_msg = create_summary_flex(
            title="สนใจติดตั้ง CCTV",
            color="#00c853",
            image_url=img_url,
            items=[("ประเภท", cctv_type), ("สถานะ", "รับเรื่องแล้ว")],
            footer_text="เจ้าหน้าที่จะติดต่อกลับครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'

    if reply_msgs:
        line_bot_api.reply_message(event.reply_token, reply_msgs)

if __name__ == "__main__":
    app.run(port=5000)
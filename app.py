import os
from dotenv import load_dotenv
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction, FlexSendMessage,
    BubbleContainer, BoxComponent, TextComponent, SeparatorComponent,
    ImageComponent, ButtonComponent, URIAction
)

# --- Configuration ---
load_dotenv()
app = Flask(__name__)

channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

# In-memory storage (For production, use Redis or Database)
sessions = {}
user_data = {}

# --- Flex Message Templates ---

def create_summary_flex(title, color, items, footer_text, image_url=None):
    """สร้างการ์ดสรุปรายการแบบ Flex Message"""
    header = BoxComponent(
        layout='vertical',
        backgroundColor=color,
        paddingAll='none',
        contents=[
            BoxComponent(
                layout='vertical',
                paddingAll='md',
                contents=[TextComponent(text=title, weight='bold', color='#ffffff', size='lg')]
            )
        ]
    )

    hero = None
    if image_url:
        hero = ImageComponent(
            url=image_url,
            size='full',
            aspect_ratio='4:3',
            aspect_mode='cover',
            backgroundColor=color
        )

    body_contents = [TextComponent(text='รายละเอียด', weight='bold', size='md', margin='md')]
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

    footer = BoxComponent(
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

    bubble = BubbleContainer(
        styles={'hero': {'separator': False, 'backgroundColor': color}},
        header=header,
        hero=hero,
        body=BoxComponent(layout='vertical', contents=body_contents),
        footer=footer
    )
    return FlexSendMessage(alt_text=title, contents=bubble)

def create_location_card():
    """สร้างการ์ดแผนที่ร้าน"""
    map_url = "https://github.com/taedate/datacom-image/blob/main/Datacom.jpg?raw=true"
    bubble = BubbleContainer(
        direction='ltr',
        hero=ImageComponent(
            url=map_url,
            size='full',
            aspect_ratio='2.35:1',
            aspect_mode='cover',
            action=URIAction(uri='https://www.google.com/maps') # ใส่ Link จริงของคุณ
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text='Datacom Service', weight='bold', size='xl'),
                BoxComponent(
                    layout='vertical', margin='lg', spacing='sm',
                    contents=[
                        BoxComponent(layout='baseline', spacing='sm', contents=[
                            TextComponent(text='ที่อยู่', color='#aaaaaa', size='sm', flex=1),
                            TextComponent(text='123 ถ.สุขุมวิท กทม. 10110', wrap=True, color='#666666', size='sm', flex=5)
                        ]),
                        BoxComponent(layout='baseline', spacing='sm', contents=[
                            TextComponent(text='เวลา', color='#aaaaaa', size='sm', flex=1),
                            TextComponent(text='09:00 - 18:00 น. (จ-ส)', wrap=True, color='#666666', size='sm', flex=5)
                        ]),
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical', spacing='sm',
            contents=[
                ButtonComponent(style='primary', height='sm', action=URIAction(label='โทรติดต่อ', uri='tel:0812345678')),
                ButtonComponent(style='secondary', height='sm', action=URIAction(label='แผนที่นำทาง', uri='https://www.google.com/maps'))
            ]
        )
    )
    return FlexSendMessage(alt_text="ที่ตั้งร้าน", contents=bubble)

# --- Helper Functions ---

def get_skip_image_quick_reply():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ไม่ใส่รูป (ข้าม)", text="ข้าม"))
    ])

# --- Webhook Handler ---

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(403)
    return 'OK', 200

@handler.add(MessageEvent, message=(TextMessage, ImageMessage))
def handle_message(event):
    user_id = event.source.user_id
    state = sessions.get(user_id, 'IDLE')
    
    # ดึงข้อความหรือกำหนดสถานะรูปภาพ
    is_image = isinstance(event.message, ImageMessage)
    text = event.message.text.strip() if not is_image else "__IMAGE__"

    # Global Cancel
    if text == "ยกเลิก":
        sessions[user_id] = 'IDLE'
        user_data.pop(user_id, None)
        return line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อย"))

    # --- Router ---
    if state == 'IDLE':
        handle_idle_state(event, text, user_id)
    elif state.startswith('REPAIR_'):
        handle_repair_flow(event, text, user_id, state, is_image)
    elif state.startswith('ORG_'):
        handle_org_flow(event, text, user_id, state, is_image)
    elif state.startswith('INQUIRY_'):
        handle_inquiry_flow(event, text, user_id, state, is_image)
    elif state == 'CCTV_SELECT_TYPE':
        handle_cctv_flow(event, text, user_id)

# --- Flow Handlers ---

def handle_idle_state(event, text, user_id):
    if text in ["ติดต่อเรา", "แผนที่"]:
        line_bot_api.reply_message(event.reply_token, create_location_card())
    elif text == "แจ้งซ่อม":
        sessions[user_id] = 'REPAIR_SELECT_TYPE'
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
            QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
            QuickReplyButton(action=MessageAction(label="⌨️ อุปกรณ์อื่นๆ", text="อุปกรณ์คอมพิวเตอร์"))
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🔧 ต้องการซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=quick_reply))
    elif text == "สั่งซื้อหน่วยงาน":
        sessions[user_id] = 'ORG_WAIT_NAME'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🏢 ขอทราบชื่อหน่วยงานของท่านครับ?"))
    elif text == "สอบถามสินค้า":
        sessions[user_id] = 'INQUIRY_WAIT_PRODUCT'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📦 ต้องการสอบถามข้อมูลสินค้าตัวไหนครับ?"))
    elif text == "ติดตั้งกล้องวงจรปิด":
        sessions[user_id] = 'CCTV_SELECT_TYPE'
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="🏠 Smart Camera", text="Smart Camera")),
            QuickReplyButton(action=MessageAction(label="📹 กล้อง Analog", text="กล้อง Analog")),
            QuickReplyButton(action=MessageAction(label="🌐 IP Camera", text="กล้อง IP Camera")),
            QuickReplyButton(action=MessageAction(label="❓ อื่นๆ", text="อื่นๆ"))
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📹 สนใจติดตั้งกล้องประเภทไหนครับ?", quick_reply=quick_reply))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="👋 สวัสดีครับ พิมพ์ 'ติดต่อเรา' ดูแผนที่ หรือเลือกเมนูรายการได้เลยครับ"))

def handle_repair_flow(event, text, user_id, state, is_image):
    if state == 'REPAIR_SELECT_TYPE':
        if text == "อุปกรณ์คอมพิวเตอร์":
            sessions[user_id] = 'REPAIR_WAIT_DEVICE_NAME'
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ระบุชื่ออุปกรณ์ที่ต้องการซ่อมครับ?"))
        else:
            user_data[user_id] = {'repair_type': text}
            sessions[user_id] = 'REPAIR_WAIT_DETAIL'
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"รับเรื่องซ่อม {text} ครับ\n📝 กรุณาพิมพ์อาการเสียมาได้เลย"))
    
    elif state == 'REPAIR_WAIT_DEVICE_NAME':
        user_data[user_id] = {'repair_type': text}
        sessions[user_id] = 'REPAIR_WAIT_DETAIL'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"โอเคครับ รับซ่อม {text}\n📝 ช่วยบอกอาการเสียหน่อยครับ?"))

    elif state == 'REPAIR_WAIT_DETAIL':
        user_data[user_id]['symptom'] = text
        sessions[user_id] = 'REPAIR_WAIT_IMAGE'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปภาพประกอบไหมครับ?", quick_reply=get_skip_image_quick_reply()))

    elif state == 'REPAIR_WAIT_IMAGE':
        if is_image or text == "ข้าม":
            has_img = "มี (ได้รับแล้ว)" if is_image else "ไม่มี"
            data = user_data.pop(user_id)
            sessions[user_id] = 'IDLE'
            card = create_summary_flex("บันทึกแจ้งซ่อม", "#ff9100", [
                ("ประเภท", data['repair_type']), ("อาการ", data['symptom']), ("รูปภาพแนบ", has_img), ("สถานะ", "รอประเมินราคา")
            ], "กรุณารอแอดมินประเมินราคา", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true")
            line_bot_api.reply_message(event.reply_token, card)

def handle_org_flow(event, text, user_id, state, is_image):
    if state == 'ORG_WAIT_NAME':
        user_data[user_id] = {'org_name': text}
        sessions[user_id] = 'ORG_WAIT_ITEM'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ยินดีต้อนรับ {text} ครับ\n🛒 พิมพ์รายการสินค้าได้เลย"))
    elif state == 'ORG_WAIT_ITEM':
        user_data[user_id]['item_list'] = text
        sessions[user_id] = 'ORG_WAIT_IMAGE'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปตัวอย่างไหมครับ?", quick_reply=get_skip_image_quick_reply()))
    elif state == 'ORG_WAIT_IMAGE':
        if is_image or text == "ข้าม":
            has_img = "มี (ได้รับแล้ว)" if is_image else "ไม่มี"
            data = user_data.pop(user_id)
            sessions[user_id] = 'IDLE'
            card = create_summary_flex("คำสั่งซื้อหน่วยงาน", "#007bff", [
                ("หน่วยงาน", data['org_name']), ("รายการ", data['item_list']), ("รูปภาพแนบ", has_img), ("สถานะ", "รอตรวจสอบสต็อก")
            ], "แอดมินจะรีบส่งใบเสนอราคาให้ครับ", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true")
            line_bot_api.reply_message(event.reply_token, card)

def handle_inquiry_flow(event, text, user_id, state, is_image):
    if state == 'INQUIRY_WAIT_PRODUCT':
        user_data[user_id] = {'product_name': text}
        sessions[user_id] = 'INQUIRY_WAIT_IMAGE'
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปสินค้าไหมครับ?", quick_reply=get_skip_image_quick_reply()))
    elif state == 'INQUIRY_WAIT_IMAGE':
        if is_image or text == "ข้าม":
            has_img = "มี (ได้รับแล้ว)" if is_image else "ไม่มี"
            data = user_data.pop(user_id)
            sessions[user_id] = 'IDLE'
            card = create_summary_flex("สอบถามสินค้า", "#9c27b0", [
                ("สินค้า", data['product_name']), ("รูปภาพแนบ", has_img), ("สถานะ", "รอแอดมินตอบกลับ")
            ], "กำลังเรียกแอดมินครับ", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true")
            line_bot_api.reply_message(event.reply_token, card)

def handle_cctv_flow(event, text, user_id):
    sessions[user_id] = 'IDLE'
    card = create_summary_flex("สนใจติดตั้ง CCTV", "#00c853", [
        ("ประเภท", text), ("สถานะ", "รับเรื่องแล้ว")
    ], "เจ้าหน้าที่จะติดต่อกลับครับ", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true")
    line_bot_api.reply_message(event.reply_token, card)

if __name__ == "__main__":
    app.run(port=5000)
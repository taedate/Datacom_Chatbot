import os
from dotenv import load_dotenv 

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction,
    FlexSendMessage, BubbleContainer, BoxComponent, 
    TextComponent, SeparatorComponent
)

app = Flask(__name__)
load_dotenv()

channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

sessions = {} 
user_data = {} 

# --- ฟังก์ชันสร้าง Flex Message สวยๆ (การ์ดสรุปผล) ---
def create_summary_flex(title, color, items, footer_text):
    """
    title: หัวข้อการ์ด (เช่น แจ้งซ่อมสำเร็จ)
    color: สีแถบหัวข้อ (Hex Code เช่น #00b900)
    items: ข้อมูลที่จะแสดงในลิสต์ [('หัวข้อ', 'เนื้อหา'), ...]
    footer_text: ข้อความปิดท้าย
    """
    # ส่วนเนื้อหา (Body)
    body_contents = []
    for label, value in items:
        body_contents.append(BoxComponent(
            layout='baseline',
            spacing='sm',
            contents=[
                TextComponent(text=label, color='#aaaaaa', size='sm', flex=2),
                TextComponent(text=value, wrap=True, color='#666666', size='sm', flex=5)
            ]
        ))

    # ประกอบร่างเป็น Bubble
    bubble = BubbleContainer(
        header=BoxComponent(
            layout='vertical',
            backgroundColor=color,
            contents=[
                TextComponent(text=title, weight='bold', color='#ffffff', size='lg')
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            contents=body_contents
        ),
        footer=BoxComponent(
            layout='vertical',
            contents=[
                SeparatorComponent(),
                BoxComponent(
                    layout='vertical',
                    padding_top='md',
                    contents=[
                        TextComponent(text=footer_text, color='#aaaaaa', size='xs', align='center')
                    ]
                )
            ]
        )
    )
    return FlexSendMessage(alt_text=title, contents=bubble)

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
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการแล้วครับ เลือกเมนูใหม่ได้เลย"))
        return

    # =================================================================
    # STATE: IDLE
    # =================================================================
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
            reply_msgs.append(TextSendMessage(text="📦 ต้องการสอบถามข้อมูลสินค้าตัวไหนครับ?\n(พิมพ์ชื่อสินค้าหรือรุ่นได้เลย)"))

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
            reply_msgs.append(TextSendMessage(text="👋 สวัสดีครับ กรุณาเลือกรายการจากเมนูด้านล่างได้เลยครับ"))

    # =================================================================
    # FLOW 1: แจ้งซ่อม 
    # =================================================================
    elif current_state == 'REPAIR_SELECT_TYPE':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['repair_type'] = msg
        sessions[user_id] = 'REPAIR_WAIT_DETAIL'
        reply_msgs.append(TextSendMessage(text=f"รับเรื่องซ่อม {msg} ครับ\n📝 กรุณาพิมพ์อาการเสียหรือปัญหาที่เจอให้หน่อยครับ"))

    elif current_state == 'REPAIR_WAIT_DETAIL':
        repair_type = user_data[user_id].get('repair_type')
        symptom = msg
        
        # สร้าง Flex Message สรุปผล (สีส้ม)
        flex_msg = create_summary_flex(
            title="บันทึกแจ้งซ่อม",
            color="#ff9100", # สีส้ม
            items=[
                ("ประเภท", repair_type),
                ("อาการ", symptom),
                ("สถานะ", "รอประเมินราคา")
            ],
            footer_text="กรุณารอแอดมินประเมินราคาและติดต่อกลับ"
        )
        reply_msgs.append(flex_msg)
        
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # =================================================================
    # FLOW 2: สั่งซื้อหน่วยงาน
    # =================================================================
    elif current_state == 'ORG_WAIT_NAME':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['org_name'] = msg
        sessions[user_id] = 'ORG_WAIT_ITEM'
        reply_msgs.append(TextSendMessage(text=f"ยินดีต้อนรับ {msg} ครับ\n🛒 กรุณาพิมพ์รายการสินค้าที่ต้องการสั่งซื้อได้เลยครับ"))

    elif current_state == 'ORG_WAIT_ITEM':
        org_name = user_data[user_id].get('org_name')
        item_list = msg
        
        # สร้าง Flex Message สรุปผล (สีน้ำเงิน)
        flex_msg = create_summary_flex(
            title="คำสั่งซื้อหน่วยงาน",
            color="#007bff", # สีน้ำเงิน
            items=[
                ("หน่วยงาน", org_name),
                ("รายการ", item_list),
                ("สถานะ", "รอตรวจสอบสต็อก")
            ],
            footer_text="แอดมินจะรีบตรวจสอบและส่งใบเสนอราคาให้ครับ"
        )
        reply_msgs.append(flex_msg)
        
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # =================================================================
    # FLOW 3: สอบถามสินค้า
    # =================================================================
    elif current_state == 'INQUIRY_WAIT_PRODUCT':
        product_name = msg
        
        # สร้าง Flex Message (สีม่วง)
        flex_msg = create_summary_flex(
            title="สอบถามสินค้า",
            color="#9c27b0", # สีม่วง
            items=[
                ("สินค้า", product_name),
                ("สถานะ", "รอแอดมินตอบกลับ")
            ],
            footer_text="กำลังเรียกแอดมินมาตอบข้อมูลครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'

    # =================================================================
    # FLOW 4: ติดตั้งกล้องวงจรปิด
    # =================================================================
    elif current_state == 'CCTV_SELECT_TYPE':
        cctv_type = msg
        
        # สร้าง Flex Message (สีเขียว)
        flex_msg = create_summary_flex(
            title="สนใจติดตั้ง CCTV",
            color="#00c853", # สีเขียว
            items=[
                ("ประเภท", cctv_type),
                ("สถานะ", "รับเรื่องแล้ว")
            ],
            footer_text="เจ้าหน้าที่จะติดต่อกลับเพื่อสำรวจหน้างานครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'

    if reply_msgs:
        line_bot_api.reply_message(event.reply_token, reply_msgs)

@app.route("/")
def hello():
    return "Hello World"

if __name__ == "__main__":
    app.run(port=5000)
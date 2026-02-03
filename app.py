import os
from dotenv import load_dotenv 

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction,
    FlexSendMessage, BubbleContainer, BoxComponent, 
    TextComponent, SeparatorComponent, ImageComponent,
    ButtonComponent, URIAction, CarouselContainer
)

app = Flask(__name__)
load_dotenv()

channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

sessions = {} 
user_data = {} 

# --- 1. ฟังก์ชันสร้าง Summary Flex Message (การ์ดสรุปงาน) ---
def create_summary_flex(title, color, items, footer_text, image_url=None):
    
    # Header
    header_box = BoxComponent(
        layout='vertical',
        backgroundColor=color,
        contents=[TextComponent(text=title, weight='bold', color='#ffffff', size='lg')]
    )

    # Hero Image (ปรับขนาดใหม่)
    hero_image = None
    if image_url:
        hero_image = ImageComponent(
            url=image_url,
            size='full',
            # --- จุดที่แก้ไข ---
            # ปรับ aspect_ratio ให้กว้างขึ้น เพื่อลดความสูงของกล่อง
            # ลองใช้ 2:1 (พอดีรูปคุณ) หรือ 2.35:1 (แบบโรงหนัง จะดูเพรียวลงอีก)
            aspect_ratio='2.35:1', 
            # aspect_mode='cover' จะตัดส่วนเกินออกให้เต็มกรอบ
            # aspect_mode='fit' จะย่อรูปให้เห็นครบ แต่จะมีขอบขาว
            aspect_mode='cover' 
        )

    # Body
    body_contents = []
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

    # ประกอบร่าง Bubble
    bubble = BubbleContainer(
        header=header_box,
        hero=hero_image, 
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


# --- 2. ฟังก์ชันสร้าง Location Card (การ์ดแผนที่) ---
def create_location_card():
    # รูปแผนที่
    map_image_url = "https://github.com/taedate/datacom-image/blob/main/Datacom.jpg?raw=true"
    
    bubble = BubbleContainer(
        direction='ltr',
        hero=ImageComponent(
            url=map_image_url,
            size='full',
            # --- จุดที่แก้ไข ---
            # ปรับลดความสูงลงจากเดิม 20:13 (สูงมาก) เป็น 2.35:1 (เตี้ยลง)
            aspect_ratio='2.35:1', 
            aspect_mode='cover',
            action=URIAction(uri='https://www.google.com/maps') 
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text='Datacom Service', weight='bold', size='xl'),
                BoxComponent(
                    layout='vertical',
                    margin='lg',
                    spacing='sm',
                    contents=[
                        BoxComponent(
                            layout='baseline',
                            spacing='sm',
                            contents=[
                                TextComponent(text='ที่อยู่', color='#aaaaaa', size='sm', flex=1),
                                TextComponent(text='123 ถ.สุขุมวิท กทม. 10110', wrap=True, color='#666666', size='sm', flex=5)
                            ]
                        ),
                        BoxComponent(
                            layout='baseline',
                            spacing='sm',
                            contents=[
                                TextComponent(text='เวลา', color='#aaaaaa', size='sm', flex=1),
                                TextComponent(text='09:00 - 18:00 น. (จ-ส)', wrap=True, color='#666666', size='sm', flex=5)
                            ]
                        ),
                    ]
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            spacing='sm',
            contents=[
                ButtonComponent(
                    style='primary',
                    height='sm',
                    action=URIAction(label='โทรติดต่อ', uri='tel:0812345678')
                ),
                ButtonComponent(
                    style='secondary',
                    height='sm',
                    action=URIAction(label='แผนที่นำทาง', uri='https://www.google.com/maps')
                )
            ]
        )
    )
    return FlexSendMessage(alt_text="ที่ตั้งร้าน", contents=bubble)

# -----------------------------------------------
# ส่วน Callback และ Handle Message ใช้ของเดิมได้เลยครับ (ไม่มีการเปลี่ยนแปลง)
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

    # =================================================================
    # STATE: IDLE (เมนูหลัก)
    # =================================================================
    if current_state == 'IDLE':
        
        # 1. ดูแผนที่ร้าน
        if msg == "ติดต่อเรา" or msg == "แผนที่":
            flex_msg = create_location_card()
            reply_msgs.append(flex_msg)

        # 2. แจ้งซ่อม
        elif msg == "แจ้งซ่อม": 
            sessions[user_id] = 'REPAIR_SELECT_TYPE'
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
                QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
                QuickReplyButton(action=MessageAction(label="⌨️ อุปกรณ์อื่นๆ", text="อุปกรณ์คอมพิวเตอร์"))
            ])
            reply_msgs.append(TextSendMessage(text="🔧 ต้องการซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=quick_reply))

        # 3. สั่งซื้อหน่วยงาน
        elif msg == "สั่งซื้อหน่วยงาน":
            sessions[user_id] = 'ORG_WAIT_NAME'
            reply_msgs.append(TextSendMessage(text="🏢 ขอทราบชื่อหน่วยงานของท่านครับ?"))

        # 4. สอบถามสินค้า
        elif msg == "สอบถามสินค้า":
            sessions[user_id] = 'INQUIRY_WAIT_PRODUCT'
            reply_msgs.append(TextSendMessage(text="📦 ต้องการสอบถามข้อมูลสินค้าตัวไหนครับ?"))

        # 5. ติดตั้งกล้อง
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
            # Default response
            reply_msgs.append(TextSendMessage(text="👋 สวัสดีครับ พิมพ์ 'ติดต่อเรา' เพื่อดูแผนที่ หรือเลือกเมนูรายการได้เลยครับ"))

    # =================================================================
    # FLOW 1: แจ้งซ่อม (มี Logic อุปกรณ์อื่นๆ)
    # =================================================================
    elif current_state == 'REPAIR_SELECT_TYPE':
        # กรณีเลือก "อุปกรณ์อื่นๆ" -> ไปถามชื่อก่อน
        if msg == "อุปกรณ์คอมพิวเตอร์":
            sessions[user_id] = 'REPAIR_WAIT_DEVICE_NAME'
            reply_msgs.append(TextSendMessage(text="ระบุชื่ออุปกรณ์ที่ต้องการซ่อมครับ?"))
        
        # กรณีเลือก คอม/ปริ้นเตอร์ -> ข้ามไปถามอาการเลย
        else:
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id]['repair_type'] = msg
            sessions[user_id] = 'REPAIR_WAIT_DETAIL'
            reply_msgs.append(TextSendMessage(text=f"รับเรื่องซ่อม {msg} ครับ\n📝 กรุณาพิมพ์อาการเสียมาได้เลย"))

    elif current_state == 'REPAIR_WAIT_DEVICE_NAME':
        # รับชื่ออุปกรณ์ที่พิมพ์มา
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['repair_type'] = msg 
        
        sessions[user_id] = 'REPAIR_WAIT_DETAIL'
        reply_msgs.append(TextSendMessage(text=f"โอเคครับ รับซ่อม {msg}\n📝 ช่วยบอกอาการเสียหน่อยครับ?"))

    elif current_state == 'REPAIR_WAIT_DETAIL':
        # จบ Flow ซ่อม -> แสดง Card
        repair_type = user_data[user_id].get('repair_type')
        symptom = msg
        
        img_url = "https://github.com/taedate/datacom-image/blob/main/reply.png?raw=true"
        
        # เรียกใช้ create_summary_flex ตรงนี้
        flex_msg = create_summary_flex(
            title="บันทึกแจ้งซ่อม",
            color="#ff9100",
            image_url=img_url,
            items=[("ประเภท", repair_type), ("อาการ", symptom), ("สถานะ", "รอประเมินราคา")],
            footer_text="กรุณารอแอดมินประเมินราคา"
        )
        reply_msgs.append(flex_msg)
        
        # Reset
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # =================================================================
    # FLOW 2: สั่งซื้อหน่วยงาน
    # =================================================================
    elif current_state == 'ORG_WAIT_NAME':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['org_name'] = msg
        sessions[user_id] = 'ORG_WAIT_ITEM'
        reply_msgs.append(TextSendMessage(text=f"ยินดีต้อนรับ {msg} ครับ\n🛒 พิมพ์รายการสินค้าได้เลย"))

    elif current_state == 'ORG_WAIT_ITEM':
        # จบ Flow สั่งซื้อ -> แสดง Card
        org_name = user_data[user_id].get('org_name')
        item_list = msg
        
        img_url = "https://github.com/taedate/datacom-image/blob/main/reply.png?raw=true"

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

    # =================================================================
    # FLOW 3: สอบถามสินค้า
    # =================================================================
    elif current_state == 'INQUIRY_WAIT_PRODUCT':
        # จบ Flow สอบถาม -> แสดง Card
        product_name = msg
        
        img_url = "https://github.com/taedate/datacom-image/blob/main/reply.png?raw=true"

        flex_msg = create_summary_flex(
            title="สอบถามสินค้า",
            color="#9c27b0",
            image_url=img_url,
            items=[("สินค้า", product_name), ("สถานะ", "รอแอดมินตอบกลับ")],
            footer_text="กำลังเรียกแอดมินครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'

    # =================================================================
    # FLOW 4: CCTV
    # =================================================================
    elif current_state == 'CCTV_SELECT_TYPE':
        # จบ Flow กล้อง -> แสดง Card
        cctv_type = msg
        
        img_url = "https://github.com/taedate/datacom-image/blob/main/reply.png?raw=true"

        flex_msg = create_summary_flex(
            title="สนใจติดตั้ง CCTV",
            color="#00c853",
            image_url=img_url,
            items=[("ประเภท", cctv_type), ("สถานะ", "รับเรื่องแล้ว")],
            footer_text="เจ้าหน้าที่จะติดต่อกลับครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'

    # ส่งข้อความทั้งหมด
    if reply_msgs:
        line_bot_api.reply_message(event.reply_token, reply_msgs)

if __name__ == "__main__":
    app.run(port=5000)
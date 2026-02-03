import os
from dotenv import load_dotenv 

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage,
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

def get_skip_image_quick_reply():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ไม่ใส่รูป (ข้าม)", text="ข้าม"))
    ])

# --- 1. ฟังก์ชันสร้าง Summary Flex Message (แบบ Compact: ข้อความทับรูป 4:3) ---
def create_summary_flex(title, color, items, footer_text, image_url=None):
    
    # 1. เตรียมเนื้อหาที่จะแสดง (Title + รายละเอียด)
    content_list = []
    
    # หัวข้อ (Title)
    content_list.append(TextComponent(text=title, weight='bold', color='#ffffff', size='lg'))
    
    # รายการย่อย (Items)
    for label, value in items:
        content_list.append(BoxComponent(
            layout='baseline',
            spacing='sm',
            contents=[
                TextComponent(text=label, color='#cccccc', size='xs', flex=2), # สีเทาอ่อน
                TextComponent(text=value, wrap=True, color='#ffffff', size='xs', flex=5) # สีขาว
            ]
        ))
        
    # ข้อความปิดท้าย (Footer)
    content_list.append(TextComponent(text=footer_text, color='#aaaaaa', size='xxs', margin='md', align='left'))

    # 2. สร้างกล่องข้อความโปร่งแสง (Overlay Box)
    overlay_box = BoxComponent(
        layout='vertical',
        position='absolute',     # สั่งให้ลอยทับ
        backgroundColor='#000000cc', # สีดำโปร่งแสง
        offsetBottom='0px',      # ชิดขอบล่าง
        start='0px',             # ชิดขอบซ้าย
        end='0px',               # ชิดขอบขวา
        paddingAll='md',         # เว้นระยะขอบใน
        contents=content_list    # เอาเนื้อหาใส่เข้าไป
    )

    # 3. สร้างรูปภาพพื้นหลัง (Main Image)
    # ถ้าไม่มีรูป ให้ใช้รูป Placeholder
    final_image_url = image_url if image_url else "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
    
    main_image = ImageComponent(
        url=final_image_url,
        size='full',
        aspect_ratio='4:3',      # <--- ปรับเป็น 4:3 ตามที่ต้องการ (Card จะทรงเกือบจัตุรัส)
        aspect_mode='cover'      # ขยายเต็มพื้นที่
    )

    # 4. ประกอบร่าง
    bubble = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            paddingAll='none',   # ไม่เอาขอบขาวรอบๆ
            contents=[
                main_image,      # ชั้นล่าง: รูปภาพ
                overlay_box      # ชั้นบน: ข้อความทับรูป
            ]
        ),
        # ใส่ขีดสีด้านบน เพื่อบอกประเภทงาน (สีส้ม/ฟ้า/ม่วง)
        styles={'body': {'borderTopColor': color, 'borderTopWidth': '5px'}} 
    )
    
    return FlexSendMessage(alt_text=title, contents=bubble)


# --- 2. ฟังก์ชันสร้าง Location Card (เหมือนเดิม) ---
def create_location_card():
    map_image_url = "https://github.com/taedate/datacom-image/blob/main/Datacom.jpg?raw=true"
    bubble = BubbleContainer(
        direction='ltr',
        hero=ImageComponent(
            url=map_image_url,
            size='full',
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

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(403)
    return 'OK', 200

# --- HANDLER หลัก ---
@handler.add(MessageEvent, message=(TextMessage, ImageMessage))
def handle_message(event):
    user_id = event.source.user_id 
    current_state = sessions.get(user_id, 'IDLE')
    reply_msgs = []
    
    msg_text = ""
    is_image = False
    
    if isinstance(event.message, TextMessage):
        msg_text = event.message.text.strip()
    elif isinstance(event.message, ImageMessage):
        is_image = True
        msg_text = "__IMAGE_UPLOADED__"

    if msg_text == "ยกเลิก":
        sessions[user_id] = 'IDLE'
        if user_id in user_data: del user_data[user_id]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อย"))
        return

    if current_state == 'IDLE':
        if msg_text == "ติดต่อเรา" or msg_text == "แผนที่":
            flex_msg = create_location_card()
            reply_msgs.append(flex_msg)
        elif msg_text == "แจ้งซ่อม": 
            sessions[user_id] = 'REPAIR_SELECT_TYPE'
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
                QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
                QuickReplyButton(action=MessageAction(label="⌨️ อุปกรณ์อื่นๆ", text="อุปกรณ์คอมพิวเตอร์"))
            ])
            reply_msgs.append(TextSendMessage(text="🔧 ต้องการซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=quick_reply))
        elif msg_text == "สั่งซื้อหน่วยงาน":
            sessions[user_id] = 'ORG_WAIT_NAME'
            reply_msgs.append(TextSendMessage(text="🏢 ขอทราบชื่อหน่วยงานของท่านครับ?"))
        elif msg_text == "สอบถามสินค้า":
            sessions[user_id] = 'INQUIRY_WAIT_PRODUCT'
            reply_msgs.append(TextSendMessage(text="📦 ต้องการสอบถามข้อมูลสินค้าตัวไหนครับ?"))
        elif msg_text == "ติดตั้งกล้องวงจรปิด":
            sessions[user_id] = 'CCTV_SELECT_TYPE'
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="🏠 Smart Camera", text="Smart Camera")),
                QuickReplyButton(action=MessageAction(label="📹 กล้อง Analog", text="กล้อง Analog")),
                QuickReplyButton(action=MessageAction(label="🌐 IP Camera", text="กล้อง IP Camera")),
                QuickReplyButton(action=MessageAction(label="❓ อื่นๆ", text="อื่นๆ"))
            ])
            reply_msgs.append(TextSendMessage(text="📹 สนใจติดตั้งกล้องประเภทไหนครับ?", quick_reply=quick_reply))
        else:
            if not is_image:
                reply_msgs.append(TextSendMessage(text="👋 สวัสดีครับ พิมพ์ 'ติดต่อเรา' ดูแผนที่ หรือเลือกเมนูรายการได้เลยครับ"))

    # --- FLOW 1: แจ้งซ่อม ---
    elif current_state == 'REPAIR_SELECT_TYPE':
        if msg_text == "อุปกรณ์คอมพิวเตอร์":
            sessions[user_id] = 'REPAIR_WAIT_DEVICE_NAME'
            reply_msgs.append(TextSendMessage(text="ระบุชื่ออุปกรณ์ที่ต้องการซ่อมครับ?"))
        else:
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id]['repair_type'] = msg_text
            sessions[user_id] = 'REPAIR_WAIT_DETAIL'
            reply_msgs.append(TextSendMessage(text=f"รับเรื่องซ่อม {msg_text} ครับ\n📝 กรุณาพิมพ์อาการเสียมาได้เลย"))

    elif current_state == 'REPAIR_WAIT_DEVICE_NAME':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['repair_type'] = msg_text 
        sessions[user_id] = 'REPAIR_WAIT_DETAIL'
        reply_msgs.append(TextSendMessage(text=f"โอเคครับ รับซ่อม {msg_text}\n📝 ช่วยบอกอาการเสียหน่อยครับ?"))

    elif current_state == 'REPAIR_WAIT_DETAIL':
        user_data[user_id]['symptom'] = msg_text
        sessions[user_id] = 'REPAIR_WAIT_IMAGE'
        reply_msgs.append(TextSendMessage(
            text="📸 มีรูปภาพประกอบอาการเสียไหมครับ?\n(ส่งรูปมาได้เลย หรือกดปุ่ม 'ข้าม' ถ้าไม่มี)",
            quick_reply=get_skip_image_quick_reply()
        ))

    elif current_state == 'REPAIR_WAIT_IMAGE':
        has_image = "ไม่มี"
        if is_image:
            has_image = "มี (ได้รับแล้ว)"
        elif msg_text == "ข้าม":
            has_image = "ไม่มี"
        else:
            reply_msgs.append(TextSendMessage(text="กรุณาส่งรูป หรือกดปุ่ม 'ข้าม' ครับ", quick_reply=get_skip_image_quick_reply()))
            line_bot_api.reply_message(event.reply_token, reply_msgs)
            return

        repair_type = user_data[user_id].get('repair_type')
        symptom = user_data[user_id].get('symptom')
        # ใส่รูป Default กรณี user ไม่ได้อัปโหลด
        img_url = "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        
        flex_msg = create_summary_flex(
            title="บันทึกแจ้งซ่อม",
            color="#ff9100", # สีส้ม
            image_url=img_url,
            items=[
                ("ประเภท", repair_type), 
                ("อาการ", symptom), 
                ("รูปภาพแนบ", has_image),
                ("สถานะ", "รอประเมินราคา")
            ],
            footer_text="กรุณารอแอดมินประเมินราคา"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # --- FLOW 2: สั่งซื้อหน่วยงาน ---
    elif current_state == 'ORG_WAIT_NAME':
        if user_id not in user_data: user_data[user_id] = {}
        user_data[user_id]['org_name'] = msg_text
        sessions[user_id] = 'ORG_WAIT_ITEM'
        reply_msgs.append(TextSendMessage(text=f"ยินดีต้อนรับ {msg_text} ครับ\n🛒 พิมพ์รายการสินค้าได้เลย"))

    elif current_state == 'ORG_WAIT_ITEM':
        user_data[user_id]['item_list'] = msg_text
        sessions[user_id] = 'ORG_WAIT_IMAGE'
        reply_msgs.append(TextSendMessage(
            text="📸 มีรูปตัวอย่างสินค้าหรือใบสั่งซื้อไหมครับ?\n(ส่งรูปมาได้เลย หรือกดปุ่ม 'ข้าม')",
            quick_reply=get_skip_image_quick_reply()
        ))

    elif current_state == 'ORG_WAIT_IMAGE':
        has_image = "ไม่มี"
        if is_image:
            has_image = "มี (ได้รับแล้ว)"
        elif msg_text == "ข้าม":
            has_image = "ไม่มี"
        else:
            reply_msgs.append(TextSendMessage(text="กรุณาส่งรูป หรือกดปุ่ม 'ข้าม' ครับ", quick_reply=get_skip_image_quick_reply()))
            line_bot_api.reply_message(event.reply_token, reply_msgs)
            return

        org_name = user_data[user_id].get('org_name')
        item_list = user_data[user_id].get('item_list')
        img_url = "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"

        flex_msg = create_summary_flex(
            title="คำสั่งซื้อหน่วยงาน",
            color="#007bff", # สีน้ำเงิน
            image_url=img_url,
            items=[
                ("หน่วยงาน", org_name), 
                ("รายการ", item_list), 
                ("รูปภาพแนบ", has_image),
                ("สถานะ", "รอตรวจสอบสต็อก")
            ],
            footer_text="แอดมินจะรีบส่งใบเสนอราคาให้ครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # --- FLOW 3: สอบถามสินค้า ---
    elif current_state == 'INQUIRY_WAIT_PRODUCT':
        user_data[user_id] = {'product_name': msg_text}
        sessions[user_id] = 'INQUIRY_WAIT_IMAGE'
        reply_msgs.append(TextSendMessage(
            text="📸 มีรูปตัวอย่างสินค้าไหมครับ?\n(ส่งรูปมาได้เลย หรือกดปุ่ม 'ข้าม')",
            quick_reply=get_skip_image_quick_reply()
        ))
    
    elif current_state == 'INQUIRY_WAIT_IMAGE':
        has_image = "ไม่มี"
        if is_image:
            has_image = "มี (ได้รับแล้ว)"
        elif msg_text == "ข้าม":
            has_image = "ไม่มี"
        else:
            reply_msgs.append(TextSendMessage(text="กรุณาส่งรูป หรือกดปุ่ม 'ข้าม' ครับ", quick_reply=get_skip_image_quick_reply()))
            line_bot_api.reply_message(event.reply_token, reply_msgs)
            return

        product_name = user_data[user_id].get('product_name')
        img_url = "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"

        flex_msg = create_summary_flex(
            title="สอบถามสินค้า",
            color="#9c27b0", # สีม่วง
            image_url=img_url,
            items=[
                ("สินค้า", product_name), 
                ("รูปภาพแนบ", has_image),
                ("สถานะ", "รอแอดมินตอบกลับ")
            ],
            footer_text="กำลังเรียกแอดมินครับ"
        )
        reply_msgs.append(flex_msg)
        sessions[user_id] = 'IDLE'
        del user_data[user_id]

    # --- FLOW 4: CCTV ---
    elif current_state == 'CCTV_SELECT_TYPE':
        cctv_type = msg_text
        img_url = "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        flex_msg = create_summary_flex(
            title="สนใจติดตั้ง CCTV",
            color="#00c853", # สีเขียว
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
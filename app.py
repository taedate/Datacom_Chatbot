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
    ButtonComponent, URIAction, CarouselContainer # <--- เพิ่ม CarouselContainer
)

app = Flask(__name__)
load_dotenv()

channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN', '')
channel_secret = os.environ.get('CHANNEL_SECRET', '')

line_bot_api = LineBotApi(channel_access_token)
handler = WebhookHandler(channel_secret)

sessions = {} 
user_data = {} 

# --- ฟังก์ชันสร้าง Flex Message (แบบเดิม) ---
def create_summary_flex(title, color, items, footer_text, image_url=None):
    # ... (ใช้โค้ดเดิมจากข้อที่แล้วได้เลยครับ) ...
    # (เพื่อความกระชับ ผมขอละไว้ในส่วนนี้นะครับ ให้ใช้ตัวเดิมได้เลย)
    
    # Copy โค้ด create_summary_flex จากอันเก่ามาแปะตรงนี้
    # ...
    
    # ขอเขียนย่อไว้เพื่อให้โค้ดไม่ยาวเกินไปนะครับ
    header_box = BoxComponent(layout='vertical', backgroundColor=color, contents=[TextComponent(text=title, weight='bold', color='#ffffff', size='lg')])
    hero_image = ImageComponent(url=image_url, size='full', aspect_ratio='1.91:1', aspect_mode='cover') if image_url else None
    body_contents = [TextComponent(text='รายละเอียด', weight='bold', size='md', margin='md')]
    for label, value in items:
        body_contents.append(BoxComponent(layout='baseline', spacing='sm', margin='sm', contents=[TextComponent(text=label, color='#aaaaaa', size='sm', flex=2), TextComponent(text=value, wrap=True, color='#666666', size='sm', flex=5)]))
    
    return FlexSendMessage(alt_text=title, contents=BubbleContainer(header=header_box, hero=hero_image, body=BoxComponent(layout='vertical', contents=body_contents), footer=BoxComponent(layout='vertical', contents=[SeparatorComponent(), BoxComponent(layout='vertical', padding_top='md', contents=[TextComponent(text=footer_text, color='#aaaaaa', size='xs', align='center')])])))


# --- [ใหม่] ฟังก์ชันสร้าง Location Card (การ์ดสถานที่) ---
def create_location_card():
    """
    สร้าง Flex Message แบบ Carousel (เลื่อนได้) หรือ Bubble เดียว
    สำหรับแสดงที่ตั้งร้าน
    """
    
    # รูปแผนที่ (คุณสามารถแคปรูป Map จริงๆ แล้วอัปโหลดได้)
    map_image_url = "https://github.com/taedate/datacom-image/blob/main/Datacom.jpg?raw=true"
    
    bubble = BubbleContainer(
        direction='ltr',
        hero=ImageComponent(
            url=map_image_url,
            size='full',
            aspect_ratio='20:13',
            aspect_mode='cover',
            action=URIAction(uri='https://maps.app.goo.gl/NrRpbYwrZxsgQe69A') # ลิงก์กดที่รูปแล้วไป Google Map
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                # ชื่อร้าน
                TextComponent(text='Datacom Service', weight='bold', size='xl'),
                # ที่อยู่
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
                                TextComponent(text='123 ถ.สุขุมวิท แขวงคลองเตย เขตคลองเตย กทม. 10110', wrap=True, color='#666666', size='sm', flex=5)
                            ]
                        ),
                        BoxComponent(
                            layout='baseline',
                            spacing='sm',
                            contents=[
                                TextComponent(text='เวลา', color='#aaaaaa', size='sm', flex=1),
                                TextComponent(text='09:00 - 18:00 น. (จันทร์-เสาร์)', wrap=True, color='#666666', size='sm', flex=5)
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
                # ปุ่ม Call Action
                ButtonComponent(
                    style='primary',
                    height='sm',
                    action=URIAction(label='โทรติดต่อ', uri='tel:0812345678')
                ),
                # ปุ่ม Map Action
                ButtonComponent(
                    style='secondary',
                    height='sm',
                    action=URIAction(label='แผนที่นำทาง', uri='https://maps.app.goo.gl/ExampleLink') # ใส่ลิงก์ Google Map จริงตรงนี้
                ),
                # ปุ่ม Website (ถ้ามี)
                ButtonComponent(
                    style='link',
                    height='sm',
                    action=URIAction(label='เว็บไซต์', uri='https://www.google.com')
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = event.message.text.strip()
    user_id = event.source.user_id 
    current_state = sessions.get(user_id, 'IDLE')
    reply_msgs = []

    if msg == "ยกเลิก":
        sessions[user_id] = 'IDLE'
        if user_id in user_data: del user_data[user_id]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อย"))
        return

    # --- STATE: IDLE ---
    if current_state == 'IDLE':
        
        # [ใหม่] เพิ่มเงื่อนไขสำหรับดูที่ตั้งร้าน
        if msg == "ติดต่อเรา" or msg == "แผนที่":
            flex_msg = create_location_card()
            reply_msgs.append(flex_msg)

        elif msg == "แจ้งซ่อม": 
            sessions[user_id] = 'REPAIR_SELECT_TYPE'
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
                QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
                QuickReplyButton(action=MessageAction(label="⌨️ อุปกรณ์อื่นๆ", text="อุปกรณ์คอมพิวเตอร์"))
            ])
            reply_msgs.append(TextSendMessage(text="🔧 ต้องการซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=quick_reply))

        # ... (เงื่อนไขอื่นๆ เหมือนเดิม) ...
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
            # ถ้าไม่ตรงเงื่อนไขข้างบนเลย
            reply_msgs.append(TextSendMessage(text="สวัสดีครับ พิมพ์ 'ติดต่อเรา' เพื่อดูแผนที่ร้าน หรือเลือกเมนูด้านล่างได้เลยครับ"))

    # ... (ส่วน Logic Flow อื่นๆ เหมือนเดิม ไม่ต้องแก้ครับ) ...
    # เพื่อประหยัดพื้นที่ ผมขอละไว้ แต่คุณใช้โค้ดเดิมส่วน Flow 1-4 ต่อท้ายตรงนี้ได้เลยครับ
    # ...
    
    # (อย่าลืมแปะโค้ด Flow 1-4 ตรงนี้นะครับ ถ้าเอาไปรันจริง)
    
    # --- ตัวอย่าง Flow 1 (เอามาแปะให้ดูเป็นตัวอย่างว่าวางตรงไหน) ---
    elif current_state == 'REPAIR_SELECT_TYPE':
        if msg == "อุปกรณ์คอมพิวเตอร์":
            sessions[user_id] = 'REPAIR_WAIT_DEVICE_NAME'
            reply_msgs.append(TextSendMessage(text="ระบุชื่ออุปกรณ์ที่ต้องการซ่อมครับ?"))
        else:
            if user_id not in user_data: user_data[user_id] = {}
            user_data[user_id]['repair_type'] = msg
            sessions[user_id] = 'REPAIR_WAIT_DETAIL'
            reply_msgs.append(TextSendMessage(text=f"รับเรื่องซ่อม {msg} ครับ\n📝 กรุณาพิมพ์อาการเสียมาได้เลย"))
            
    # ... (ต่อ Flow อื่นๆ จนจบ) ...

    # ส่งข้อความ
    if reply_msgs:
        line_bot_api.reply_message(event.reply_token, reply_msgs)

if __name__ == "__main__":
    app.run(port=5000)
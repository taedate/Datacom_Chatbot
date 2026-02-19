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

# ================= CONFIG =================
load_dotenv()
app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

sessions = {}
user_data = {}

# ================= FLEX =================
def create_summary_flex(title, color, items, footer_text, image_url=None):
    body_contents = [
        TextComponent(text=title, weight='bold', size='lg', wrap=True),
        SeparatorComponent(margin='md')
    ]

    for label, value in items:
        body_contents.append(
            BoxComponent(
                layout='baseline',
                spacing='sm',
                margin='md',
                contents=[
                    TextComponent(text=label, color='#aaaaaa', size='sm', flex=2),
                    TextComponent(text=value, wrap=True, color='#666666', size='sm', flex=5)
                ]
            )
        )

    footer = BoxComponent(
        layout='vertical',
        margin='lg',
        contents=[
            SeparatorComponent(),
            TextComponent(text=footer_text, color='#aaaaaa', size='xs', align='center', margin='md')
        ]
    )

    bubble = BubbleContainer(
        hero=ImageComponent(url=image_url, size='full', aspect_ratio='4:3', aspect_mode='cover') if image_url else None,
        body=BoxComponent(layout='vertical', paddingAll='lg', contents=body_contents),
        footer=footer
    )

    return FlexSendMessage(alt_text=title, contents=bubble)

def create_location_card():
    return FlexSendMessage(
        alt_text="ที่ตั้งร้าน",
        contents=BubbleContainer(
            hero=ImageComponent(
                url="https://github.com/taedate/datacom-image/blob/main/Datacom.jpg?raw=true",
                size='full', aspect_ratio='2.35:1', aspect_mode='cover',
                action=URIAction(uri="https://www.google.com/maps")
            ),
            body=BoxComponent(
                layout='vertical', paddingAll='lg',
                contents=[
                    TextComponent(text="Datacom Service", weight='bold', size='xl'),
                    BoxComponent(
                        layout='vertical', margin='md',
                        contents=[
                            TextComponent(text="📍 123 ถ.สุขุมวิท กรุงเทพฯ", wrap=True),
                            TextComponent(text="⏰ 09:00 - 18:00 น. (จ-ส)", wrap=True)
                        ]
                    )
                ]
            ),
            footer=BoxComponent(
                layout='vertical',
                contents=[
                    ButtonComponent(style='primary', action=URIAction(label="โทรติดต่อ", uri="tel:0812345678")),
                    ButtonComponent(style='secondary', action=URIAction(label="แผนที่นำทาง", uri="https://www.google.com/maps"))
                ]
            )
        )
    )

# เพิ่มปุ่มยกเลิกในกรณีข้ามรูปภาพ
def skip_image_qr():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ไม่ใส่รูป (ข้าม)", text="ข้าม")),
        QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
    ])

# ฟังก์ชันใหม่ สำหรับปุ่มยกเลิกเดี่ยวๆ เวลาให้กรอกข้อความ
def cancel_qr():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
    ])

# ================= WEBHOOK =================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(403)
    return "OK"

@handler.add(MessageEvent, message=(TextMessage, ImageMessage))
def handle_message(event):
    user_id = event.source.user_id
    state = sessions.get(user_id, "IDLE")

    is_image = isinstance(event.message, ImageMessage)
    text = "__IMAGE__" if is_image else event.message.text.strip()

    if text == "ยกเลิก":
        sessions[user_id] = "IDLE"
        user_data.pop(user_id, None)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อยแล้วครับ"))
        return

    # Route state ไปยัง Flow ต่างๆ
    if state == "IDLE":
        handle_idle(event, text, user_id)
    elif state == "CHECK_STATUS":
        handle_check_status(event, text, user_id)
    elif state.startswith("REPAIR_"):
        handle_repair(event, text, user_id, state, is_image)
    elif state.startswith("ORG_"):
        handle_org(event, text, user_id, state, is_image)
    elif state.startswith("INQUIRY_"):
        handle_inquiry(event, text, user_id, state, is_image)
    elif state.startswith("INSTALL_"):
        handle_install(event, text, user_id, state, is_image)

# ================= FLOWS =================
def handle_idle(event, text, user_id):
    if text in ["ติดต่อเรา", "แผนที่"]:
        line_bot_api.reply_message(event.reply_token, create_location_card())

    elif text == "ตรวจสอบสถานะงานซ่อม":
        sessions[user_id] = "CHECK_STATUS"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔍 รบกวนพิมพ์ 'เบอร์โทรศัพท์' หรือ 'รหัสงานซ่อม' เพื่อตรวจสอบสถานะครับ", quick_reply=cancel_qr())
        )

    elif text == "แจ้งซ่อม":
        sessions[user_id] = "REPAIR_TYPE"
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
            QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
            QuickReplyButton(action=MessageAction(label="⌨️ อื่นๆ", text="อุปกรณ์อื่น")),
            QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="ต้องการซ่อมอะไรครับ?", quick_reply=qr))

    elif text == "สั่งซื้อหน่วยงาน":
        sessions[user_id] = "ORG_DETAIL"
        prompt_text = (
            "รบกวนลูกค้ากรอกข้อมูลต่อไปนี้ครับ\n"
            "ชื่อหน่วยงาน:\n"
            "รายการสินค้าที่ต้องการพร้อมจำนวน:"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=prompt_text, quick_reply=cancel_qr()))

    elif text == "สอบถามสินค้า":
        sessions[user_id] = "INQUIRY_PRODUCT"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📦 สอบถามสินค้าตัวไหนครับ?", quick_reply=cancel_qr()))

    elif text == "งานติดตั้ง":
        sessions[user_id] = "INSTALL_TYPE"
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="📹 กล้องวงจรปิด", text="กล้องวงจรปิด")),
            QuickReplyButton(action=MessageAction(label="🔌 สายแลน", text="สายแลน")),
            QuickReplyButton(action=MessageAction(label="🖥️ ระบบเซิฟเวอร์", text="ระบบเซิฟเวอร์")),
            QuickReplyButton(action=MessageAction(label="📽️ โปรเจคเตอร์", text="โปรเจคเตอร์")),
            QuickReplyButton(action=MessageAction(label="💻 ชุดคอมพิวเตอร์", text="ชุดคอมพิวเตอร์")),
            QuickReplyButton(action=MessageAction(label="🛠️ ติดตั้งอื่นๆ", text="ติดตั้งอื่นๆ")),
            QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="สนใจงานติดตั้งประเภทไหนครับ?", quick_reply=qr))

    else:
        # แนะนำให้ใส่เป็นปุ่มเมนูหลักในกรณีพิมพ์ผิดหรือเริ่มแชท
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="🔧 แจ้งซ่อม", text="แจ้งซ่อม")),
            QuickReplyButton(action=MessageAction(label="🛠️ งานติดตั้ง", text="งานติดตั้ง")),
            QuickReplyButton(action=MessageAction(label="🏢 สั่งซื้อหน่วยงาน", text="สั่งซื้อหน่วยงาน")),
            QuickReplyButton(action=MessageAction(label="📦 สอบถามสินค้า", text="สอบถามสินค้า")),
            QuickReplyButton(action=MessageAction(label="📍 ติดต่อเรา", text="ติดต่อเรา"))
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="👋 สวัสดีครับ ยินดีให้บริการ เลือกเมนูด้านล่างได้เลยครับ", quick_reply=qr)
        )

# ---------- CHECK STATUS ----------
def handle_check_status(event, text, user_id):
    sessions[user_id] = "IDLE"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"กำลังตรวจสอบข้อมูลของ: {text}\n(แอดมินจะรีบแจ้งความคืบหน้าให้ทราบครับ)")
    )

# ---------- REPAIR ----------
def handle_repair(event, text, user_id, state, is_image):
    if state == "REPAIR_TYPE":
        user_data[user_id] = {"type": text}
        sessions[user_id] = "REPAIR_DETAIL"
        prompt_text = (
            "รบกวนลูกค้ากรอกข้อมูลต่อไปนี้ครับ\nอุปกรณ์ที่ต้องการซ่อม:\nยี่ห้อ:\nรุ่น:\nอาการ/รายละเอียด:"
            if text == "อุปกรณ์อื่น" else
            "รบกวนลูกค้ากรอกข้อมูลต่อไปนี้ครับ\nยี่ห้อ:\nรุ่น:\nอาการ/รายละเอียด:"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=prompt_text, quick_reply=cancel_qr()))

    elif state == "REPAIR_DETAIL":
        user_data[user_id]["detail"] = text
        sessions[user_id] = "REPAIR_IMAGE"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปไหมครับ?", quick_reply=skip_image_qr()))

    elif state == "REPAIR_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"
        card = create_summary_flex(
            "บันทึกแจ้งซ่อม", "#ff9800",
            [("อุปกรณ์", data["type"]), ("รายละเอียด", data["detail"]), ("รูปภาพ", "มี" if is_image else "ไม่มี"), ("สถานะ", "รอประเมินราคา")],
            "แอดมินจะติดต่อกลับครับ", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- ORG ----------
def handle_org(event, text, user_id, state, is_image):
    if state == "ORG_DETAIL":
        user_data[user_id] = {"detail": text}
        sessions[user_id] = "ORG_IMAGE"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📸 มีรูปไหมครับ?", quick_reply=skip_image_qr())
        )

    elif state == "ORG_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"

        card = create_summary_flex(
            "คำสั่งซื้อหน่วยงาน", "#1976d2",
            [
                ("รายละเอียด", data["detail"]),
                ("รูปภาพ", "มี" if is_image else "ไม่มี"),
                ("สถานะ", "รอตรวจสอบสต็อก")
            ],
            "แอดมินจะส่งใบเสนอราคาให้ครับ",
            "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- INQUIRY ----------
def handle_inquiry(event, text, user_id, state, is_image):
    if state == "INQUIRY_PRODUCT":
        user_data[user_id] = {"product": text}
        sessions[user_id] = "INQUIRY_IMAGE"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปสินค้าไหมครับ?", quick_reply=skip_image_qr()))

    elif state == "INQUIRY_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"
        card = create_summary_flex(
            "สอบถามสินค้า", "#9c27b0",
            [("สินค้า", data["product"]), ("รูปภาพ", "มี" if is_image else "ไม่มี"), ("สถานะ", "รอแอดมินตอบ")],
            "กำลังเรียกเจ้าหน้าที่ครับ", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- INSTALL ----------
def handle_install(event, text, user_id, state, is_image):
    if state == "INSTALL_TYPE":
        user_data[user_id] = {"type": text}
        sessions[user_id] = "INSTALL_DETAIL"
        prompt_text = "รบกวนลูกค้ากรอกข้อมูลต่อไปนี้ครับ\nชื่อหน่วยงาน/ชื่อลูกค้า:\nเบอร์โทรติดต่อ:\nความต้องการ/ขนาดพื้นที่ (หากไม่ทราบสเปก พิมพ์ 'ให้ช่างแนะนำ'):"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=prompt_text, quick_reply=cancel_qr()))

    elif state == "INSTALL_DETAIL":
        user_data[user_id]["detail"] = text
        sessions[user_id] = "INSTALL_IMAGE"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปสถานที่หรือหน้างานไหมครับ?", quick_reply=skip_image_qr()))

    elif state == "INSTALL_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"
        card = create_summary_flex(
            "งานติดตั้ง", "#00c853",
            [("ประเภทงาน", data["type"]), ("ข้อมูลลูกค้า", data["detail"]), ("รูปหน้างาน", "มี" if is_image else "ไม่มี"), ("สถานะ", "รอช่างประเมิน/ติดต่อกลับ")],
            "เจ้าหน้าที่จะรีบติดต่อกลับครับ", "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ================= HEALTH CHECK / KEEP ALIVE =================
@app.route("/", methods=["GET"])
def home():
    return "Bot is awake and running!"

# ================= RUN =================
if __name__ == "__main__":
    app.run(port=5000)
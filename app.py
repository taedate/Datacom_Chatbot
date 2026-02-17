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
            TextComponent(
                text=footer_text,
                color='#aaaaaa',
                size='xs',
                align='center',
                margin='md'
            )
        ]
    )

    bubble = BubbleContainer(
        hero=ImageComponent(
            url=image_url,
            size='full',
            aspect_ratio='4:3',
            aspect_mode='cover'
        ) if image_url else None,

        body=BoxComponent(
            layout='vertical',
            paddingAll='lg',
            contents=body_contents
        ),
        footer=footer
    )

    return FlexSendMessage(alt_text=title, contents=bubble)


def create_location_card():
    return FlexSendMessage(
        alt_text="ที่ตั้งร้าน",
        contents=BubbleContainer(
            hero=ImageComponent(
                url="https://github.com/taedate/datacom-image/blob/main/Datacom.jpg?raw=true",
                size='full',
                aspect_ratio='2.35:1',
                aspect_mode='cover',
                action=URIAction(uri="https://www.google.com/maps")
            ),
            body=BoxComponent(
                layout='vertical',
                paddingAll='lg',
                contents=[
                    TextComponent(text="Datacom Service", weight='bold', size='xl'),
                    BoxComponent(
                        layout='vertical',
                        margin='md',
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
                    ButtonComponent(
                        style='primary',
                        action=URIAction(label="โทรติดต่อ", uri="tel:0812345678")
                    ),
                    ButtonComponent(
                        style='secondary',
                        action=URIAction(label="แผนที่นำทาง", uri="https://www.google.com/maps")
                    )
                ]
            )
        )
    )


def skip_image_qr():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ไม่ใส่รูป (ข้าม)", text="ข้าม"))
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
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกเรียบร้อย"))
        return

    if state == "IDLE":
        handle_idle(event, text, user_id)
    elif state.startswith("REPAIR_"):
        handle_repair(event, text, user_id, state, is_image)
    elif state.startswith("ORG_"):
        handle_org(event, text, user_id, state, is_image)
    elif state.startswith("INQUIRY_"):
        handle_inquiry(event, text, user_id, state, is_image)
    elif state == "CCTV_SELECT":
        handle_cctv(event, text, user_id)

# ================= FLOWS =================

def handle_idle(event, text, user_id):
    if text in ["ติดต่อเรา", "แผนที่"]:
        line_bot_api.reply_message(event.reply_token, create_location_card())

    elif text == "แจ้งซ่อม":
        sessions[user_id] = "REPAIR_TYPE"
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
            QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
            QuickReplyButton(action=MessageAction(label="⌨️ อื่นๆ", text="อุปกรณ์อื่น"))
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ต้องการซ่อมอะไรครับ?", quick_reply=qr)
        )

    elif text == "สั่งซื้อหน่วยงาน":
        sessions[user_id] = "ORG_NAME"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🏢 ชื่อหน่วยงานคืออะไรครับ?"))

    elif text == "สอบถามสินค้า":
        sessions[user_id] = "INQUIRY_PRODUCT"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📦 สอบถามสินค้าตัวไหนครับ?"))

    elif text == "ติดตั้งกล้องวงจรปิด":
        sessions[user_id] = "CCTV_SELECT"
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="🏠 Smart Camera", text="Smart Camera")),
            QuickReplyButton(action=MessageAction(label="📹 Analog", text="Analog")),
            QuickReplyButton(action=MessageAction(label="🌐 IP Camera", text="IP Camera"))
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="เลือกประเภทกล้องครับ", quick_reply=qr)
        )

    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="👋 พิมพ์ แจ้งซ่อม / สอบถามสินค้า / สั่งซื้อหน่วยงาน / ติดต่อเรา")
        )

# ---------- REPAIR ----------
def handle_repair(event, text, user_id, state, is_image):
    if state == "REPAIR_TYPE":
        user_data[user_id] = {"type": text}
        sessions[user_id] = "REPAIR_DETAIL"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📝 อาการเสียคืออะไรครับ?"))

    elif state == "REPAIR_DETAIL":
        user_data[user_id]["symptom"] = text
        sessions[user_id] = "REPAIR_IMAGE"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📸 มีรูปไหมครับ?", quick_reply=skip_image_qr())
        )

    elif state == "REPAIR_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"

        card = create_summary_flex(
            "บันทึกแจ้งซ่อม", "#ff9800",
            [
                ("ประเภท", data["type"]),
                ("อาการ", data["symptom"]),
                ("รูปภาพ", "มี" if is_image else "ไม่มี"),
                ("สถานะ", "รอประเมินราคา")
            ],
            "แอดมินจะติดต่อกลับครับ",
            "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- ORG ----------
def handle_org(event, text, user_id, state, is_image):
    if state == "ORG_NAME":
        user_data[user_id] = {"org": text}
        sessions[user_id] = "ORG_ITEM"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🛒 รายการสินค้าที่ต้องการครับ"))

    elif state == "ORG_ITEM":
        user_data[user_id]["item"] = text
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
                ("หน่วยงาน", data["org"]),
                ("รายการ", data["item"]),
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
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📸 มีรูปสินค้าไหมครับ?", quick_reply=skip_image_qr())
        )

    elif state == "INQUIRY_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"

        card = create_summary_flex(
            "สอบถามสินค้า", "#9c27b0",
            [
                ("สินค้า", data["product"]),
                ("รูปภาพ", "มี" if is_image else "ไม่มี"),
                ("สถานะ", "รอแอดมินตอบ")
            ],
            "กำลังเรียกเจ้าหน้าที่ครับ",
            "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- CCTV ----------
def handle_cctv(event, text, user_id):
    sessions[user_id] = "IDLE"
    card = create_summary_flex(
        "สนใจติดตั้ง CCTV", "#00c853",
        [("ประเภท", text), ("สถานะ", "รับเรื่องแล้ว")],
        "เจ้าหน้าที่จะติดต่อกลับครับ",
        "https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
    )
    line_bot_api.reply_message(event.reply_token, card)

# ================= HEALTH CHECK / KEEP ALIVE =================
@app.route("/", methods=["GET"])
def home():
    # หน้าเว็บเปล่าๆ เอาไว้ให้ cron-job.org ยิงมาสะกิดทุกๆ 14 นาที
    return "Bot is awake and running!"

# ================= RUN =================
if __name__ == "__main__":
    app.run(port=5000)

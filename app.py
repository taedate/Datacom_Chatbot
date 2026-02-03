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

# ================== CONFIG ==================
load_dotenv()
app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ใช้ memory ชั่วคราว
sessions = {}
user_data = {}

# ================== FLEX MESSAGE ==================

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
                    TextComponent(
                        text="123 ถนนสุขุมวิท กรุงเทพฯ\n⏰ 09:00 - 18:00 (จ-ส)",
                        wrap=True,
                        margin='md'
                    )
                ]
            ),
            footer=BoxComponent(
                layout='vertical',
                contents=[
                    ButtonComponent(
                        style='primary',
                        action=URIAction(label='โทรติดต่อ', uri='tel:0812345678')
                    )
                ]
            )
        )
    )


def skip_image_qr():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ข้าม", text="ข้าม"))
    ])

# ================== WEBHOOK ==================

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
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อย")
        )
        return

    if state == "IDLE":
        handle_idle(event, text, user_id)
    elif state.startswith("REPAIR_"):
        handle_repair(event, text, user_id, state, is_image)


# ================== FLOWS ==================

def handle_idle(event, text, user_id):
    if text == "แจ้งซ่อม":
        sessions[user_id] = "REPAIR_SELECT"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔧 ซ่อมอุปกรณ์อะไรครับ?")
        )

    elif text in ["ติดต่อเรา", "แผนที่"]:
        line_bot_api.reply_message(event.reply_token, create_location_card())

    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="พิมพ์ 'แจ้งซ่อม' หรือ 'ติดต่อเรา' ได้เลยครับ 😊")
        )


def handle_repair(event, text, user_id, state, is_image):
    if state == "REPAIR_SELECT":
        user_data[user_id] = {"device": text}
        sessions[user_id] = "REPAIR_DETAIL"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📝 อาการเสียเป็นอย่างไรครับ?")
        )

    elif state == "REPAIR_DETAIL":
        user_data[user_id]["symptom"] = text
        sessions[user_id] = "REPAIR_IMAGE"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="📸 มีรูปประกอบไหมครับ?",
                quick_reply=skip_image_qr()
            )
        )

    elif state == "REPAIR_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"

        card = create_summary_flex(
            title="บันทึกแจ้งซ่อม",
            color="#ff9800",
            items=[
                ("อุปกรณ์", data["device"]),
                ("อาการ", data["symptom"]),
                ("รูปภาพ", "มี" if is_image else "ไม่มี"),
                ("สถานะ", "รอประเมินราคา")
            ],
            footer_text="เจ้าหน้าที่จะติดต่อกลับครับ",
            image_url="https://github.com/taedate/datacom-image/blob/main/CardChat.png?raw=true"
        )

        line_bot_api.reply_message(event.reply_token, card)


# ================== RUN ==================

if __name__ == "__main__":
    app.run(port=5000)

import os
import io
from datetime import datetime
import pytz
from dotenv import load_dotenv
from flask import Flask, request, abort, send_file
from PIL import Image

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction, FlexSendMessage,
    BubbleContainer, BoxComponent, TextComponent, SeparatorComponent,
    ImageComponent, ButtonComponent, URIAction, ImagemapSendMessage,
    BaseSize, URIImagemapAction, MessageImagemapAction, ImagemapArea
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
def create_closed_sunday_flex():
    bubble = BubbleContainer(
        hero=ImageComponent(
            url="https://github.com/taedate/DATACOM-ImageV2/blob/main/Weekend.png?raw=true",
            size='full',
            aspect_ratio='16:9', # ปรับสัดส่วนรูปภาพให้เป็นแนวนอน
            aspect_mode='cover'
        ),
        body=BoxComponent(
            layout='vertical',
            paddingAll='xl',
            contents=[
                BoxComponent(
                    layout='vertical', spacing='sm',
                    contents=[
                        TextComponent(text="วันนี้ (วันอาทิตย์) ปิดทำการครับ", wrap=True, weight='bold', size='md', color='#e53935'),
                        TextComponent(text="⏰ เปิดทำการปกติ: จันทร์ - เสาร์ (08:30 - 18:00 น.)", wrap=True, size='sm', color='#666666'),
                        TextComponent(text="คุณลูกค้าสามารถใช้งานเมนู 'ช่วยเหลือ' ด้านล่างได้ปกตินะครับ หรือฝากข้อความไว้ แอดมินจะรีบดูแลให้ในวันพรุ่งนี้ครับ 🙏", wrap=True, size='sm', color='#666666')
                    ]
                )
            ]
        )
    )
    return FlexSendMessage(alt_text="ร้านปิดทำการวันอาทิตย์", contents=bubble)

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
        alt_text="ที่ตั้งร้าน Datacom Service",
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

def skip_image_qr():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="ไม่ใส่รูป (ข้าม)", text="ข้าม")),
        QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
    ])

def cancel_qr():
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
    ])

# ================= IMAGEMAP =================
def create_help_imagemap():
    base_url = "https://datacom-chatbot.onrender.com/imagemap/help" 
    
    return ImagemapSendMessage(
        base_url=base_url,
        alt_text="เมนูช่วยเหลือ",
        base_size=BaseSize(height=520, width=1040),
        actions=[
            URIImagemapAction(
                link_uri='https://maps.app.goo.gl/i6819NkupemvipH9A',
                area=ImagemapArea(x=27, y=30, width=484, height=166)
            ),
            MessageImagemapAction(
                text='เวลาเปิดปิด',
                area=ImagemapArea(x=534, y=31, width=479, height=163)
            ),
            URIImagemapAction(
                link_uri='https://datacom-service.com/',
                area=ImagemapArea(x=26, y=221, width=487, height=170)
            ),
            MessageImagemapAction(
                text='ติดต่อด่วนโทร',
                area=ImagemapArea(x=535, y=221, width=476, height=169)
            ),
            MessageImagemapAction(
                text='คำถามอื่นๆ',
                area=ImagemapArea(x=29, y=412, width=985, height=87)
            )
        ]
    )

# ================= IMAGEMAP ROUTE =================
@app.route("/imagemap/help/<int:size>", methods=["GET"])
def serve_imagemap(size):
    if size not in [1040, 700, 460, 300, 240]:
        abort(404)
        
    original_image_path = os.path.join("static", "help_menu.png")
    
    try:
        img = Image.open(original_image_path)
        
        width_percent = (size / float(img.size[0]))
        new_height = int((float(img.size[1]) * float(width_percent)))
        
        img_resized = img.resize((size, new_height), Image.Resampling.LANCZOS)
        
        img_io = io.BytesIO()
        img_resized.save(img_io, 'PNG', quality=85)
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        print(f"Error processing imagemap: {e}")
        abort(404)

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

    # --- เช็ควันอาทิตย์ ---
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    is_sunday = now.weekday() == 6  # 0=วันจันทร์, 6=วันอาทิตย์

    # กำหนดกลุ่มคำสั่งที่ยอมให้ทำงานได้ในวันอาทิตย์
    allowed_on_sunday = [
        "ช่วยเหลือ", "เวลาเปิดปิด", "ติดต่อด่วนโทร", "คำถามอื่นๆ", "แผนที่", "ติดต่อเรา", "ยกเลิก"
    ]

    # ถ้าเป็นวันอาทิตย์ และไม่ได้กดเมนูที่อนุญาตไว้
    if is_sunday and text not in allowed_on_sunday:
        # เคลียร์สถานะการทำรายการ
        sessions.pop(user_id, None)
        user_data.pop(user_id, None)
        # ส่งการ์ดแจ้งร้านปิด
        line_bot_api.reply_message(event.reply_token, create_closed_sunday_flex())
        return
    # ----------------------------------------

    if text == "ยกเลิก":
        sessions[user_id] = "IDLE"
        user_data.pop(user_id, None)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ ยกเลิกรายการเรียบร้อยแล้วครับ หากต้องการสอบถามเพิ่มเติมเลือกเมนูด้านล่างได้เลยนะครับ"))
        return

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

# ================= FLOWS =================
def handle_idle(event, text, user_id):
    if text in ["ติดต่อเรา", "แผนที่"]:
        line_bot_api.reply_message(event.reply_token, create_location_card())
        
    elif text == "ช่วยเหลือ":
        line_bot_api.reply_message(event.reply_token, create_help_imagemap())

    elif text == "ตรวจสอบสถานะงานซ่อม":
        sessions[user_id] = "CHECK_STATUS"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🔍 สามารถตรวจสอบสถานะได้ง่ายๆ เลยครับ รบกวนพิมพ์ 'เบอร์โทรศัพท์' หรือ 'รหัสงานซ่อม' ส่งมาได้เลยครับ", quick_reply=cancel_qr())
        )

    elif text == "แจ้งซ่อม":
        sessions[user_id] = "REPAIR_TYPE"
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="💻 คอมพิวเตอร์", text="คอมพิวเตอร์")),
            QuickReplyButton(action=MessageAction(label="🖨️ ปริ้นเตอร์", text="ปริ้นเตอร์")),
            QuickReplyButton(action=MessageAction(label="⌨️ อื่นๆ", text="อุปกรณ์อื่น")),
            QuickReplyButton(action=MessageAction(label="❌ ยกเลิก", text="ยกเลิก"))
        ])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🛠️ คุณลูกค้าต้องการแจ้งซ่อมอุปกรณ์ประเภทไหนครับ?", quick_reply=qr))

    elif text == "สั่งซื้อหน่วยงาน":
        sessions[user_id] = "ORG_DETAIL"
        prompt_text = (
            "🏢 สำหรับลูกค้าองค์กร/หน่วยงาน รบกวนแจ้งรายละเอียดเบื้องต้นตามนี้นะครับ\n\n"
            "- ชื่อหน่วยงาน:\n"
            "- รายการสินค้าและจำนวนที่ต้องการ:\n\n"
            "(หลังจากได้รับข้อมูล แอดมินจะรีบตรวจสอบและจัดทำใบเสนอราคาให้ครับ)"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=prompt_text, quick_reply=cancel_qr()))

    elif text == "สอบถามสินค้า":
        sessions[user_id] = "INQUIRY_PRODUCT"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📦 สนใจสอบถามสินค้าตัวไหน หรือกำลังตามหาอุปกรณ์ชิ้นไหนอยู่ แจ้งแอดมินได้เลยครับ", quick_reply=cancel_qr()))

    # --- ดักจับข้อความที่มาจาก Imagemap ---
    elif text == "เวลาเปิดปิด":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⏰ ร้านเปิดให้บริการ จันทร์-เสาร์ เวลา 08:30 - 18:00 น. (หยุดวันอาทิตย์) ยินดีต้อนรับเสมอนะครับ"))
    elif text == "ติดต่อด่วนโทร":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📞 โทรติดต่อด่วน: 098-794-6235, 06-1994-1928\n📞 โทรติดต่อเบอร์ร้าน: 056-223-547"))
    elif text == "คำถามอื่นๆ":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="💬 คุณลูกค้าสามารถพิมพ์คำถามหรือข้อสงสัยทิ้งไว้ได้เลยนะครับ แอดมินจะรีบเข้ามาตอบกลับให้เร็วที่สุดครับ ขอบคุณครับ 🙏"))

    else:
        qr = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="🔧 แจ้งซ่อม", text="แจ้งซ่อม")),
            QuickReplyButton(action=MessageAction(label="🏢 สั่งซื้อหน่วยงาน", text="สั่งซื้อหน่วยงาน")),
            QuickReplyButton(action=MessageAction(label="📦 สอบถามสินค้า", text="สอบถามสินค้า")),
            QuickReplyButton(action=MessageAction(label="ℹ️ ช่วยเหลือ", text="ช่วยเหลือ")),
            QuickReplyButton(action=MessageAction(label="📍 ติดต่อเรา", text="ติดต่อเรา"))
        ])
        greeting_text = "👋 สวัสดีครับ Datacom Service ยินดีให้บริการครับ 😊\nคุณลูกค้าต้องการให้เราดูแลเรื่องไหน สามารถเลือกเมนูด้านล่างได้เลยนะครับ 👇"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=greeting_text, quick_reply=qr)
        )

# ---------- CHECK STATUS ----------
def handle_check_status(event, text, user_id):
    sessions[user_id] = "IDLE"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"กำลังตรวจสอบข้อมูลของ: {text}\n(แอดมินจะรีบแจ้งความคืบหน้าให้ทราบโดยเร็วนะครับ)")
    )

# ---------- REPAIR ----------
def handle_repair(event, text, user_id, state, is_image):
    if state == "REPAIR_TYPE":
        user_data[user_id] = {"type": text}
        sessions[user_id] = "REPAIR_DETAIL"
        prompt_text = (
            "📝 รบกวนแจ้งรายละเอียดตามนี้ เพื่อให้ช่างประเมินได้แม่นยำขึ้นนะครับ\n"
            "- ยี่ห้อ:\n"
            "- รุ่น:\n"
            "- อาการที่พบ:\n"
            "(สามารถพิมพ์รวมกันแล้วส่งมาในข้อความเดียวได้เลยครับ)"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=prompt_text, quick_reply=cancel_qr()))

    elif state == "REPAIR_DETAIL":
        user_data[user_id]["detail"] = text
        sessions[user_id] = "REPAIR_IMAGE"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 หากมีรูปภาพอุปกรณ์หรืออาการเสีย สามารถส่งมาให้ดูได้เลยนะครับ\n(ถ้าไม่มี สามารถกด 'ข้าม' ที่เมนูด้านล่างได้เลยครับ)", quick_reply=skip_image_qr()))

    elif state == "REPAIR_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"
        card = create_summary_flex(
            "บันทึกแจ้งซ่อม", "#ff9800",
            [("อุปกรณ์", data["type"]), ("รายละเอียด", data["detail"]), ("รูปภาพ", "มี" if is_image else "ไม่มี"), ("สถานะ", "รอประเมินราคา")],
            "รับเรื่องเรียบร้อย แอดมินจะติดต่อกลับครับ", "https://raw.githubusercontent.com/taedate/DATACOM-ImageV2/main/PleaseWaitadminreply.png"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- ORG ----------
def handle_org(event, text, user_id, state, is_image):
    if state == "ORG_DETAIL":
        user_data[user_id] = {"detail": text}
        sessions[user_id] = "ORG_IMAGE"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📸 หากมีรูปภาพตัวอย่างสินค้า สามารถส่งมาได้เลยนะครับ\n(ถ้าไม่มี สามารถกด 'ข้าม' ที่เมนูด้านล่างได้เลยครับ)", quick_reply=skip_image_qr())
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
            "รับเรื่องเรียบร้อย แอดมินจะจัดส่งใบเสนอราคาให้ครับ",
            "https://raw.githubusercontent.com/taedate/DATACOM-ImageV2/main/PleaseWaitadminreply.png"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ---------- INQUIRY ----------
def handle_inquiry(event, text, user_id, state, is_image):
    if state == "INQUIRY_PRODUCT":
        user_data[user_id] = {"product": text}
        sessions[user_id] = "INQUIRY_IMAGE"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📸 มีรูปภาพสินค้าตัวอย่างไหมครับ?\n(ถ้าไม่มี สามารถกด 'ข้าม' ที่เมนูด้านล่างได้เลยครับ)", quick_reply=skip_image_qr()))

    elif state == "INQUIRY_IMAGE":
        data = user_data.pop(user_id)
        sessions[user_id] = "IDLE"
        card = create_summary_flex(
            "สอบถามสินค้า", "#9c27b0",
            [("สินค้า", data["product"]), ("รูปภาพ", "มี" if is_image else "ไม่มี"), ("สถานะ", "รอแอดมินตอบ")],
            "ระบบได้รับข้อความแล้ว กำลังเรียกแอดมินครับ", "https://raw.githubusercontent.com/taedate/DATACOM-ImageV2/main/PleaseWaitadminreply.png"
        )
        line_bot_api.reply_message(event.reply_token, card)

# ================= HEALTH CHECK / KEEP ALIVE =================
@app.route("/", methods=["GET"])
def home():
    return "Bot is awake and running!"

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
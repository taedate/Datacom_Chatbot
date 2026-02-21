import requests
import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
IMAGE_PATH = "/Users/nakorn/Documents/GitHub/Datacom_Chatbot/assets/Repair_Da.png"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

rich_menu_payload = {
  "size": {
    "width": 2500,
    "height": 1686
  },
  "selected": True,
  "name": "Rich Menu 1",
  "chatBarText": "Bulletin",
  "areas": [
    {
      "bounds": {
        "x": 0,
        "y": 0,
        "width": 1667,
        "height": 916
      },
      "action": {
        "type": "message",
        "text": "แจ้งซ่อม"
      }
    },
    {
      "bounds": {
        "x": 1675,
        "y": 0,
        "width": 825,
        "height": 916
      },
      "action": {
        "type": "uri",
        "uri": "https://datacom-service.com/track"
      }
    },
    {
      "bounds": {
        "x": 0,
        "y": 932,
        "width": 821,
        "height": 754
      },
      "action": {
        "type": "message",
        "text": "สั่งซื้อหน่วยงาน"
      }
    },
    {
      "bounds": {
        "x": 837,
        "y": 932,
        "width": 830,
        "height": 754
      },
      "action": {
        "type": "message",
        "text": "สอบถามสินค้า"
      }
    },
    {
      "bounds": {
        "x": 1679,
        "y": 932,
        "width": 821,
        "height": 754
      },
      "action": {
        "type": "message",
        "text": "งานติดตั้ง"
      }
    }
  ]
}

def setup_rich_menu():
    print("1. Creating Rich Menu...")
    res = requests.post("https://api.line.me/v2/bot/richmenu", headers=HEADERS, json=rich_menu_payload)
    if res.status_code != 200:
        print("Error creating menu:", res.text)
        return
    
    rich_menu_id = res.json().get("richMenuId")
    print(f"-> Success! ID: {rich_menu_id}")

    print("2. Uploading Image...")
    with open(IMAGE_PATH, "rb") as f:
        headers_img = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "image/png"}
        # --- เปลี่ยน URL เป็น api-data ---
        res_img = requests.post(f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content", headers=headers_img, data=f)
        print(f"-> Upload Status: {res_img.status_code}")
        if res_img.status_code != 200:
            print("Upload Error:", res_img.text)

    print("3. Setting as Default Rich Menu...")
    res_default = requests.post(f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}", headers=HEADERS)
    print(f"-> Set Default Status: {res_default.status_code}")
    if res_default.status_code != 200:
        print("Set Default Error:", res_default.text)
        
    print("🎉 เสร็จเรียบร้อย! ลองเปิดแอป LINE ดูได้เลยครับ")

if __name__ == "__main__":
    setup_rich_menu()
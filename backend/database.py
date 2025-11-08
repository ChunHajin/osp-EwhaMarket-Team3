# backend/database.py
import json
import pyrebase

class DBhandler:
    def __init__(self):
        # Load Firebase configuration
        with open("./authentication/firebase_auth.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        # Initialize Firebase
        firebase = pyrebase.initialize_app(config)
        self.db = firebase.database()

    def insert_item(self, name, data, img_path):
        # Match your product-create.html fields exactly
        item_info = {
            "title": data.get("title"),
            "price": data.get("price"),
            "region": data.get("region"),
            "status": data.get("status"),
            "desc": data.get("desc"),
            "author": "ewhaosp",
            "img_path": img_path
        }

        # Save under item/<title>
        self.db.child("item").child(name).set(item_info)
        print("✅ Firebase Save Success:", item_info)
        return True

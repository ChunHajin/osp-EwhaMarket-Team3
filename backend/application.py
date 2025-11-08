# backend/application.py
from flask import Flask, request
from database import DBhandler
import os

application = Flask(__name__)
DB = DBhandler()

@application.route("/")
def index():
    return "✅ EwhaMarket backend is running."

@application.route("/submit_item_post", methods=["POST"])
def submit_item_post():
    try:
        # Handle uploaded file (optional)
        image_file = request.files.get("photos")
        img_path = ""
        if image_file and image_file.filename:
            save_dir = os.path.join(os.getcwd(), "backend", "static", "images")
            os.makedirs(save_dir, exist_ok=True)
            img_path = f"static/images/{image_file.filename}"
            image_file.save(os.path.join(save_dir, image_file.filename))

        # Collect form fields
        data = request.form
        key_name = data.get("title", "unnamed_item")

        # Save to Firebase
        DB.insert_item(key_name, data, img_path)

        return f"""
        <html><body style='font-family:sans-serif; text-align:center;'>
        <h2>상품이 Firebase에 등록되었습니다 ✅</h2>
        <p><b>상품명:</b> {key_name}</p>
        <p><a href='/'>돌아가기</a></p>
        </body></html>
        """

    except Exception as e:
        return f"<h3>❌ 오류 발생: {e}</h3>", 500


if __name__ == "__main__":
    application.run(debug=True)

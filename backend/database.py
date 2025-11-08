import pyrebase
import json
import hashlib
import os

class DBhandler:
    def __init__(self):
        # app.py가 backend 폴더에 있다고 가정하고 경로 설정
        with open('./backend/authentication/firebase_auth.json') as f:
            config = json.load(f)
        
        firebase = pyrebase.initialize_app(config)
        self.db = firebase.database()

    def user_duplicate_check(self, id_string):
        """
        사용자 ID 중복 체크
        :param id_string: 체크할 사용자 ID
        :return: (bool) 중복이면 False, 사용 가능하면 True
        """
        users = self.db.child("user").get()
        
        # users.val()가 None (즉, 등록된 유저가 아무도 없음)이면 True 반환
        if not users.val():
            return True
        
        # users.each()를 순회하며 ID 비교
        for user in users.each():
            if user.val().get('id') == id_string:
                return False  # 중복된 ID 찾음
        
        return True  # 중복된 ID 없음

    def insert_user(self, data, pw_hash):
        """
        신규 사용자 정보 DB에 삽입
        :param data: (dict) 사용자 정보 (id, email, phone 등)
        :param pw_hash: (str) 해시된 비밀번호
        :return: (bool) 성공 여부
        """
        user_info = {
            "id": data.get('id'),
            "pw": pw_hash,
            "email": data.get('email'),
            "phone": data.get('phone', '') # 선택 항목
        }
        
        # insert_user 호출 전 ID 중복 체크 (필수)
        if self.user_duplicate_check(data.get('id')):
            self.db.child("user").push(user_info)
            print(f"User {data.get('id')} inserted.")
            return True
        else:
            print(f"Error: User ID {data.get('id')} already exists.")
            return False
        
    # 상품 정보 삽입 함수
    def insert_item(self, name, data, img_path):
        item_info = {
            "title": data.get("title"),
            "price": data.get("price"),
            "region": data.get("region"),
            "status": data.get("status"),
            "desc": data.get("desc"),
            "author": "ewhaosp", # 임시 작성자
            "img_path": img_path
        }
        # item 노드에 상품 정보 저장
        self.db.child("item").child(name).set(item_info)
        print("✅ Firebase Save Success:", item_info)
        return True
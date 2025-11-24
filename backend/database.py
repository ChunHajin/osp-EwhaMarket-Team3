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
            "phone": data.get('phone', ''), # 선택 항목
            "profile_img_path": ""
        }
        
        # insert_user 호출 전 ID 중복 체크 (필수)
        if self.user_duplicate_check(data.get('id')):
            self.db.child("user").push(user_info)
            print(f"User {data.get('id')} inserted.")
            return True
        else:
            print(f"Error: User ID {data.get('id')} already exists.")
            return False
        
    def find_user(self, id_, pw_hash):
        users = self.db.child("user").get()
        if not users.val():
            return False
        for user in users.each():
            value = user.val()
            if value.get('id') == id_ and value.get('pw') == pw_hash:
                return True
        return False
    
    def get_user_info(self, user_id):
        """
        사용자 ID로 사용자 정보를 조회합니다.
        :param user_id: (str) 사용자 ID
        :return: (dict) 사용자 정보 또는 None
        """
        users = self.db.child("user").get()
        if not users.val():
            return None
        for user in users.each():
            if user.val().get('id') == user_id:
                return user.val()
        return None

    def update_user_profile_img(self, user_id, img_path):
        """
        사용자의 프로필 이미지 경로 업데이트
        :param user_id: (str) 사용자 ID
        :param img_path: (str) 이미지 경로
        :return: (bool) 업데이트 성공 여부
        """
        users = self.db.child("user").get()
        target_key = None

        # 해당 user_id를 가진 노드 키(key) 찾기
        for user in users.each():
            if user.val().get('id') == user_id:
                target_key = user.key()
                break

        if target_key:
            self.db.child("user").child(target_key).update({"profile_img": img_path})
            return True
        return False
        
    # 상품 정보 가져오는 함수
    def get_items(self):
        """
        Firebase의 'item' 노드 아래 모든 상품 데이터를 가져옵니다.
        """
        items = self.db.child("item").get().val()
        return items

    # 특정 상품 정보 가져오는 함수
    def get_item_byname(self, name):
        """
        상품 이름(key)을 이용해 'item' 노드에서 특정 상품 데이터를 찾습니다.
        """
        items = self.db.child("item").get()
        
        if not items.val():
            return None
            
        for res in items.each():
            key_value = res.key()
            if key_value == name:
                return res.val()
        
        return None

    # 상품 정보 삽입 함수
    def insert_item(self, name, data, img_path, author_id, trade_method):
        item_info = {
            "title": data.get("title"),
            "price": data.get("price"),
            "region": data.get("region"),
            "status": data.get("status"),
            "desc": data.get("desc"),
            "author": author_id,
            "img_path": img_path,
            "category": data.get("category"),
            "trade_method": data.get("trade_method")
        }
        self.db.child("item").child(name).set(item_info)
        print("✅ Firebase Save Success:", item_info)
        return True

    def purchase_item(self, name, buyer_id):
        """
        상품 구매 처리: 구매자 ID 등록 및 상태를 '거래 완료'로 변경
        """
        update_data = {
            "buyer": buyer_id,
            "status": "거래 완료"
        }
        try:
            self.db.child("item").child(name).update(update_data)
            return True
        except Exception as e:
            print(f"Purchase Error: {e}")
            return False
        
    # 리뷰 등록 함수
    def reg_review(self, item_name, data, img_path, writer_id, created_at):
        review_key = f"{item_name}_{writer_id}"

        review_info ={
            "title": data.get('reviewTitle'),
            "rate": data.get('rating'),
            "content": data.get('reviewContent'),
            "img_path": img_path,
            "item_name": item_name,
            "writer_id": writer_id,
            "created_at": created_at
        }

        self.db.child("review").child(review_key).set(review_info)
        return review_key
    
    # 전체 리뷰 조회 함수
    def get_reviews(self):
        reviews = self.db.child("review").get().val()
        return reviews
    
    # 특정 리뷰 상세 조회 함수
    def get_review_by_key(self, review_key):
        """
        리뷰 키(review_key)로 직접 조회. review_key는 reg_review에서 생성한 키와 동일한 형식.
        """
        review_data = self.db.child("review").child(review_key).get().val()
        return review_data
    
     # -------------------- 좋아요 기능 추가 --------------------

    def get_like_status(self, item_name, user_id):
        """
        특정 사용자가 해당 상품에 좋아요를 눌렀는지 확인
        likes / item_name / user_id = True 형태
        """
        try:
            res = self.db.child("likes").child(item_name).child(user_id).get()
            return bool(res.val())
        except Exception as e:
            print(f"get_like_status Error: {e}")
            return False

    def set_like_status(self, item_name, user_id, liked):
        """
        liked=True  → set(True)
        liked=False → remove()
        """
        try:
            if liked:
                self.db.child("likes").child(item_name).child(user_id).set(True)
            else:
                self.db.child("likes").child(item_name).child(user_id).remove()
            return True
        except Exception as e:
            print(f"set_like_status Error: {e}")
            return False

    def toggle_like(self, item_name, user_id):
        """
        현재 좋아요 상태를 읽고 반대로 변경한 뒤 반환
        """
        current = self.get_like_status(item_name, user_id)
        new_status = not current
        success = self.set_like_status(item_name, user_id, new_status)
        return success, new_status

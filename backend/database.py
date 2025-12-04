import pyrebase
import json
import hashlib
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DBhandler:
    """Firebase Realtime Database handler.

    Environment:
      FIREBASE_CONFIG: 파일 경로 (기본: ./backend/authentication/firebase_auth.json)
    """

    # ==========================================================
    # 1. DB 초기화 및 설정 (Initialization & Setup)
    # ==========================================================

    def __init__(self, config_path: Optional[str] = None):
        # config_path 우선, 없으면 환경변수, 기본 경로 순
        cfg_path = config_path or os.getenv("FIREBASE_CONFIG") or os.path.join("./backend", "authentication", "firebase_auth.json")
        self.db = None
        try:
            if not os.path.exists(cfg_path):
                logger.error("Firebase config not found at %s", cfg_path)
                return

            with open(cfg_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            firebase = pyrebase.initialize_app(config)
            self.db = firebase.database()
            logger.info("Initialized Firebase DB handler using %s", cfg_path)
        except Exception:
            logger.exception("Failed to initialize Firebase DB handler from %s", cfg_path)

    # ==========================================================
    # 2. 사용자 인증 및 계정 관리 (User Auth & Management)
    # ==========================================================

    def user_duplicate_check(self, id_string):
        """
        사용자 ID 중복 체크
        :param id_string: 체크할 사용자 ID
        :return: (bool) 중복이면 False, 사용 가능하면 True
        """
        if not self.db:
            logger.error("user_duplicate_check called but DB is not initialized")
            return True

        users = self.db.child("user").get()

        # users.val()가 None (즉, 등록된 유저가 아무도 없음)이면 True 반환
        if not users or not users.val():
            return True

        # users.each()를 순회하며 ID 비교
        try:
            for user in users.each() or []:
                if (user.val() or {}).get('id') == id_string:
                    return False  # 중복된 ID 찾음
        except Exception:
            logger.exception("Error iterating users for duplicate check")

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
            "phone": data.get('phone', ''),  # 선택 항목
            # 앱에서 기대하는 키는 `profile_img` 이므로 일관성 유지
            "profile_img": ""
        }
        
        # insert_user 호출 전 ID 중복 체크 (필수)
        if not self.db:
            logger.error("insert_user called but DB is not initialized")
            return False

        try:
            if self.user_duplicate_check(data.get('id')):
                self.db.child("user").push(user_info)
                logger.info("User %s inserted.", data.get('id'))
                return True
            else:
                logger.warning("User ID %s already exists.", data.get('id'))
                return False
        except Exception:
            logger.exception("insert_user failed for %s", data.get('id'))
            return False
        
    def find_user(self, id_, pw_hash):
        """
        아이디와 해시된 비밀번호로 사용자 존재 여부 확인 (로그인용)
        """
        if not self.db:
            logger.error("find_user called but DB is not initialized")
            return False

        users = self.db.child("user").get()
        if not users or not users.val():
            return False
        try:
            for user in users.each() or []:
                value = user.val() or {}
                if value.get('id') == id_ and value.get('pw') == pw_hash:
                    return True
        except Exception:
            logger.exception("find_user iteration failed")
        return False
    
    def get_user_info(self, user_id):
        """
        사용자 ID로 사용자 정보를 조회
        :param user_id: (str) 사용자 ID
        :return: (dict) 사용자 정보 또는 None
        """
        if not self.db:
            logger.error("get_user_info called but DB is not initialized")
            return None

        users = self.db.child("user").get()
        if not users or not users.val():
            return None
        try:
            for user in users.each() or []:
                val = user.val() or {}
                if val.get('id') == user_id:
                    return val
        except Exception:
            logger.exception("get_user_info iteration failed")
        return None

    def update_user_profile_img(self, user_id, img_path):
        """
        사용자의 프로필 이미지 경로 업데이트
        :param user_id: (str) 사용자 ID
        :param img_path: (str) 이미지 경로
        :return: (bool) 업데이트 성공 여부
        """
        if not self.db:
            logger.error("update_user_profile_img called but DB is not initialized")
            return False

        users = self.db.child("user").get()
        target_key = None

        # 해당 user_id를 가진 노드 키(key) 찾기
        try:
            for user in users.each() or []:
                if (user.val() or {}).get('id') == user_id:
                    target_key = user.key()
                    break
        except Exception:
            logger.exception("update_user_profile_img: failed to iterate users")

        if target_key:
            try:
                self.db.child("user").child(target_key).update({"profile_img": img_path})
                return True
            except Exception:
                logger.exception("Failed to update profile image for %s", user_id)
                return False
        return False
    
    def update_user_info(self, user_id, pw_hash, email, phone):
        """
        사용자 정보 수정 (비밀번호, 이메일, 전화번호)
        """
        if not self.db:
            logger.error("update_user_info called but DB is not initialized")
            return False

        users = self.db.child("user").get()
        target_key = None

        # 해당 user_id를 가진 노드 키(key) 찾기
        try:
            for user in users.each() or []:
                if (user.val() or {}).get('id') == user_id:
                    target_key = user.key()
                    break
        except Exception:
            logger.exception("update_user_info: failed to iterate users")

        if target_key:
            update_data = {
                "pw": pw_hash,
                "email": email,
                "phone": phone
            }
            try:
                # Firebase Realtime DB 업데이트
                self.db.child("user").child(target_key).update(update_data)
                return True
            except Exception:
                logger.exception("Failed to update user info for %s", user_id)
                return False
        return False
        
    # ==========================================================
    # 3. 상품 정보 관리 (Item Management)
    # ==========================================================

    def get_items(self):
        """
        Firebase의 'item' 노드 아래 모든 상품 데이터를 가져옵니다.
        """
        if not self.db:
            logger.error("get_items called but DB is not initialized")
            return None
        try:
            items = self.db.child("item").get().val()
            return items
        except Exception:
            logger.exception("get_items failed")
            return None

    def get_item_byname(self, name):
        """
        상품 이름(key)을 이용해 'item' 노드에서 특정 상품 데이터를 찾습니다.
        """
        if not self.db:
            logger.error("get_item_byname called but DB is not initialized")
            return None
        items = self.db.child("item").get()

        if not items or not items.val():
            return None

        try:
            for res in items.each() or []:
                key_value = res.key()
                if key_value == name:
                    return res.val()
        except Exception:
            logger.exception("get_item_byname iteration failed for %s", name)
        return None

    def insert_item(self, name, data, img_path, author_id, trade_method, created_at):
        """
        신규 상품 정보를 DB의 'item' 노드에 삽입
        """
        item_info = {
            "title": data.get("title"),
            "price": data.get("price"),
            "region": data.get("region"),
            "status": data.get("status"),
            "desc": data.get("desc"),
            "author": author_id,
            "img_path": img_path,
            "category": data.get("category"),
            "trade_method": data.get("trade_method"),
            "created_at": created_at
        }
        if not self.db:
            logger.error("insert_item called but DB is not initialized")
            return False
        try:
            self.db.child("item").child(name).set(item_info)
            logger.info("Firebase Save Success: %s", item_info)
            return True
        except Exception:
            logger.exception("insert_item failed for %s", name)
            return False

    def purchase_item(self, name, buyer_id):
        """
        상품 구매 처리: 구매자 ID 등록 및 상태를 '거래 완료'로 변경
        """        
        if not self.db:
            logger.error("purchase_item called but DB is not initialized")
            return False, "DB 초기화 실패"
        try:
            current = self.db.child("item").child(name).get().val()
            if not current:
                return False, "상품을 찾을 수 없습니다."

            # 이미 거래 완료 상태라면 구매 불가 안내
            if str(current.get('status', '')).strip() == '거래 완료' or current.get('buyer'):
                return False, "이미 거래 완료된 상품입니다."

            update_data = {
                "buyer": buyer_id,
                "status": "거래 완료"
            }
            self.db.child("item").child(name).update(update_data)
            return True, "구매가 완료되었습니다."
        except Exception:
            logger.exception("purchase_item failed for %s", name)
            return False, "구매 처리에 실패했습니다."
        
    def update_item(self, original_key, new_data, img_path, author_id, new_key=None):
        """
        기존 상품 정보 업데이트
        """
        existing_data = None
        if self.db:
            try:
                existing_data = self.db.child("item").child(original_key).get().val()
            except Exception:
                logger.exception("update_item: failed to read existing item %s", original_key)

        final_img_path = img_path if img_path else (existing_data.get("img_path", "") if existing_data else "")
        existing_created_at = existing_data.get("created_at") if existing_data and existing_data.get("created_at") else datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        item_info = {
            "title": new_data.get("title"),
            "price": new_data.get("price"),
            "region": new_data.get("region"),
            "status": new_data.get("status"),
            "desc": new_data.get("desc"),
            "author": author_id,
            "img_path": final_img_path,
            "category": new_data.get("category"),
            "trade_method": new_data.get("trade_method"),
            "created_at": existing_created_at
        }
        
        if not self.db:
            logger.error("update_item called but DB is not initialized")
            return False

        try:
            if new_key and new_key != original_key:
                # 키 변경 시: 기존 노드 삭제 후 새 노드 생성
                self.db.child("item").child(original_key).remove()
                self.db.child("item").child(new_key).set(item_info)
                logger.info("Firebase Item Updated (Key Change: %s -> %s)", original_key, new_key)
            else:
                # 키 유지 시: 기존 노드 덮어쓰기
                self.db.child("item").child(original_key).set(item_info)
                logger.info("Firebase Item Updated (Key Maintained: %s)", original_key)
            return True
        except Exception:
            logger.exception("update_item failed for %s", original_key)
            return False
    
    def delete_item(self, item_name):
        """
        특정 상품 정보를 DB에서 삭제하고 연관된 좋아요 정보도 삭제
        """
        if not self.db:
            logger.error("delete_item called but DB is not initialized")
            return False
        try:
            self.db.child("item").child(item_name).remove()
            self.db.child("likes").child(item_name).remove()  # 연관된 좋아요 정보도 삭제
            logger.info("Firebase Item %s deleted.", item_name)
            return True
        except Exception:
            logger.exception("Delete Item Error for %s", item_name)
            return False
        
    # ==========================================================
    # 4. 리뷰 관리 (Review Management)
    # ==========================================================

    def reg_review(self, item_name, data, img_path, writer_id, created_at):
        """
        리뷰 정보를 DB의 'review' 노드에 등록
        """
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

        if not self.db:
            logger.error("reg_review called but DB is not initialized")
            return ""
        try:
            self.db.child("review").child(review_key).set(review_info)
            return review_key
        except Exception:
            logger.exception("reg_review failed for %s", review_key)
            return ""
    
    def get_reviews(self):
        """
        DB의 'review' 노드 아래 모든 리뷰 데이터를 가져옵니다.
        """
        if not self.db:
            logger.error("get_reviews called but DB is not initialized")
            return None
        try:
            reviews = self.db.child("review").get().val()
            return reviews
        except Exception:
            logger.exception("get_reviews failed")
            return None
    
    def get_review_by_key(self, review_key):
        """
        리뷰 키(review_key)로 직접 조회.
        """
        if not self.db:
            logger.error("get_review_by_key called but DB is not initialized")
            return None
        try:
            review_data = self.db.child("review").child(review_key).get().val()
            return review_data
        except Exception:
            logger.exception("get_review_by_key failed for %s", review_key)
            return None
    
    def check_review_exists(self, item_name, user_id):
        """
        특정 상품에 대한 사용자의 리뷰가 존재하는지 확인
        :param item_name: (str) 상품 이름
        :param user_id: (str) 사용자 ID
        :return: (bool) 리뷰 존재 여부
        """
        if not self.db:
            logger.error("check_review_exists called but DB is not initialized")
            return False
        review_key = f"{item_name}_{user_id}"
        try:
            review_data = self.db.child("review").child(review_key).get().val()
            return review_data is not None
        except Exception:
            logger.exception("check_review_exists failed for %s", review_key)
            return False
    
    # ==========================================================
    # 5. 좋아요 관리 (Like/Wishlist Management)
    # ==========================================================

    def get_like_status(self, item_name, user_id):
        """
        특정 사용자가 해당 상품에 좋아요를 눌렀는지 확인
        """
        if not self.db:
            logger.error("get_like_status called but DB is not initialized")
            return False
        try:
            res = self.db.child("likes").child(item_name).child(user_id).get()
            return bool(res.val())
        except Exception:
            logger.exception("get_like_status Error for %s / %s", item_name, user_id)
            return False

    def get_like_count(self, item_name):
        """
        특정 상품의 좋아요 개수를 반환합니다.
        """
        if not self.db:
            logger.error("get_like_count called but DB is not initialized")
            return 0
        try:
            res = self.db.child("likes").child(item_name).get()
            if not res or not res.val():
                return 0
            if isinstance(res.val(), dict):
                return len(res.val())
            return 0
        except Exception:
            logger.exception("get_like_count Error for %s", item_name)
            return 0

    def set_like_status(self, item_name, user_id, liked):
        """
        좋아요 상태를 설정하거나 제거합니다.
        """
        if not self.db:
            logger.error("set_like_status called but DB is not initialized")
            return False
        try:
            if liked:
                self.db.child("likes").child(item_name).child(user_id).set(True)
            else:
                self.db.child("likes").child(item_name).child(user_id).remove()
            return True
        except Exception:
            logger.exception("set_like_status Error for %s / %s", item_name, user_id)
            return False

    def toggle_like(self, item_name, user_id):
        """
        현재 좋아요 상태를 읽고 반대로 변경한 뒤 반환
        """
        current = self.get_like_status(item_name, user_id)
        new_status = not current
        success = self.set_like_status(item_name, user_id, new_status)
        return success, new_status

    def get_liked_items_by_user(self, user_id):
        """
        이 사용자가 좋아요를 누른 상품 이름 목록을 반환.
        """
        liked_items = []
        if not self.db:
             logger.error("get_liked_items_by_user called but DB is not initialized")
             return liked_items
             
        try:
            snapshot = self.db.child("likes").get()
            if not snapshot or not snapshot.val():
                return []

            for item_node in snapshot.each() or []:
                item_name = item_node.key()
                item_likes = item_node.val()
                if isinstance(item_likes, dict) and user_id in item_likes:
                    liked_items.append(item_name)
        except Exception:
            logger.exception("get_liked_items_by_user Error for %s", user_id)
        return liked_items
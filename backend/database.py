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
        # 구현: Firebase 설정 파일 경로 결정 (인수 > 환경변수 > 기본경로)
        cfg_path = config_path or os.getenv("FIREBASE_CONFIG") or os.path.join("./backend", "authentication", "firebase_auth.json")
        self.db = None
        
        # 구현: 설정 파일을 읽어 pyrebase 초기화 후 DB 레퍼런스 설정
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("user_duplicate_check called but DB is not initialized")
            return True

        # 구현: 사용자 노드 스냅샷을 가져와 id 중복 여부 검사 (전체 스캔)
        users = self.db.child("user").get()

        if not users or not users.val():
            return True

        try:
            for user in users.each() or []:
                if (user.val() or {}).get('id') == id_string:
                    return False 
        except Exception:
            logger.exception("Error iterating users for duplicate check")

        return True

    def insert_user(self, data, pw_hash):
        """
        신규 사용자 정보 DB에 삽입
        :param data: (dict) 사용자 정보 (id, email, phone 등)
        :param pw_hash: (str) 해시된 비밀번호
        :return: (bool) 성공 여부
        """
        # 구현: 사용자 정보 dict 구성 (id, pw, email, phone, profile_img)
        user_info = {
            "id": data.get('id'),
            "pw": pw_hash,
            "email": data.get('email'),
            "phone": data.get('phone', ''),
            "profile_img": ""
        }
        
        # 구현: DB 연결 확인 및 중복 여부 확인 후 push로 사용자 노드에 저장
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("find_user called but DB is not initialized")
            return False

        # 구현: 모든 사용자 스냅샷을 순회하여 id/pw 해시 일치 여부 검사
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_user_info called but DB is not initialized")
            return None

        # 구현: 사용자 스냅샷을 순회하여 user_id에 해당하는 레코드 반환
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("update_user_profile_img called but DB is not initialized")
            return False

        users = self.db.child("user").get()
        target_key = None

        # 구현: 사용자 스냅샷을 순회하여 해당 user_id의 노드 키를 찾음
        try:
            for user in users.each() or []:
                if (user.val() or {}).get('id') == user_id:
                    target_key = user.key()
                    break
        except Exception:
            logger.exception("update_user_profile_img: failed to iterate users")

        # 구현: 발견 시 profile_img 필드를 update
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("update_user_info called but DB is not initialized")
            return False

        users = self.db.child("user").get()
        target_key = None

        # 구현: 사용자 스냅샷을 순회하여 노드 키를 찾아 pw/email/phone을 업데이트
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_items called but DB is not initialized")
            return None
        # 구현: 'item' 노드의 전체 스냅샷을 반환
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_item_byname called but DB is not initialized")
            return None
        items = self.db.child("item").get()

        if not items or not items.val():
            return None

        # 구현: item 스냅샷을 순회하며 키 비교로 대상 아이템 반환
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
        # 구현: 전달받은 필드로 item_info 구성
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
        # 구현: item/<name>에 set하여 저장 (기존 키 덮어쓰기)
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
        # 구현: DB 연결 확인 및 상품 존재 여부 확인
        if not self.db:
            logger.error("purchase_item called but DB is not initialized")
            return False, "DB 초기화 실패"
        try:
            current = self.db.child("item").child(name).get().val()
            if not current:
                return False, "상품을 찾을 수 없습니다."

            # 구현: 중복 구매(이미 거래 완료 또는 buyer 존재) 여부 검사
            if str(current.get('status', '')).strip() == '거래 완료' or current.get('buyer'):
                return False, "이미 거래 완료된 상품입니다."

            # 구현: 구매자 ID와 상태 업데이트
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
        # 구현: 기존 데이터 로드 (원본 키에서 읽기)
        existing_data = None
        if self.db:
            try:
                existing_data = self.db.child("item").child(original_key).get().val()
            except Exception:
                logger.exception("update_item: failed to read existing item %s", original_key)

        # 구현: 전달된 필드와 이미지 경로 병합하여 item_info 구성
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
        
        # 구현: 키 변경 시 remove 후 set, 아니면 set으로 덮어쓰기
        if not self.db:
            logger.error("update_item called but DB is not initialized")
            return False

        try:
            if new_key and new_key != original_key:
                self.db.child("item").child(original_key).remove()
                self.db.child("item").child(new_key).set(item_info)
                logger.info("Firebase Item Updated (Key Change: %s -> %s)", original_key, new_key)
            else:
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("delete_item called but DB is not initialized")
            return False
        # 구현: item/<item_name> 및 likes/<item_name> 노드 제거
        try:
            self.db.child("item").child(item_name).remove()
            self.db.child("likes").child(item_name).remove()
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
        # 구현: review_key 생성 (item_name_writer_id)
        review_key = f"{item_name}_{writer_id}"

        # 구현: 리뷰 정보 dict 구성 및 review/<review_key>에 set
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_reviews called but DB is not initialized")
            return None
        # 구현: 'review' 노드 전체 스냅샷 반환
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_review_by_key called but DB is not initialized")
            return None
        # 구현: review/<review_key>로 직접 조회하여 반환
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
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("check_review_exists called but DB is not initialized")
            return False
        # 구현: review_key로 직접 조회하여 존재 여부 판단
        review_key = f"{item_name}_{user_id}"
        try:
            review_data = self.db.child("review").child(review_key).get().val()
            return review_data is not None
        except Exception:
            logger.exception("check_review_exists failed for %s", review_key)
            return False
    
    # ==========================================================
    # 5. 찜 관리 (Wishlist Management)
    # ==========================================================

    def get_like_status(self, item_name, user_id):
        """
        특정 사용자가 해당 상품에 찜을 눌렀는지 확인
        """
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_like_status called but DB is not initialized")
            return False
        # 구현: likes/<item_name>/<user_id> 노드 조회하여 상태 반환
        try:
            res = self.db.child("likes").child(item_name).child(user_id).get()
            return bool(res.val())
        except Exception:
            logger.exception("get_like_status Error for %s / %s", item_name, user_id)
            return False

    def get_like_count(self, item_name):
        """
        특정 상품의 찜 개수를 반환합니다.
        """
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("get_like_count called but DB is not initialized")
            return 0
        # 구현: likes/<item_name>의 child dict 길이로 좋아요 수 계산
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
        찜 상태를 설정하거나 제거합니다.
        """
        # 구현: DB 연결 확인
        if not self.db:
            logger.error("set_like_status called but DB is not initialized")
            return False
        # 구현: liked=True면 set, False면 remove 수행
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
        현재 찜 상태를 읽고 반대로 변경한 뒤 반환
        """
        # 구현: 현재 상태를 읽고 반전한 뒤 set_like_status 호출
        current = self.get_like_status(item_name, user_id)
        new_status = not current
        success = self.set_like_status(item_name, user_id, new_status)
        return success, new_status

    def get_liked_items_by_user(self, user_id):
        """
        이 사용자가 찜을 누른 상품 이름 목록을 반환.
        """
        liked_items = []
        # 구현: 전체 likes 스냅샷을 가져와서
        if not self.db:
             logger.error("get_liked_items_by_user called but DB is not initialized")
             return liked_items
             
        # 구현: 각 아이템의 likes 자식에 user_id가 있는지 검사하여 리스트 반환
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
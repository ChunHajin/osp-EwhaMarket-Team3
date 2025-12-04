from flask import Flask, request, redirect, session, jsonify, render_template, url_for, make_response
from database import DBhandler
from datetime import datetime, timedelta
from markupsafe import Markup
from werkzeug.utils import secure_filename
import hashlib
import json
import os
import logging
from typing import Optional, Dict, Any

# Flask 애플리케이션 초기화
app = Flask(__name__,
            static_folder="../frontend",
            template_folder="../frontend",
            static_url_path=""
           )

# ==============================================================================
# 1. 애플리케이션 설정 (Configuration)
# 환경 변수를 통한 설정으로 오픈소스 배포 용이성 증대
# ==============================================================================

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "EwhaMarket_SecretKey")
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "..", "frontend", "uploads")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 기본 5MB
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = (os.getenv("FLASK_ENV") == "production")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=int(os.getenv("SESSION_DAYS", 7)))

logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# ==============================================================================
# 2. 데이터베이스 핸들러 (Lazy Loading for Testability)
# ==============================================================================

DB: Optional[DBhandler] = None

def get_db() -> DBhandler:
    """
    DBhandler 인스턴스를 싱글톤 패턴으로 로드하거나 반환합니다.
    테스트 환경에서 Mocking을 위해 사용됩니다.
    :return: (DBhandler) 데이터베이스 핸들러 인스턴스.
    """
    global DB
    if DB is None:
        DB = DBhandler()
    return DB

if DB is None:
    DB = get_db()

# ==============================================================================
# 3. 정적 페이지 및 리다이렉션 라우팅
# ==============================================================================

@app.route("/")
def home():
    """
    기본 경로('/')로 접근 시 상품 목록 페이지로 리디렉션합니다.
    :return: (Redirect) product_list 라우트로 리다이렉션.
    """
    return redirect(url_for('product_list'))

@app.route('/signup.html')
def signup_page():
    """
    회원가입 페이지를 렌더링합니다.
    :return: (HTML) signup.html
    """
    return render_template("signup.html")

@app.route('/login.html')
def login_page():
    """
    로그인 페이지를 렌더링합니다.
    :return: (HTML) login.html
    """
    return render_template("login.html")

@app.route('/product-create.html')
def product_create():
    """
    상품 등록 페이지를 렌더링합니다.
    :return: (HTML) product-create.html
    """
    return render_template('product-create.html')

@app.route('/product-wishlist.html')
def product_wishlist():
    """
    찜 목록 페이지를 렌더링합니다.
    :return: (HTML) product-wishlist.html
    """
    return render_template('product-wishlist.html')

@app.route('/product-detail.html')
def product_detail_static():
    """
    상품 상세 페이지의 정적 접근을 처리합니다. (실제 데이터 접근은 /product-detail/<name> 사용)
    :return: (HTML) product-detail.html
    """
    return render_template('product-detail.html')

# ==============================================================================
# 4. 사용자 인증 및 계정 관리 라우팅 (Auth & User)
# ==============================================================================

@app.route("/api/check_userid", methods=['GET'])
def check_userid():
    """
    [API] 사용자 ID 중복 확인을 처리합니다.
    :method: GET
    :query_param userid: (str) 확인할 사용자 ID.
    :return: (JSON) 사용 가능 여부. 상태 코드 200 또는 400.
    """
    userid = request.args.get('userid')
    if not userid:
        return jsonify({"available": False, "message": "아이디를 입력하세요."}), 400
    
    is_available = get_db().user_duplicate_check(userid)
    
    if is_available:
        return jsonify({"available": True}), 200
    else:
        return jsonify({"available": False}), 200

@app.route("/signup_post", methods=['POST'])
def register_user():
    """
    회원가입 폼 제출을 처리하고 사용자를 등록합니다.
    :method: POST
    :form_data id, pw, email: (str) 필수 사용자 정보.
    :return: (Redirect) 성공 시 login_page, 실패 시 signup_page로 리디렉션.
    """
    data = request.form
    pw = data.get('pw')
    
    pw_hash = hashlib.sha256(pw.encode('utf-8')).hexdigest()
    
    success = get_db().insert_user(data, pw_hash)
    
    if success:
        return redirect(url_for('login_page'))
    else:
        return redirect(url_for('signup_page'))

@app.route("/api/login_confirm", methods=['POST'])
def login_user():
    """
    [API] 사용자 로그인 인증을 처리합니다.
    :method: POST
    :form_data id, pw: (str) 사용자 ID와 비밀번호.
    :return: (JSON) 성공 여부. 상태 코드 200, 400 (필수 값 누락), 401 (인증 실패).
    """
    id_ = request.form.get('id')
    pw = request.form.get('pw')

    if not id_ or not pw:
        return jsonify({"success": False, "message": "필수 값 누락"}), 400

    pw_hash = hashlib.sha256(pw.encode('utf-8')).hexdigest()

    if get_db().find_user(id_, pw_hash):
        session['id'] = id_
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False, "message": "아이디 또는 비밀번호를 다시 입력하세요."}), 401

@app.route("/logout")
def logout():
    """
    사용자 세션을 제거하고 로그아웃 처리 후 상품 목록으로 리디렉션합니다.
    :return: (Redirect) product_list 라우트로 리다이렉션.
    """
    session.pop('id', None)
    return redirect(url_for('product_list'))

@app.route('/user-edit.html')
def user_edit_page():
    """
    개인정보 수정 페이지를 렌더링합니다.
    :return: (HTML) user-edit.html 또는 로그인 페이지로 리디렉션 (401), 사용자 정보 없음 (404).
    """
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session.get('id')
    user_info = get_db().get_user_info(user_id)

    if not user_info:
        return make_response("사용자 정보를 찾을 수 없습니다.", 404)
        
    return render_template("user-edit.html", user_info=user_info)


@app.route("/submit_user_edit", methods=['POST'])
def submit_user_edit():
    """
    개인정보 수정 폼 제출을 처리하고 DB 정보를 업데이트합니다.
    :method: POST
    :form_data current_pw, new_pw(선택), email, phone(선택): 사용자 수정 정보.
    :return: (JSON) 성공 여부. 상태 코드 200, 400, 401, 500.
    """
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    user_id = session['id']
    data = request.form
    
    current_pw = data.get('current_pw')
    if not current_pw:
        return jsonify({"success": False, "message": "현재 비밀번호를 입력해야 개인정보를 수정할 수 있습니다."}), 400

    current_pw_hash = hashlib.sha256(current_pw.encode('utf-8')).hexdigest()
    
    if not get_db().find_user(user_id, current_pw_hash):
        return jsonify({"success": False, "message": "현재 비밀번호가 일치하지 않습니다."}), 401

    new_pw = data.get('new_pw')
    new_pw_confirm = data.get('new_pw_confirm')
    pw_to_update = current_pw_hash

    if new_pw:
        if new_pw != new_pw_confirm:
            return jsonify({"success": False, "message": "새 비밀번호와 확인이 일치하지 않습니다."}), 400
        pw_to_update = hashlib.sha256(new_pw.encode('utf-8')).hexdigest()
    
    success = get_db().update_user_info(user_id, pw_to_update, data.get('email'), data.get('phone'))

    if success:
        return jsonify({"success": True, "message": "개인정보가 성공적으로 수정되었습니다."}), 200
    else:
        return jsonify({"success": False, "message": "DB 업데이트에 실패했습니다."}), 500

@app.route("/api/upload_profile_img", methods=['POST'])
def upload_profile_img():
    """
    [API] 사용자 프로필 이미지 업로드를 처리하고 DB 정보를 업데이트합니다.
    :method: POST
    :file_data profile_image: 업로드할 이미지 파일.
    :return: (JSON) 성공 여부와 이미지 경로. 상태 코드 200, 400, 401, 500.
    """
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    user_id = session['id']
    file = request.files.get('profile_image')

    if not file or not file.filename:
        return jsonify({"success": False, "message": "파일이 없습니다."}), 400

    try:
        ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "avif"}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({"success": False, "message": "허용되지 않는 파일 형식입니다."}), 400

        original_filename = secure_filename(file.filename)
        filename = f"{user_id}_{int(datetime.now().timestamp())}_{original_filename}"
        
        save_dir = os.path.join(app.config['UPLOAD_FOLDER'], "profile")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
        file.save(save_path)

        db_path = f"uploads/profile/{filename}"

        if get_db().update_user_profile_img(user_id, db_path):
            return jsonify({"success": True, "image_path": db_path}), 200
        else:
            app.logger.error("DB 업데이트 실패: update_user_profile_img for %s", user_id)
            return jsonify({"success": False, "message": "DB 업데이트 실패"}), 500

    except Exception:
        app.logger.exception("프로필 업로드 중 예외")
        return jsonify({"success": False, "message": "서버 오류"}), 500

# ==============================================================================
# 5. 상품 관리 라우팅 (Product)
# ==============================================================================

@app.route("/submit_item_post", methods=["POST"])
def submit_item_post():
    """
    상품 등록 폼 제출을 처리하고 Firebase에 상품 정보를 저장합니다.
    :method: POST
    :form_data title, price, category, status, desc, photos: 상품 정보 및 이미지.
    :return: (HTML Response) 성공 메시지 페이지 또는 오류 메시지 (400, 500).
    """
    author_id = session.get('id', 'unknown_user')
    if author_id == 'unknown_user':
        return redirect(url_for('login_page'))
        
    try:
        image_file = request.files.get("photos")
        img_path = ""
        
        if image_file and image_file.filename:
            import time
            original_filename = secure_filename(image_file.filename)
            key_name_sanitized = secure_filename(request.form.get("title", "unnamed_item"))
            
            unique_filename = f"{key_name_sanitized}_{int(time.time())}_{original_filename}"
            save_dir = os.path.join(app.config['UPLOAD_FOLDER'])
            os.makedirs(save_dir, exist_ok=True)
            img_path = f"uploads/{unique_filename}"
            image_file.save(os.path.join(save_dir, unique_filename))

        data = request.form
        key_name = data.get("title", "unnamed_item")
        trade_method = data.get('trade_method')

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        get_db().insert_item(key_name, data, img_path, author_id, trade_method, created_at)

        return f"""
        <html><body style='font-family:sans-serif; text-align:center;'>
        <h2>상품이 Firebase에 등록되었습니다 ✅</h2>
        <p><b>상품명:</b> {key_name}</p>
        <p><a href='/product-list.html'>목록으로 돌아가기</a></p>
        </body></html>
        """, 200

    except Exception:
        app.logger.exception("상품 등록 중 오류 발생")
        return make_response("<h3>❌ 오류 발생</h3>", 500)

@app.route('/product-list.html')
def product_list():
    """
    상품 목록을 조회하고 페이지네이션 및 카테고리 필터를 적용하여 렌더링합니다.
    :query_param page: (int) 현재 페이지 번호 (기본값 1).
    :query_param category: (str) 선택된 카테고리 (기본값 '전체').
    :return: (HTML) product-list.html
    """
    page = request.args.get("page", 1, type=int)
    per_page = 4
    start_idx = per_page * (page - 1)
    end_idx = per_page * page

    selected_category = request.args.get('category', '전체')

    all_items = get_db().get_items() or {}

    if selected_category and selected_category != '전체':
        filtered_items = {k: v for k, v in all_items.items() if (v.get('category') == selected_category)}
    else:
        filtered_items = all_items

    item_counts = len(filtered_items)
    page_count = (item_counts + per_page - 1) // per_page if item_counts > 0 else 1

    datas_for_page = dict(list(filtered_items.items())[start_idx:end_idx])
    
    like_info = {}
    current_user = session.get('id')
    db_handler = get_db()
    for item_key in datas_for_page.keys():
        try:
            count = db_handler.get_like_count(item_key)
            liked = db_handler.get_like_status(item_key, current_user) if current_user else False
        except Exception:
            app.logger.exception("like_info 조회 중 예외 for %s", item_key)
            count = 0
            liked = False
        like_info[item_key] = { 'liked': bool(liked), 'count': int(count) }

    return render_template(
        "product-list.html",
        datas=datas_for_page.items(),
        total=item_counts,
        page=page,
        page_count=page_count,
        selected_category=selected_category,
        like_info=like_info
    )

@app.route('/product-detail/<name>')
def product_detail(name: str):
    """
    특정 상품의 상세 정보를 조회하고 렌더링합니다.
    :param name: (str) 상품 이름 (Firebase Key).
    :return: (HTML) product-detail.html 또는 404 Not Found.
    """
    db_handler = get_db()
    data = db_handler.get_item_byname(str(name))
    
    if data:
        seller_info = {}
        try:
            author_id = data.get('author')
            if author_id:
                seller_info = db_handler.get_user_info(author_id) or {}
        except Exception:
            app.logger.exception("상품 판매자 정보 조회 중 예외")
            seller_info = {}

        current_user = session.get('id')
        liked = False
        try:
            liked = db_handler.get_like_status(name, current_user) if current_user else False
        except Exception:
            app.logger.exception("좋아요 상태 조회 중 예외 for %s", name)
            liked = False

        return render_template('product-detail.html', name=name, data=data, seller_info=seller_info, liked=bool(liked))
    else:
        return make_response("상품을 찾을 수 없습니다.", 404)

@app.route('/product-update.html')
def update_item_page():
    """
    상품 수정 페이지를 렌더링합니다.
    :query_param key: (str) 수정할 상품의 이름 (Firebase Key).
    :return: (HTML) product-update.html 또는 로그인/마이페이지로 리디렉션.
    """
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session.get('id')
    item_key = request.args.get('key')
    item_data = None
    
    if item_key:
        item_data = get_db().get_item_byname(item_key)
        
        if not item_data or item_data.get('author') != user_id:
            return redirect(url_for('mypage'))
        
    else:
        return redirect(url_for('mypage'))
        
    return render_template('product-update.html', 
                           item_data=item_data, 
                           item_key=item_key,
                           user_id=user_id)

@app.route("/submit_item_update", methods=["POST"])
def submit_item_update():
    """
    상품 수정 폼 제출을 처리하고 Firebase 정보를 업데이트합니다.
    :method: POST
    :form_data original_key, title, photos(선택): 수정된 상품 정보.
    :return: (HTML Response) 성공 메시지 페이지 또는 오류 메시지 (400, 500).
    """
    author_id = session.get('id', 'unknown_user')
    if author_id == 'unknown_user':
        return redirect(url_for('login_page'))
        
    try:
        data = request.form
        original_key = data.get("original_key")
        key_name = data.get("title", "unnamed_item")
        
        if not original_key:
            return make_response("<h3>❌ 오류 발생: 수정할 상품 키가 누락되었습니다.</h3>", 400)
        
        image_file = request.files.get("photos")
        img_path = ""
        
        if image_file and image_file.filename:
            import time
            original_filename = secure_filename(image_file.filename)
            key_name_sanitized = secure_filename(key_name)
            
            unique_filename = f"{key_name_sanitized}_{int(time.time())}_{original_filename}"
            save_dir = os.path.join(app.config['UPLOAD_FOLDER'])
            os.makedirs(save_dir, exist_ok=True)
            img_path = f"uploads/{unique_filename}"
            image_file.save(os.path.join(save_dir, unique_filename))

        get_db().update_item(original_key, data, img_path, author_id, new_key=key_name)
        
        return f"""
        <html><body style='font-family:sans-serif; text-align:center;'>
        <h2>상품이 성공적으로 수정되었습니다 ✅</h2>
        <p><b>상품명:</b> {key_name}</p>
        <p><a href='/mypage.html'>마이페이지로 돌아가기</a></p>
        </body></html>
        """, 200

    except Exception:
        app.logger.exception("상품 수정 중 오류 발생")
        return make_response("<h3>❌ 오류 발생</h3>", 500)
    
@app.route("/api/delete_item/<item_name>", methods=['POST'])
def delete_item_api(item_name: str):
    """
    [API] 특정 상품을 삭제합니다.
    :method: POST
    :param item_name: (str) 삭제할 상품 이름.
    :return: (JSON) 성공 여부. 상태 코드 200, 401, 500.
    """
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
    
    if get_db().delete_item(item_name):
        return jsonify({"success": True, "message": "상품이 삭제되었습니다."}), 200
    else:
        app.logger.error("DB 상품 삭제 실패: %s", item_name)
        return jsonify({"success": False, "message": "상품 삭제에 실패했습니다."}), 500
    
@app.route("/api/purchase", methods=['POST'])
def purchase_item_api():
    """
    [API] 상품 구매 요청을 처리하고 상태를 '거래 완료'로 변경합니다.
    :method: POST
    :json_data item_name: 구매할 상품 이름.
    :return: (JSON) 성공 여부. 상태 코드 200, 400 (본인 상품, 이미 완료), 401 (로그인 필요).
    """
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
    
    data = request.get_json() or {}
    item_name = data.get('item_name')
    buyer_id = session['id']
    
    if not item_name:
        return jsonify({"success": False, "message": "상품명이 누락되었습니다."}), 400

    db_handler = get_db()
    try:
        item = db_handler.get_item_byname(item_name)
        if item and item.get('author') == buyer_id:
            return jsonify({"success": False, "message": "자신이 등록한 상품은 구매할 수 없습니다."}), 400
    except Exception:
        app.logger.exception("purchase_item_api: DB 조회 중 예외")
        pass

    success, message = db_handler.purchase_item(item_name, buyer_id)
    if success:
        return jsonify({"success": True, "message": message}), 200
    else:
        return jsonify({"success": False, "message": message}), 400
    
    
@app.route("/api/like_status")
def like_status():
    """
    [API] 현재 사용자/상품의 좋아요 여부와 개수를 조회합니다.
    :method: GET
    :query_param item_name: (str) 상품 이름.
    :return: (JSON) 성공 여부, 좋아요 상태(liked), 로그인 상태, 좋아요 수. 상태 코드 200, 400.
    """
    item_name = request.args.get("item_name")
    if not item_name:
        return jsonify({"success": False, "message": "상품명이 필요합니다."}), 400

    user_id = session.get('id')
    db_handler = get_db()
    
    if not user_id:
        return jsonify({"success": True, "liked": False, "logged_in": False}), 200

    try:
        liked = db_handler.get_like_status(item_name, user_id)
        like_count = db_handler.get_like_count(item_name)
    except Exception:
        app.logger.exception("like_status 조회 중 예외 for %s", item_name)
        liked = False
        like_count = 0
        
    return jsonify({"success": True, "liked": liked, "logged_in": True, "like_count": like_count}), 200


@app.route("/api/toggle_like", methods=['POST'])
def toggle_like_api():
    """
    [API] 좋아요 상태를 토글하고 업데이트된 상태와 개수를 반환합니다.
    :method: POST
    :json_data item_name: (str) 좋아요를 토글할 상품 이름.
    :return: (JSON) 성공 여부, 새 좋아요 상태(liked), 좋아요 수. 상태 코드 200, 400, 401, 500.
    """
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data = request.get_json() or {}
    item_name = data.get("item_name")

    if not item_name:
        return jsonify({"success": False, "message": "상품명이 필요합니다."}), 400

    db_handler = get_db()
    try:
        item = db_handler.get_item_byname(item_name)
        if item and item.get('author') == session['id']:
            return jsonify({"success": False, "message": "자신이 등록한 상품은 찜할 수 없습니다."}), 400
    except Exception:
        app.logger.exception("toggle_like_api: DB 조회 중 예외")
        pass

    success, liked = db_handler.toggle_like(item_name, session['id'])

    if not success:
        return jsonify({"success": False, "message": "좋아요 처리에 실패했습니다."}), 500

    msg = "찜에 추가되었습니다" if liked else "찜에서 제거되었습니다."
    try:
        latest_count = db_handler.get_like_count(item_name)
    except Exception:
        app.logger.exception("toggle_like_api: like count 조회 중 예외 for %s", item_name)
        latest_count = 0

    return jsonify({"success": True, "liked": liked, "like_count": int(latest_count), "message": msg}), 200


# ==============================================================================
# 6. 리뷰 관리 라우팅 (Review)
# ==============================================================================

@app.route('/review-write.html')
def review_write():
    """
    리뷰 작성 페이지를 렌더링합니다.
    :query_param item_name: (str) 리뷰를 작성할 상품 이름.
    :return: (HTML) review-write.html 또는 로그인 페이지로 리디렉션.
    """
    item_name = request.args.get('item_name')
    user_id = session.get('id')

    if not user_id:
        return redirect(url_for('login_page'))
    
    product_data = None

    if item_name:
        product_data = get_db().get_item_byname(item_name)
    
    return render_template('review-write.html',
                           product=product_data,
                           product_key=item_name,
                           writer_id=user_id)

@app.route("/submit_review_post", methods=['POST'])
def submit_review_post():
    """
    리뷰 작성 폼 제출을 처리하고 Firebase에 리뷰 정보를 저장합니다.
    :method: POST
    :form_data item_name, reviewTitle, rating, reviewContent, review-photos(선택): 리뷰 정보 및 이미지.
    :return: (Redirect) 리뷰 목록 페이지로 리디렉션 또는 오류 메시지 (500).
    """
    writer_id = session.get('id')
    if not writer_id:
        return redirect(url_for('login_page'))
    
    try:
        data = request.form
        item_name = data.get("item_name")

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        image_file = request.files.get("review-photos")
        img_path = ""

        if image_file and image_file.filename:
            original_filename = secure_filename(image_file.filename)
            filename_key = f"{item_name}_{writer_id}_{original_filename}"
            
            save_dir = os.path.join(app.config['UPLOAD_FOLDER'])
            os.makedirs(save_dir, exist_ok=True)
            
            img_path = f"uploads/{filename_key}"
            image_file.save(os.path.join(save_dir, filename_key))

        get_db().reg_review(item_name, data, img_path, writer_id, current_time)

        return redirect(url_for('view_review'))
        
    except Exception:
        app.logger.exception("리뷰 등록 중 오류 발생")
        return make_response("<h3>❌ 리뷰 등록 오류 발생</h3>", 500)

@app.route('/review-detail/<review_key>')
def review_detail_by_key(review_key: str):
    """
    특정 리뷰의 상세 정보를 조회하고 렌더링합니다.
    :param review_key: (str) 조회할 리뷰의 고유 키 (item_name_writer_id).
    :return: (HTML) review-detail.html 또는 404 Not Found.
    """
    review_data = get_db().get_review_by_key(review_key)
    if review_data:
        return render_template('review-detail.html', review_data=review_data, review_key=review_key)
    else:
        return make_response("리뷰를 찾을 수 없습니다.", 404)


@app.route("/review")
def view_review():
    """
    전체 리뷰 목록을 조회하고 페이지네이션 및 정렬을 적용하여 렌더링합니다.
    :query_param page: (int) 현재 페이지 번호 (기본값 0).
    :query_param sort: (str) 정렬 옵션 ('latest' 또는 'rating').
    :return: (HTML) review.html.
    """
    page = request.args.get("page", 0, type=int)
    per_page = 8
    sort_option = request.args.get("sort", "latest")

    data = get_db().get_reviews() or {}
    data_list = list(data.items())
    db_handler = get_db()

    for _, review in data_list:
        writer_id = review.get("writer_id")
        if writer_id:
            user_info = db_handler.get_user_info(writer_id)
            review["profile_img"] = user_info.get("profile_img") if user_info else ""
        else:
            review["profile_img"] = ""

    def _parse_created(s: str) -> datetime:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.min

    if sort_option == "latest":
        data_list.sort(key=lambda x: _parse_created(x[1].get("created_at", "")), reverse=True)
    elif sort_option == "rating":
        data_list.sort(key=lambda x: float(x[1].get("rate", 0)), reverse=True)

    item_counts = len(data)
    page_count = (item_counts + per_page - 1) // per_page if item_counts > 0 else 1

    start_idx = per_page * page
    end_idx = per_page * (page + 1)
    datas = dict(data_list[start_idx:end_idx])

    row1 = dict(list(datas.items())[:2])
    row2 = dict(list(datas.items())[2:8])

    return render_template(
        "review.html",
        datas=datas.items(),
        row0=row1.items(),
        row1=row2.items(),
        page=page,
        page_count=page_count,
        total=item_counts,
        sort_option=sort_option,
    )


# ==============================================================================
# 7. 마이페이지 라우팅 (Mypage)
# ==============================================================================

@app.route('/mypage.html')
def mypage():
    """
    마이페이지를 렌더링합니다.
    :query_param page_sales: (int) 판매 상품 페이지 번호 (기본값 1).
    :query_param page_purchases: (int) 구매 상품 페이지 번호 (기본값 1).
    :return: (HTML) mypage.html 또는 로그인 페이지로 리디렉션.
    """
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session['id']

    sales_page = request.args.get("page_sales", 1, type=int)
    purchase_page = request.args.get("page_purchases", 1, type=int)
    per_page = 3
    db_handler = get_db()

    user_info = db_handler.get_user_info(user_id) or {'profile_img': ''}
    all_items = db_handler.get_items() or {}

    my_sales = {k: v for k, v in all_items.items() if v.get('author') == user_id}
    my_purchases = {k: v for k, v in all_items.items() if v.get('buyer') == user_id}

    sales_list = list(my_sales.items())
    sales_total = len(sales_list)
    sales_page_count = max((sales_total + per_page - 1) // per_page, 1)

    sales_start = (sales_page - 1) * per_page
    sales_end = sales_page * per_page
    sales_items = sales_list[sales_start:sales_end]

    purchases_list = list(my_purchases.items())
    purchase_total = len(purchases_list)
    purchase_page_count = max((purchase_total + per_page - 1) // per_page, 1)

    purchase_start = (purchase_page - 1) * per_page
    purchase_end = purchase_page * per_page
    purchase_items = purchases_list[purchase_start:purchase_end]

    purchase_review_status = {k: db_handler.check_review_exists(k, user_id) for k, _ in my_purchases.items()}

    available_count = sum(1 for item in my_sales.values() if item.get('status') != '거래 완료')
    sold_count = sum(1 for item in my_sales.values() if item.get('status') == '거래 완료')

    return render_template(
        'mypage.html',
        user_id=user_id,
        user_info=user_info,

        my_sales=sales_items,
        my_purchases=purchase_items,

        sales_page=sales_page,
        sales_page_count=sales_page_count,
        purchase_page=purchase_page,
        purchase_page_count=purchase_page_count,

        purchase_review_status=purchase_review_status,
        available_count=available_count,
        sold_count=sold_count
    )

# ==============================================================================
# 8. 유틸리티 함수 및 컨텍스트 프로세서
# ==============================================================================

def format_time_ago(timestamp_str: str) -> str:
    """
    'YYYY-MM-DD HH:MM:SS' 형식의 타임스탬프를 상대적 시간으로 변환합니다.
    :param timestamp_str: (str) Firebase에 저장된 시간 문자열.
    :return: (str) 상대적 시간 문자열 또는 원본 문자열.
    """
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S" 
    try:
        posted_time = datetime.strptime(timestamp_str, TIME_FORMAT)
    except (ValueError, TypeError):
        return timestamp_str
    
    now = datetime.now()
    delta = now - posted_time
    
    seconds = delta.total_seconds()
    days = delta.days

    if seconds < 60:
        return f"{int(seconds)}초 전"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}분 전"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}시간 전"
    elif days < 30:
        return f"{days}일 전"
    elif days < 365:
        months = int(days / 30)
        return f"{months}달 전"
    else:
        years = int(days / 365)
        return f"{years}년 전"


@app.template_filter('nl2br')
def nl2br_filter(s: str) -> Markup:
    """
    줄바꿈 문자(\n)를 HTML <br> 태그로 변환하는 Jinja2 필터입니다.
    :param s: (str) 입력 문자열.
    :return: (Markup) <br> 태그로 치환된 HTML 문자열.
    """
    if not isinstance(s, str):
        s = str(s)
    
    return Markup(s.replace('\n', '<br>'))


@app.context_processor
def inject_user_and_time() -> Dict[str, Any]: 
    """
    모든 템플릿에 현재 로그인된 사용자 ID와 시간 포맷 함수를 주입합니다.
    :return: (dict) 주입할 컨텍스트 변수.
    """
    return dict(user_id=session.get('id'),
                format_time_ago=format_time_ago)

# ==============================================================================
# 9. 애플리케이션 실행
# ==============================================================================

if __name__ == "__main__":
    # 두 가지 방법으로 실행 가능
    # 1) python backend/app.py
    # 2) flask --app backend/app.py --debug run
    app.run(host='0.0.0.0')
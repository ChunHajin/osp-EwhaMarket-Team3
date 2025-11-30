from flask import Flask, request, redirect, session, jsonify, render_template, url_for
from database import DBhandler
from datetime import datetime, timedelta
from markupsafe import Markup
import hashlib
import json
import os


app = Flask(__name__,
            static_folder="../frontend",
            template_folder="../frontend",
            static_url_path=""
           )
app.config["SECRET_KEY"] = "EwhaMarket_SecretKey" # 세션 관리를 위한 시크릿 키 (필수)

#app.add_url_rule('/uploads/<path:filename>', endpoint='uploads', view_func=app.send_static_file)

DB = DBhandler()

@app.route("/")
def home():
    # 기본 페이지를 product-list.html로 리디렉션
    # 화면 이동 구현 안 된 페이지의 경우 주소창에서 html 파일명 직접 수정해 접속
    return redirect(url_for('product_list'))

@app.route('/signup.html')
def signup_page():
    return render_template("signup.html")

@app.route('/login.html')
def login_page():
    return render_template("login.html")

@app.route('/product-create.html')
def product_create():
    return render_template('product-create.html')

@app.route('/product-wishlist.html')
def product_wishlist():
    return render_template('product-wishlist.html')

@app.route('/review-write.html')
def review_write():
    item_name = request.args.get('item_name')
    user_id = session.get('id')

    if not user_id:
        return redirect(url_for('login_page'))
    

    product_data = None

    # 상품 이름으로 DB에서 상품 정보 조회
    if item_name:
        product_data = DB.get_item_byname(item_name)
    
    return render_template('review-write.html',
                           product=product_data,
                           product_key=item_name,
                           writer_id=user_id)

@app.route("/submit_review_post", methods=['POST'])
def submit_review_post():
    writer_id = session.get('id')
    if not writer_id:
        return redirect(url_for('login_page'))
    
    try:
        data = request.form
        item_name = data.get("item_name")

        # 작성 시간 생성
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        image_file = request.files.get("review-photos")
        img_path = ""

        if image_file and image_file.filename:
            save_dir = os.path.join(os.getcwd(), "frontend", "uploads")
            if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)    

            filename_key = f"{item_name}_{writer_id}_{image_file.filename}"
            img_path = f"uploads/{filename_key}"
            image_file.save(os.path.join(save_dir, filename_key))

        DB.reg_review(item_name, data, img_path, writer_id, current_time)

        return redirect(url_for('view_review'))
        
    except Exception as e:
        print(f"리뷰 등록 중 오류 발생: {e}")
        return f"<h3>❌ 리뷰 등록 오류 발생: {e}</h3>", 500

@app.route('/review-detail/<review_key>')
def review_detail_by_key(review_key):
    # path에 들어온 키(review_key)로 DB에서 직접 조회.
    # review_key는 reg_review에서 생성한 키.
    review_data = DB.get_review_by_key(review_key)
    if review_data:
        return render_template('review-detail.html', review_data=review_data, review_key=review_key)
    else:
        return "리뷰를 찾을 수 없습니다.", 404



@app.route("/review")
def view_review():
    page = request.args.get("page",0,type=int)
    per_page=8
    per_row=2

    data=DB.get_reviews()
    if not data:
        data={}

    item_counts=len(data)
 
    data_list=list(data.items()) #딕셔너리->리스트변환
    page_count=int((item_counts/per_page)+1) #전체페이지수 계산

    
    start_idx=per_page*page
    end_idx=per_page*(page+1) #현재 페이지에 뿌릴 데이터

    datas = dict(data_list[start_idx:end_idx])

    row1=dict(list(datas.items())[:2])
    row2=dict(list(datas.items())[2:8]) #row1 row2분리

    return render_template(
        "review.html",
        datas=datas.items(),
        row0=row1.items(),
        row1=row2.items(),
        page=page,
        page_count=page_count,
        total=item_counts
    )



@app.route('/mypage.html')
def mypage():
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session['id']
    
    # 사용자 정보 가져오기
    user_info = DB.get_user_info(user_id)
    if not user_info:
        user_info = {'profile_img': ''}
    elif not user_info.get('profile_img'):
        user_info['profile_img'] = ''
        
    # 전체 상품 가져오기
    all_items = DB.get_items()
    if not all_items:
        all_items = {}
    
    # 내 판매 상품 (작성자가 나인 경우)
    my_sales = {k: v for k, v in all_items.items() if v.get('author') == user_id}
    
    # 내 구매 상품 (구매자가 나인 경우)
    my_purchases = {k: v for k, v in all_items.items() if v.get('buyer') == user_id}
    
     # 각 구매한 상품에 대해 리뷰 존재 여부 확인
    purchase_review_status = {}
    for item_key in my_purchases.keys():
        purchase_review_status[item_key] = DB.check_review_exists(item_key, user_id)

    available_count = sum(1 for item in my_sales.values() if item.get('status') != '거래 완료')
    sold_count = sum(1 for item in my_sales.values() if item.get('status') == '거래 완료')

    return render_template('mypage.html',
                           user_id=user_id,
                           user_info=user_info,
                           my_sales=my_sales.items(),
                           my_purchases=my_purchases.items(),
                           purchase_review_status=purchase_review_status,
                           available_count=available_count,
                           sold_count=sold_count)


@app.route("/api/upload_profile_img", methods=['POST'])
def upload_profile_img():
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    user_id = session['id']
    file = request.files.get('profile_image')

    if not file:
        return jsonify({"success": False, "message": "파일이 없습니다."}), 400

    try:
        # 파일 저장 경로 설정 (uploads/profile 폴더 사용)
        save_dir = os.path.join(os.getcwd(), "frontend", "uploads", "profile")
        os.makedirs(save_dir, exist_ok=True)

        # 파일명 중복 방지를 위해 ID와 시간을 조합
        filename = f"{user_id}_{int(datetime.now().timestamp())}_{file.filename}"
        save_path = os.path.join(save_dir, filename)
        file.save(save_path)

        # 웹에서 접근 가능한 경로 (static_url_path 기준)
        db_path = f"uploads/profile/{filename}"

        # DB 업데이트
        if DB.update_user_profile_img(user_id, db_path):
            return jsonify({"success": True, "image_path": db_path})
        else:
            return jsonify({"success": False, "message": "DB 업데이트 실패"}), 500

    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": "서버 오류"}), 500


@app.route('/user-edit.html')
def user_edit_page():
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session.get('id')
    user_info = DB.get_user_info(user_id)

    if not user_info:
        return "사용자 정보를 찾을 수 없습니다.", 404
        
    return render_template("user-edit.html", user_info=user_info)


@app.route("/submit_user_edit", methods=['POST'])
def submit_user_edit():
    # 1. 로그인 여부 확인
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    user_id = session['id']
    data = request.form
    
    # 2. 현재 비밀번호 확인
    current_pw = data.get('current_pw')
    if not current_pw:
        return jsonify({"success": False, "message": "현재 비밀번호를 입력해야 개인정보를 수정할 수 있습니다."}), 400

    # 현재 비밀번호 해시
    current_pw_hash = hashlib.sha256(current_pw.encode('utf-8')).hexdigest()
    
    # DB에서 아이디/비밀번호 매칭 확인
    if not DB.find_user(user_id, current_pw_hash):
        return jsonify({"success": False, "message": "현재 비밀번호가 일치하지 않습니다."}), 401

    # 3. 새 비밀번호 처리
    new_pw = data.get('new_pw')
    new_pw_confirm = data.get('new_pw_confirm')
    pw_to_update = current_pw_hash # 기본값은 기존 비밀번호 해시

    if new_pw:
        if new_pw != new_pw_confirm:
            return jsonify({"success": False, "message": "새 비밀번호와 확인이 일치하지 않습니다."}), 400
        # 새 비밀번호 해시
        pw_to_update = hashlib.sha256(new_pw.encode('utf-8')).hexdigest()
    
    # 4. DB 업데이트
    success = DB.update_user_info(user_id, pw_to_update, data.get('email'), data.get('phone'))

    if success:
        return jsonify({"success": True, "message": "개인정보가 성공적으로 수정되었습니다."})
    else:
        return jsonify({"success": False, "message": "DB 업데이트에 실패했습니다."}), 500

@app.route('/product-update.html')
def update_item_page():
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session.get('id')
    
    item_key = request.args.get('key')
    item_data = None
    
    if item_key:
        item_data = DB.get_item_byname(item_key)
        
        # 상품이 없거나, 내가 등록한 상품이 아닌 경우 접근 제어
        if not item_data or item_data.get('author') != user_id:
            # 권한이 없거나 상품이 없으면 마이페이지로 돌려보냄
            return redirect(url_for('mypage'))
        
    else:
        # 키가 없으면 마이페이지로 돌려보냄
        return redirect(url_for('mypage'))
        
    return render_template('product-update.html', 
                           item_data=item_data, 
                           item_key=item_key,
                           user_id=user_id)

@app.route("/submit_item_update", methods=["POST"])
def submit_item_update():
    author_id = session.get('id', 'unknown_user')
    if author_id == 'unknown_user':
        return redirect(url_for('login_page'))
        
    try:
        data = request.form
        original_key = data.get("original_key") # hidden 필드에서 가져온 기존 키
        key_name = data.get("title", "unnamed_item") # 폼에서 입력된 새 상품명
        
        if not original_key:
            return "<h3>❌ 오류 발생: 수정할 상품 키가 누락되었습니다.</h3>", 400
        
        image_file = request.files.get("photos")
        img_path = ""
        
        if image_file and image_file.filename:
            import time
            save_dir = os.path.join(os.getcwd(), "frontend", "uploads")
            os.makedirs(save_dir, exist_ok=True) 
            
            unique_filename = f"{key_name}_{int(time.time())}_{image_file.filename}"
            img_path = f"uploads/{unique_filename}"
            image_file.save(os.path.join(save_dir, unique_filename))
        
        DB.update_item(original_key, data, img_path, author_id, new_key=key_name)
        
        return f"""
        <html><body style='font-family:sans-serif; text-align:center;'>
        <h2>상품이 성공적으로 수정되었습니다 ✅</h2>
        <p><b>상품명:</b> {key_name}</p>
        <p><a href='/mypage.html'>마이페이지로 돌아가기</a></p>
        </body></html>
        """

    except Exception as e:
        print(f"상품 수정 중 오류 발생: {e}")
        return f"<h3>❌ 오류 발생: {e}</h3>", 500
    
@app.route("/api/delete_item/<item_name>", methods=['POST'])
def delete_item_api(item_name):
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
    
    if DB.delete_item(item_name):
        return jsonify({"success": True, "message": "상품이 삭제되었습니다."})
    else:
        return jsonify({"success": False, "message": "상품 삭제에 실패했습니다."}), 500
    
@app.route("/api/login_confirm", methods=['POST'])
def login_user():
    id_ = request.form.get('id')
    pw = request.form.get('pw')

    if not id_ or not pw:
        return jsonify({"success": False, "message": "필수 값 누락"}), 400

    pw_hash = hashlib.sha256(pw.encode('utf-8')).hexdigest()

    if DB.find_user(id_, pw_hash):
        session['id'] = id_
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "아이디 또는 비밀번호를 다시 입력하세요."}), 401

@app.route("/logout")
def logout():
    session.pop('id', None)
    return redirect(url_for('product_list'))


# 1. ID 중복 확인 API (signup.html의 fetch 요청 처리)
@app.route("/api/check_userid", methods=['GET'])
def check_userid():
    userid = request.args.get('userid')
    if not userid:
        return jsonify({"available": False, "message": "아이디를 입력하세요."}), 400
    
    # database.py의 user_duplicate_check 함수 호출
    is_available = DB.user_duplicate_check(userid)
    
    if is_available:
        return jsonify({"available": True})
    else:
        return jsonify({"available": False})


# 2. 회원가입 폼 제출 API (signup.html의 form action 처리)
@app.route("/signup_post", methods=['POST'])
def register_user():
    data = request.form
    
    # 비밀번호 해시 처리
    pw = data.get('pw')
    pw_hash = hashlib.sha256(pw.encode('utf-8')).hexdigest()
    
    # database.py의 insert_user 함수 호출
    success = DB.insert_user(data, pw_hash)
    
    if success:
        # 회원가입 성공 시 로그인 페이지로 리디렉션
        return redirect(url_for('login_page'))
    else:
        # 회원가입 실패 (ID 중복 등) 시 다시 회원가입 페이지로
        # TODO: flash 메시지 사용해 사용자에게 알리기
        return redirect(url_for('signup_page'))


# 3. 상품 등록 폼 제출 처리 API (product-create.html의 form action 처리)
@app.route("/submit_item_post", methods=["POST"])
def submit_item_post():
    try:
        # 1. 이미지 파일 처리
        image_file = request.files.get("photos")
        img_path = ""
        if image_file and image_file.filename:
            # 이미지를 저장할 경로 설정
            save_dir = os.path.join(os.getcwd(), "frontend", "uploads")
            os.makedirs(save_dir, exist_ok=True) # 폴더가 없으면 생성
            img_path = f"uploads/{image_file.filename}"
            image_file.save(os.path.join(save_dir, image_file.filename))

        # 2. 폼 데이터 수집
        data = request.form
        key_name = data.get("title", "unnamed_item")
        author_id = session.get('id', 'unknown_user')
        trade_method = data.get('trade_method')

        # 3. Firebase에 저장 (생성 시각을 포함하여 DB에 저장)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        DB.insert_item(key_name, data, img_path, author_id, trade_method, created_at)

        # 4. 성공 페이지 반환
        return f"""
        <html><body style='font-family:sans-serif; text-align:center;'>
        <h2>상품이 Firebase에 등록되었습니다 ✅</h2>
        <p><b>상품명:</b> {key_name}</p>
        <p><a href='/product-list.html'>목록으로 돌아가기</a></p>
        </body></html>
        """

    except Exception as e:
        return f"<h3>❌ 오류 발생: {e}</h3>", 500

@app.route('/product-list.html')
def product_list():
    page = request.args.get("page", 1, type=int) 
    per_page = 4 
    start_idx = per_page * (page - 1)
    end_idx = per_page * page
    data = DB.get_items() 
    
    if not data:
        data = {}

    item_counts = len(data)
    page_count = (item_counts + per_page - 1) // per_page
    datas_for_page = dict(list(data.items())[start_idx:end_idx])

    return render_template(
        "product-list.html", 
        datas=datas_for_page.items(),
        total=item_counts,
        page=page,
        page_count=page_count 
    )

@app.route('/product-detail.html')
def product_detail_static():
    return render_template('product-detail.html')

@app.route('/product-detail/<name>')
def product_detail(name):
    
    data = DB.get_item_byname(str(name))
    
    if data:
        seller_info = None
        try:
            author_id = data.get('author')
            if author_id:
                seller_info = DB.get_user_info(author_id) or {}
        except Exception:
            seller_info = {}

        # 템플릿에 data와 seller_info 전달
        return render_template('product-detail.html', name=name, data=data, seller_info=seller_info)
    else:
        return "상품을 찾을 수 없습니다.", 404

@app.context_processor
def inject_user():
    return dict(user_id=session.get('id'))

@app.route("/api/purchase", methods=['POST'])
def purchase_item_api():
    # 1. 로그인 여부 확인
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401
    
    data = request.get_json()
    item_name = data.get('item_name')
    buyer_id = session['id']
    
    # 2. DB 업데이트 요청
    success, message = DB.purchase_item(item_name, buyer_id)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        # 이미 거래 완료 등 클라이언트에 보여줄 메시지가 있는 경우 400으로 응답
        return jsonify({"success": False, "message": message}), 400
    
    
# -------------------- 여기부터 좋아요 기능 API 추가 --------------------

@app.route("/api/like_status")
def like_status():
    """
    페이지 로딩 시 현재 사용자/상품의 좋아요 여부 조회
    """
    item_name = request.args.get("item_name")
    if not item_name:
        return jsonify({"success": False, "message": "상품명이 필요합니다."}), 400

    user_id = session.get('id')
    # 로그인 안 했으면 liked=False 로 응답
    if not user_id:
        return jsonify({"success": True, "liked": False, "logged_in": False})

    liked = DB.get_like_status(item_name, user_id)
    return jsonify({"success": True, "liked": liked, "logged_in": True})


@app.route("/api/toggle_like", methods=['POST'])
def toggle_like_api():
    """
    좋아요 / 안좋아요 토글
    """
    if 'id' not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data = request.get_json() or {}
    item_name = data.get("item_name")

    if not item_name:
        return jsonify({"success": False, "message": "상품명이 필요합니다."}), 400

    success, liked = DB.toggle_like(item_name, session['id'])

    if not success:
        return jsonify({"success": False, "message": "좋아요 처리에 실패했습니다."}), 500

    msg = "찜에 추가되었습니다" if liked else "찜에서 제거되었습니다."
    return jsonify({"success": True, "liked": liked, "message": msg})

# ----------------------------------------------------------------------

# 시간을 상대적 포맷(n초 전 ~ n년 전)으로 변환
def format_time_ago(timestamp_str):
    """
    'YYYY-MM-DD HH:MM:SS' 형식의 타임스탬프를 'n초 전', 'n분 전', 'n시간 전', 'n일 전', 'n달 전', 'n년 전'으로 변환
    """
    # Firebase DB에 저장된 형식에 따라 strptime의 형식을 변경해야 할 수 있음
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S" 
    try:
        posted_time = datetime.strptime(timestamp_str, TIME_FORMAT)
    except (ValueError, TypeError):
        return timestamp_str
    
    now = datetime.now()
    delta = now - posted_time
    
    # 초 단위 차이
    seconds = delta.total_seconds()
    days = delta.days

    if seconds < 60:
        return f"{int(seconds)}초 전"
    elif seconds < 3600: # 1시간 미만
        minutes = int(seconds / 60)
        return f"{minutes}분 전"
    elif seconds < 86400: # 24시간 미만
        hours = int(seconds / 3600)
        return f"{hours}시간 전"
    elif days < 30: # 30일 미만 (대략 1달 미만)
        return f"{days}일 전"
    elif days < 365: # 365일 미만 (대략 1년 미만)
        months = int(days / 30)
        return f"{months}달 전"
    else: # 365일 이상 (1년 이상)
        years = int(days / 365)
        return f"{years}년 전"


@app.context_processor
def inject_user_and_time(): 
    return dict(user_id=session.get('id'),
                format_time_ago=format_time_ago)

# -------------------- 여기부터 Jinja2 필터 추가 --------------------
@app.template_filter('nl2br')
def nl2br_filter(s):
    """줄바꿈 문자(\n)를 HTML <br> 태그로 변환하는 Jinja2 필터"""
    if not isinstance(s, str):
        s = str(s)
    
    # \n을 <br> 태그로 치환하고 Markup 객체로 반환하여 HTML로 인식시킵니다.
    return Markup(s.replace('\n', '<br>'))

if __name__ == "__main__":
    # 두 가지 방법으로 실행 가능
    # 1) python backend/app.py
    # 2) flask --app backend/app.py --debug run
    app.run(host='0.0.0.0')
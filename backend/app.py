from flask import Flask, request, redirect, session, jsonify, render_template, url_for
from database import DBhandler
import hashlib
import json
import os


app = Flask(__name__,
            static_folder="../frontend",
            template_folder="../frontend",
            static_url_path=""
           )
app.config["SECRET_KEY"] = "EwhaMarket_SecretKey" # 세션 관리를 위한 시크릿 키 (필수)

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
    return render_template('review-write.html')

@app.route('/review-detail.html')
def review_detail():
    return render_template('review-detail.html')

@app.route('/review.html')
def review_page():
    return render_template('review.html')

@app.route('/mypage.html')
def mypage():
    if 'id' not in session:
        return redirect(url_for('login_page'))
    
    user_id = session['id']
    
    # 전체 상품 가져오기
    all_items = DB.get_items()
    if not all_items:
        all_items = {}
    
    # 내 판매 상품 (작성자가 나인 경우)
    my_sales = {k: v for k, v in all_items.items() if v.get('author') == user_id}
    
    # 내 구매 상품 (구매자가 나인 경우)
    my_purchases = {k: v for k, v in all_items.items() if v.get('buyer') == user_id}
    
    return render_template('mypage.html', 
                           user_id=user_id, 
                           my_sales=my_sales.items(), 
                           my_purchases=my_purchases.items())

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

        # 3. Firebase에 저장 (새로 추가된 DB 함수 호출)
        DB.insert_item(key_name, data, img_path, author_id, trade_method)

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
        return render_template('product-detail.html', name=name, data=data)
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
    if DB.purchase_item(item_name, buyer_id):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "구매 처리에 실패했습니다."}), 500
    
    
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

    msg = "좋아요 완료!" if liked else "안좋아요 완료!"
    return jsonify({"success": True, "liked": liked, "message": msg})

# ----------------------------------------------------------------------

if __name__ == "__main__":
    # 두 가지 방법으로 실행 가능
    # 1) python backend/app.py
    # 2) flask --app backend/app.py --debug run
    app.run(host='0.0.0.0')
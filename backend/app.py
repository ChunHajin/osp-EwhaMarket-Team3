from flask import Flask, request, redirect, session, jsonify, render_template, url_for,flash
from database import DBhandler
import hashlib
import json
import sys


app = Flask(__name__,
            static_folder="../frontend",
            template_folder="../frontend",
            static_url_path="/"
           )
app.config["SECRET_KEY"] = "EwhaMarket_SecretKey" # 세션 관리를 위한 시크릿 키 (필수)

DB = DBhandler()

@app.route("/")
def home():
    # 기본 페이지를 product-list.html로 리디렉션
    # 다른 페이지 접속 필요 시 주소창의 html 파일명 직접 입력하세요 (임시 방편)
    return redirect(url_for('product_list'))

@app.route('/product-list.html')
def product_list():
    return render_template("product-list.html")

@app.route('/signup.html')
def signup_page():
    return render_template("signup.html")

@app.route('/login')
@app.route('/login.html')
def login_page():
    return render_template("login.html")


    
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
        return jsonify({"success": False, "message": "아이디 또는 비밀번호를 다시 입력하세요,"}),401

@app.route("/logout")
def logout_user():
    session.pop('id',None)
    flash("로그아웃 되었습니다.")
    return render_template("login.html")



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
    
    # PDF 53페이지 참고: 비밀번호 해시 처리
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

@app.context_processor
def inject_user():
    return dict(user_id=session.get('id'))


if __name__ == "__main__":
    # frontend 폴더와 backend 폴더가 있는 루트에서 
    # python -m backend.app (혹은 python backend/app.py)로 실행
    # TODO: 제출 시 flask --debug run 사용하도록 수정
    app.run(host='0.0.0.0', port=5001, debug=True)
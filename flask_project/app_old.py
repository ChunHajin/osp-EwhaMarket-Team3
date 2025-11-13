from flask import Flask, render_template, request
import sys

application = Flask(__name__)
application.config["SECRET_KEY"] = "helloosp"

DB = DBhandler()

@application.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    application.run(host='0.0.0.0')
    
@application.route("/list")
def view_list():
    return render_template("list.html")

@application.route("/review")
def view_review():
    return render_template("review.html")

@application.route("/reg_items")
def reg_item():
    return render_template("reg_items.html")

@application.route("/reg_reviews")
def reg_review():
    return render_template("reg_reviews.html")

@application.route("/submit_item")
def reg_item_submit():
    name = request.args.get("name")
    seller = request.args.get("seller")
    addr = request.args.get("addr")
    email = request.args.get("email")
    category = request.args.get("category")
    card = request.args.get("card")
    status = request.args.get("status")
    phone = request.args.get("phone")
    print(name, seller, addr, email, category, card, status, phone)
    
@application.route("/submit_item_post", methods=['POST'])
def reg_item_submit_post():
    image_file = request.files["file"]
    image_file.save("static/images/{}".format(image_file.filename))
    data = request.form
    return render_template("submit_item_result.html", data = data, img_path="static/images/{}".format(image_file.filename))

# 로그인 페이지
@application.route("/login")
def login():
    return render_template("login.html")


# 회원가입 페이지
@application.route("/signup")
def signup():
    return render_template("signup.html")


# 회원가입 처리
@application.route("/signup_post", methods=['POST'])
def register_user():
    data = request.form
    pw = data.get('pw')

    # 비밀번호 암호화
    pw_hash = hashlib.sha256(pw.encode('utf-8')).hexdigest()

    # DB에 회원 추가 시도
    if DB.insert_user(data, pw_hash):
        flash("회원가입이 완료되었습니다. 로그인 해주세요.")
        return redirect(url_for("login"))
    else:
        flash("이미 존재하는 아이디입니다.")
        return redirect(url_for("signup"))


# ---------------------------
# 실행
# ---------------------------
if __name__ == "__main__":
    application.run(host='0.0.0.0', debug=True)
# 標準函式庫
import os

# 第三方套件
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request, session
from flask_login import UserMixin, login_user
import requests
auth_bp = Blueprint("auth", __name__)


class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


web_path = f"{os.getcwd()}/web"

load_dotenv(override=True)


USER_DATA = {
    "superuser": os.getenv("SUPERUSER"),
    "root": os.getenv("ROOT"),
    "admin": os.getenv("ADMIN"),
    "user": os.getenv("USER"),
    "kiosk": os.getenv("KIOSK"),
}


user_login_info = {"username": "", "password": ""}

active_superuser = []
max_login = 3


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_login_info["username"] = username
        user_login_info["password"] = password
    else:
        username = request.args.get("username")
        password = request.args.get("password")
        user_login_info["username"] = username
        user_login_info["password"] = password

    if not username or not password:
        return jsonify(success=False)

    if USER_DATA.get(username) and USER_DATA.get(username) == password:
        user = User(username)
        login_user(user)
        session["username"] = username
        return jsonify(success=True)
    else:
        return jsonify(success=False)

@auth_bp.route("/get_redfish_admin", methods=["GET"])
def get_redfish_admin():
    admin_account = "admin"
    superuser_account = "superuser"
    superuser_password = "scrypt:32768:8:1$4muYEoJRQ6ajfqvO$7a1a983e81b2ddf0dcfcf9f49bb3471671f029dcf9f93aeec4f6e2fa698673f9a0cd533498d23051bc84cc175bb11ee7e6384588a5c5f4773af0fd6b18d00ad5"
    target_url = "https://localhost:8000/redfish/v1/Managers/1/Accounts"
    try:
        # Attempt to get the admin account
        response = requests.get(target_url, auth=(superuser_account, superuser_password), verify=False)
        if response.status_code == 200:
            return response
    except requests.exceptions.RequestException as e:
        print(f"Error accessing Redfish API with admin account: {e}")
    
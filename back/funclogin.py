import json
import os
from flask import session, redirect, url_for, render_template, request
from werkzeug.security import generate_password_hash, check_password_hash

USER_FILE = os.path.join(os.path.dirname(__file__), "users.json")

def load_users():
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def get_user_by_username(username):
    users = load_users()
    username = username.strip()
    for user in users:
        if user["username"] == username:
            return user
    return None

def create_user(username, email, password):
    users = load_users()
    if get_user_by_username(username):
        return False  # User đã tồn tại
    hashed_pw = generate_password_hash(password)
    users.append({
        "username": username.strip(),
        "email": email.strip(),
        "passwd": hashed_pw
    })
    save_users(users)
    return True

def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('passwd', '').strip()
        user = get_user_by_username(username)
        if user and check_password_hash(user['passwd'], password):
            session['username'] = user['username'].strip()
            return redirect(url_for('dashboard'))
        else:
            error = 'Sai tên đăng nhập hoặc mật khẩu!'
            return render_template('auth.html', error=error)
    return render_template('auth.html')

def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('passwd', '').strip()

        if not username or not email or not password:
            error = 'Vui lòng nhập đầy đủ thông tin!'
            return render_template('auth.html', error=error)

        if get_user_by_username(username):
            error = 'Tên đăng nhập đã tồn tại!'
            return render_template('auth.html', error=error)

        if create_user(username, email, password):
            msg = 'Đăng ký thành công! Đăng nhập ngay!'
            return render_template('auth.html', message=msg)
        else:
            return render_template('auth.html', error='Đã xảy ra lỗi!')
    return render_template('auth.html')
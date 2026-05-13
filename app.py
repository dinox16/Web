import os
import re
import json

from dotenv import load_dotenv
from flask import (
    Flask, abort, jsonify, redirect, render_template, request, session, url_for
)

from back import db
from back.funclogin import (
    forgot_start, forgot_verify, login, logout_view, otp_resend,
    register_start, register_verify
)
from back.funcdash import (
    dashboard_route, get_subject, get_subjects, quiz, subject_detail, score_answers
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")


# --- helpers ---------------------------------------------------------------

def _require_login():
    if "username" not in session:
        return redirect(url_for("auth"))
    return None


@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.context_processor
def inject_globals():
    return {
        "current_user": session.get("username"),
        "current_email": session.get("email"),
    }


# --- pages -----------------------------------------------------------------

@app.route("/")
def home():
    if "username" not in session:
        return redirect(url_for("auth"))
    return redirect(url_for("dashboard"))


@app.route("/auth", methods=["GET"])
def auth():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("auth.html")


@app.route("/dashboard")
def dashboard():
    guard = _require_login()
    if guard:
        return guard
    return dashboard_route()


@app.route("/logout")
def logout_route():
    return logout_view()


@app.route("/subject/<subject_slug>")
def subject_detail_route(subject_slug):
    guard = _require_login()
    if guard:
        return guard
    return subject_detail(subject_slug)


@app.route("/quiz/<subject_slug>")
def quiz_dashboard(subject_slug):
    guard = _require_login()
    if guard:
        return guard
    return quiz(subject_slug)


@app.route("/chatbot")
@app.route("/chatbot/<subject_slug>")
def chatbot_page(subject_slug=None):
    guard = _require_login()
    if guard:
        return guard
    subject = get_subject(subject_slug) if subject_slug else None
    return render_template(
        "chatbot.html",
        subjects=get_subjects(),
        current_subject=subject,
    )


# --- AUTH API (JSON) -------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def api_login():
    return login()


@app.route("/api/register/start", methods=["POST"])
def api_register_start():
    return register_start()


@app.route("/api/register/verify", methods=["POST"])
def api_register_verify():
    return register_verify()


@app.route("/api/forgot/start", methods=["POST"])
def api_forgot_start():
    return forgot_start()


@app.route("/api/forgot/verify", methods=["POST"])
def api_forgot_verify():
    return forgot_verify()


@app.route("/api/otp/resend", methods=["POST"])
def api_otp_resend():
    return otp_resend()


@app.route("/api/health")
def api_health():
    return jsonify({
        "ok": True,
        "db": db.connection_status(),
        "using_mongo": db.is_using_mongo(),
    })


# --- QUIZ submit ------------------------------------------------------------

@app.route("/submit/<subject_slug>", methods=["POST"])
def submit_quiz(subject_slug):
    data_path = os.path.join("static", "data", f"{subject_slug}.json")
    if not os.path.exists(data_path):
        return jsonify({"error": "Không tìm thấy đề!"}), 404
    with open(data_path, encoding="utf-8") as f:
        questions = json.load(f)
    req_data = request.get_json(silent=True) or {}
    user_answers = []
    if isinstance(req_data, dict):
        for q in questions:
            user_answers.append(req_data.get(str(q.get("id")), ""))
    else:
        user_answers = req_data
    return jsonify(score_answers(questions, user_answers))


# --- Chatbot API (frontend-only stub, backend sẽ thêm sau) -----------------

@app.route("/api/chatbot/ask", methods=["POST"])
def api_chatbot_ask():
    """Stub - backend AI sẽ được người dùng tự cài đặt sau."""
    data = request.get_json(silent=True) or {}
    return jsonify({
        "ok": True,
        "answer": "[Stub] Tính năng AI sẽ được kích hoạt sau khi cấu hình backend. "
                  "Câu hỏi của bạn đã được nhận: " + (data.get("question") or "")[:200],
        "sources": [],
    })


# --- Legacy routes (giữ lại cho tương thích cũ) ----------------------------

@app.route("/login", methods=["POST"])
def login_legacy():
    return login()


@app.route("/register", methods=["POST"])
def register_legacy():
    return register_start()


if __name__ == "__main__":
    app.run(debug=True)

from flask import session, redirect, url_for, render_template, make_response, abort, request, jsonify
import json, os

# Danh sách môn học - icon đã chuẩn hoá theo Font Awesome 6 (fa-solid / fa-brands)
subjects = [
    {"name": "Toán Rời Rạc Và Ứng Dụng", "slug": "mth254",
     "icon": "fa-solid fa-calculator", "group": "Toán",
     "desc": "Logic, tập hợp, đồ thị, tổ hợp"},
    {"name": "Kinh Tế Chính Trị Mác-Lênin", "slug": "pos151",
     "icon": "fa-solid fa-scroll", "group": "Đại cương",
     "desc": "Học thuyết kinh tế chính trị"},
    {"name": "Tư Tưởng Hồ Chí Minh", "slug": "pos361",
     "icon": "fa-solid fa-brain", "group": "Đại cương",
     "desc": "Hệ thống tư tưởng HCM"},
    {"name": "Xử Lí Tín Hiệu Số", "slug": "ee304",
     "icon": "fa-solid fa-chart-line", "group": "Kỹ thuật",
     "desc": "DSP, biến đổi Fourier, FIR/IIR"},
    {"name": "Probability Theory & Statistical Inference", "slug": "sta285",
     "icon": "fa-solid fa-chart-area", "group": "Toán",
     "desc": "Xác suất, quá trình ngẫu nhiên"},
    {"name": "Linear Algebra for Data Science", "slug": "mth383",
     "icon": "fa-solid fa-divide", "group": "Toán",
     "desc": "Đại số tuyến tính cho DS"},
    {"name": "Cơ Sở Dữ Liệu", "slug": "is301",
     "icon": "fa-solid fa-database", "group": "Tin học",
     "desc": "ER, SQL, chuẩn hoá"},
    {"name": "Hệ Điều Hành Linux", "slug": "cs226",
     "icon": "fa-brands fa-linux", "group": "Tin học",
     "desc": "Shell, quản trị Linux"},
    {"name": "Cấu Trúc Dữ Liệu Và Giải Thuật", "slug": "cs316",
     "icon": "fa-solid fa-sitemap", "group": "Tin học",
     "desc": "DSA: stack, queue, tree, graph"},
    {"name": "Triết Học Mác - Lênin", "slug": "phi150",
     "icon": "fa-solid fa-university", "group": "Đại cương",
     "desc": "Triết học Mác - Lênin"},
    {"name": "Nền tảng hệ thống máy tính", "slug": "cr250",
     "icon": "fa-solid fa-microchip", "group": "Tin học",
     "desc": "Kiến trúc máy tính"},
    {"name": "Lập trình ứng dụng NET", "slug": "cs464",
     "icon": "fa-brands fa-windows", "group": "Tin học",
     "desc": "C#, .NET, WinForms/WPF"},
    {"name": "Phân tích và thiết kế hệ thống", "slug": "cs303",
     "icon": "fa-solid fa-diagram-project", "group": "Tin học",
     "desc": "UML, OOAD"},
    {"name": "Perl & Python", "slug": "cs466",
     "icon": "fa-brands fa-python", "group": "Tin học",
     "desc": "Scripting language"},
    {"name": "Hệ Quản Trị Cơ Sở Dữ Liệu", "slug": "is401",
     "icon": "fa-solid fa-server", "group": "Tin học",
     "desc": "DBMS, truy vấn, tối ưu"},
    {"name": "Lịch Sử Đảng Cộng Sản Việt Nam", "slug": "his362",
     "icon": "fa-solid fa-landmark", "group": "Đại cương",
     "desc": "Lịch sử Đảng CSVN"},
    {"name": "Mạng Máy Tính", "slug": "cs252",
     "icon": "fa-solid fa-network-wired", "group": "Tin học",
     "desc": "TCP/IP, mô hình OSI"},
    {"name": "Công Nghệ Phần Mềm", "slug": "cs403",
     "icon": "fa-solid fa-laptop-code", "group": "Tin học",
     "desc": "SDLC, đặc tả, kiểm thử"},
    {"name": "Deep Learning Cơ Bản", "slug": "ds371",
     "icon": "fa-solid fa-robot", "group": "Tin học",
     "desc": "Perceptron, CNN, RNN, LSTM"},
]


def nocache_response(resp):
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def get_subjects():
    return subjects


def get_subject(slug):
    return next((s for s in subjects if s["slug"] == slug), None)


def dashboard_route():
    resp = make_response(render_template("dashboard.html", subjects=subjects))
    return nocache_response(resp)


def logout():
    session.pop("username", None)
    session.pop("email", None)
    return redirect(url_for("auth"))


def quiz(subject_slug):
    subject = get_subject(subject_slug)
    if not subject:
        abort(404, "Không tìm thấy môn học!")
    json_url = url_for("static", filename=f"data/{subject_slug}.json")
    submit_url = url_for("submit_quiz", subject_slug=subject_slug)
    resp = make_response(
        render_template(
            "quiz-form.html",
            subject_name=subject["name"],
            subject_slug=subject_slug,
            subject_icon=subject.get("icon", "fa-solid fa-book"),
            json_url=json_url,
            submit_url=submit_url,
        )
    )
    return nocache_response(resp)


def subject_detail(subject_slug):
    return quiz(subject_slug)


# ============ CHẤM ĐIỂM ============

def _ans_set(value):
    """Chuẩn hoá đáp án thành tập hợp các ký tự A/B/... để hỗ trợ multi-answer."""
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(v).strip().upper() for v in value if str(v).strip()}
    s = str(value).strip()
    if not s:
        return set()
    # Cho phép "A,B" hoặc "A B" hoặc "AB"
    if "," in s or " " in s:
        return {p.strip().upper() for p in re.split(r"[,\s]+", s) if p.strip()}
    if len(s) > 1 and all(c.upper() in "ABCDEFGH" for c in s):
        return {c.upper() for c in s}
    return {s.upper()}


import re  # noqa: E402


def score_answers(questions, user_answers):
    correct = 0
    details = []
    for q, ua in zip(questions, user_answers):
        qtype = q.get("type", "mcq")
        is_correct = False
        expected_raw = q.get("ans", q.get("a", q.get("answer")))

        if qtype == "mcq":
            correct_set = _ans_set(expected_raw)
            user_set = _ans_set(ua)
            is_correct = bool(correct_set) and correct_set == user_set
            expected_display = ", ".join(sorted(correct_set)) if correct_set else "---"
        elif qtype == "short":
            def normalizeVN(s):
                import unicodedata as _u
                if not s:
                    return ""
                s = _u.normalize("NFD", s)
                s = re.sub(r"[\u0300-\u036f]", "", s)
                s = re.sub(r'[.,?!;:()\[\]{}"\' ]+', " ", s)
                return s.lower().strip()

            kws = q.get("keywords") or []
            if not kws:
                is_correct = False
            else:
                ua_norm = normalizeVN(str(ua or ""))
                matched = sum(1 for kw in kws if normalizeVN(kw) in ua_norm)
                is_correct = matched / len(kws) >= 0.8
            expected_display = ", ".join(kws)
        else:
            expected_display = "---"

        if is_correct:
            correct += 1
        details.append({
            "question": q.get("q", q.get("question", "")),
            "user_answer": ua,
            "expected": expected_display,
            "correct": is_correct,
        })

    total = max(1, len(questions))
    score = round(correct / total * 100)
    return {"score": score, "correct": correct, "total": len(questions), "details": details}


from flask import Blueprint  # noqa: E402

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/submit/<subject_slug>", methods=["POST"])
def submit_quiz(subject_slug):
    data_path = os.path.join("static", "data", f"{subject_slug}.json")
    if not os.path.exists(data_path):
        return jsonify({"error": "Không tìm thấy đề!"}), 404
    with open(data_path, encoding="utf-8") as f:
        questions = json.load(f)
    req_data = request.json or {}
    user_answers = []
    if isinstance(req_data, dict):
        for q in questions:
            user_answers.append(req_data.get(str(q.get("id")), ""))
    else:
        user_answers = req_data
    return jsonify(score_answers(questions, user_answers))

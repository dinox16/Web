from flask import session, redirect, url_for, render_template, make_response, abort, request, jsonify
import json, os

subjects = [
    {"name": "Toán Rời Rạc Và Ứng Dụng", "slug": "mth254", "icon": "fa-solid fa-calculator"},
    {"name": "Kinh Tế Chính Trị Mác-Lênin", "slug": "pos151", "icon": "fa-solid fa-scroll"},
    {"name": "Tư Tưởng Hồ Chí Minh", "slug": "pos361", "icon": "fa-solid fa-brain"},
    {"name": "Xử Lí Tín Hiệu Số", "slug": "ee304", "icon": "fa-solid fa-chart-line"},
    {"name": "Probability Theory, Random Processes and Statistical Inference", "slug": "sta285", "icon": "fa-solid fa-chart-area"},
    {"name": "Linear Algebra for Data Science", "slug": "mth383", "icon": "fa-solid fa-divide"},
    {"name": "Cơ Sở Dữ Liệu", "slug": "is301", "icon": "fa-solid fa-database"},
    {"name": "Hệ Điều Hành Linux", "slug": "cs226", "icon": "fa-brands fa-linux"},
    {"name": "Cấu Trúc Dữ Liệu Và Giải Thuật", "slug": "cs316", "icon": "fas fa-sitemap"},
    {"name": "Triết Học Mác - Lênin", "slug" : "phi150", "icon": "fas fa-university"},
    {"name": "Nền tảng hệ thống máy tính", "slug": "cr250", "icon": "fa-solid fa-microchip"},
    {"name":"Lập trình ứng dụng NET", "slug": "cs464", "icon": "fa-brands fa-windows"},
    {"name":"Phân tích và thiết kế hệ thống", "slug": "cs303", "icon": "fa-solid fa-project-diagram"},
]

def nocache_response(resp):
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

def dashboard_route():
    resp = make_response(render_template('dashboard.html', subjects=subjects))
    return nocache_response(resp)

def logout():
    session.pop('username', None)
    return redirect(url_for('auth'))

def quiz(subject_slug):
    subject = next((s for s in subjects if s["slug"] == subject_slug), None)
    if not subject:
        abort(404, "Không tìm thấy môn học!")
    json_url = url_for('static', filename=f'data/{subject_slug}.json')
    submit_url = url_for('submit_quiz', subject_slug=subject_slug)
    resp = make_response(render_template(
        "quiz-form.html",
        subject_name=subject["name"],
        subject_slug=subject_slug,
        json_url=json_url,           # dữ liệu câu hỏi
        submit_url=submit_url        # endpoint nộp bài
    ))
    return nocache_response(resp)

def subject_detail(subject_slug):
    return quiz(subject_slug)

# Đáp án và chấm điểm sẽ xử lý tại đây
def score_answers(questions, user_answers):
    correct = 0
    details = []
    for q, ua in zip(questions, user_answers):
        if q.get("type") == "mcq":
            is_correct = ua == (q.get("ans") or q.get("a"))
            expected = q.get("ans") or q.get("a")
        elif q.get("type") == "short":
            # Đơn giản hóa: giống như JS logic normalizeVN và kiểm tra keywords
            def normalizeVN(str):
                import unicodedata, re
                if not str: return ""
                str = unicodedata.normalize('NFD', str)
                str = re.sub(r'[\u0300-\u036f]', '', str)
                str = re.sub(r'[.,?!;:()\[\]{}"\' ]+', ' ', str)
                return str.lower().strip()
            if not q.get("keywords"): is_correct = False
            else:
                matched = sum(normalizeVN(kw) in normalizeVN(ua) for kw in q.get("keywords"))
                is_correct = matched / len(q["keywords"]) >= 0.8
            expected = ", ".join(q.get("keywords", []))
        else:
            is_correct = False
            expected = "---"

        if is_correct: correct += 1
        details.append({
            "question": q.get("q", ""),
            "user_answer": ua,
            "expected": expected,
            "correct": is_correct
        })
    score = round(correct / len(questions) * 100)
    return {"score": score, "correct": correct, "total": len(questions), "details": details}

from flask import Blueprint
quiz_bp = Blueprint('quiz', __name__)

@quiz_bp.route('/submit/<subject_slug>', methods=['POST'])
def submit_quiz(subject_slug):
    # Xác định file data
    data_path = os.path.join('static', 'data', f'{subject_slug}.json')
    if not os.path.exists(data_path):
        return jsonify({"error": "Không tìm thấy đề!"}), 404
    questions = json.load(open(data_path, encoding="utf-8"))
    req_data = request.json
    # userAnswers gửi lên là list hoặc dict {id:ans}
    user_answers = []
    # Nếu dạng dict thì map theo id, nếu list thì theo thứ tự
    if isinstance(req_data, dict):
        for q in questions:
            user_answers.append(req_data.get(str(q.get('id')), ""))
    else:
        user_answers = req_data
    result = score_answers(questions, user_answers)
    return jsonify(result)
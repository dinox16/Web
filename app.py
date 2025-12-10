import os
import re
import json
from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, session, redirect, url_for, jsonify
)
from back.funclogin import login, register
from back.funcdash import dashboard_route, logout, quiz, subject_detail

# --- Quiz grading logic START ---
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_short_answer_correct(user_answer, keywords):
    answer = normalize(user_answer)
    match_count = sum(1 for kw in keywords if kw in answer)
    return match_count / len(keywords) >= 0.8 if keywords else False

def grade_quiz(questions, user_answers):
    results = []

    for q in questions:
        qid = q.get("id")
        qtype = q.get("type")
        question_text = q.get("question", "N/A")

        if not qid or not qtype:
            continue 

        user_ans = user_answers.get(qid, "")
        is_correct = False

        if qtype == "mcq":
            correct_ans = q.get("answer", q.get("ans"))
            is_correct = user_ans == correct_ans
        elif qtype == "short":
            is_correct = is_short_answer_correct(user_ans, q.get("keywords", []))

        results.append({
                    "id": qid,
                    "type": q.get("type", "unknown"),
                    "question": q.get("question", q.get("q", "Câu hỏi không rõ")),
                    "correct": is_correct,
                    "user_answer": user_ans,
                    "expected": q.get("answer", q.get("ans", "---"))
                })


    return results


def submit_quiz_route(quiz_json_path):
    user_answers = request.json
    with open(quiz_json_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    result = grade_quiz(questions, user_answers)
    return jsonify(result)

def quiz_page_route(quiz_json_path):
    with open(quiz_json_path, 'r', encoding='utf-8') as f:
        questions = json.load(f)
    return render_template("quiz.html", questions=questions)
# --- Quiz grading logic END ---

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here')

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/', methods=['GET'])
def home():
    if 'username' not in session:
        return redirect(url_for('auth'))
    return redirect(url_for('dashboard'))

@app.route('/auth', methods=['GET'])
def auth():
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login_route():
    return login()

@app.route('/register', methods=['POST'])
def register_route():
    return register()

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('auth'))
    return dashboard_route()

@app.route('/logout')
def logout_route():
    return logout()

@app.route('/quiz/<subject_slug>')
def quiz_dashboard(subject_slug):
    if 'username' not in session:
        return redirect(url_for('auth'))
    return quiz(subject_slug)

@app.route('/subject/<subject_slug>')
def subject_detail_route(subject_slug):
    if 'username' not in session:
        return redirect(url_for('auth'))
    return subject_detail(subject_slug)

@app.route("/quizpage/<subject_slug>")
def quiz_page(subject_slug):
    return quiz_page_route(f"data/{subject_slug}.json")

@app.route("/submit/<subject_slug>", methods=["POST"])
def submit_quiz(subject_slug):
    return submit_quiz_route(f"static/data/{subject_slug}.json")

# If you want a route that serves the quiz HTML and passes the .json and submit URL to JS:
@app.route('/quizview/<subject_slug>')
def quiz_route(subject_slug):
    json_path = f"data/{subject_slug}.json"
    return render_template(
        "quiz.html",
        subject_name=subject_slug.upper(),
        json_url=url_for('static', filename=f'json/{subject_slug}.json'),
        submit_url=url_for('submit_quiz', subject_slug=subject_slug)
    )

if __name__ == '__main__':
    app.run(debug=True)
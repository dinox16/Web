import re
import json
from flask import request, jsonify, render_template


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
    correct_count = 0
    results = []

    for q in questions:
        qid = q["id"]
        user_ans = user_answers.get(qid, "")
        is_correct = False

        if q["type"] == "mcq":
            is_correct = user_ans == q["answer"]
        elif q["type"] == "short":
            is_correct = is_short_answer_correct(user_ans, q.get("keywords", []))

        results.append({
            "id": qid,
            "type": q["type"],
            "question": q["question"],
            "correct": is_correct,
            "user_answer": user_ans,
            "expected": q.get("answer")
        })

        if is_correct:
            correct_count += 1

    score = round((correct_count / len(questions)) * 100, 2)
    return {"score": score, "total": len(questions), "correct": correct_count, "details": results}

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

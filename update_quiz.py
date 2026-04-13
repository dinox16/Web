import json

# Các câu trả lời đúng cho mỗi câu hỏi
answers = {
    1: "A", 2: "B", 3: "A", 4: "A", 5: "B", 6: "D", 7: "A", 8: "C", 9: "C", 10: "D",
    11: "A", 12: "D", 13: "C", 14: "A", 15: "D", 16: "B", 17: "A", 18: "A", 19: "A", 20: "B",
    21: "B", 22: "D", 23: "D", 24: "A", 25: "D", 26: "A", 27: "C", 28: "D", 29: "A", 30: "B",
    31: "C", 32: "B", 33: "C", 34: "D", 35: "C", 36: "C", 37: "C", 38: "D", 39: "D", 40: "C",
    41: "D", 42: "B", 43: "A", 44: "B", 45: "C", 46: "D", 47: "B", 48: "D", 49: "A", 50: "A",
    51: "D", 52: "B", 53: "A", 54: "C", 55: "D", 56: "B", 57: "A", 58: "D", 59: "D", 60: "C",
    61: "C", 62: "D", 63: "D", 64: "A", 65: "B", 66: "C", 67: "C", 68: "A", 69: "B", 70: "D",
    71: "C", 72: "D", 73: "C", 74: "D", 75: "A", 76: "D", 77: "C", 78: "D", 79: "C", 80: "B",
    81: "B", 82: "A", 83: "C", 84: "A", 85: "D", 86: "B", 87: "A", 88: "C", 89: "B", 90: "C",
    91: "B", 92: "B", 93: "A", 94: "D", 95: "D", 96: "D", 97: "D", 98: "A", 99: "A"
}

# Đọc file quiz.json
with open("quiz.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)

# Cập nhật các câu trả lời
for item in quiz_data:
    item_id = item["id"]
    if item_id in answers:
        item["ans"] = answers[item_id]

# Ghi lại file
with open("quiz.json", "w", encoding="utf-8") as f:
    json.dump(quiz_data, f, ensure_ascii=False, indent=2)

print("✓ Đã cập nhật tất cả 99 câu trả lời thành công!")

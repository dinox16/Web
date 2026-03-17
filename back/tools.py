"""
DOCX -> JSON Quiz (2 mode: default / inline / auto)
- default: "Câu 1: ..." và options A/B/C/D thường nằm ở các dòng riêng.
- inline: cả câu + A/B/C/D nằm chung 1 paragraph (như ảnh). Có thể bắt đầu bằng "1." hoặc "Câu 1:".

Đáp án đúng = option có phần chữ in đậm (bold).

Cài:
  pip install python-docx

Chạy:
  python docx_to_quiz_2mode.py input.docx --mode auto -o quiz.json --pretty
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from docx import Document


# ---------- Helpers ----------
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def is_blank(s: str) -> bool:
    return not norm(s)


# Nhận diện bắt đầu câu hỏi:
# - "Câu 1:" / "Câu 1." / "Câu 1 -"
# - "1." / "1)" / "1 -"
RE_Q_PREFIX = re.compile(r"^\s*(?:Câu\s*)?(\d+)\s*([.)\:\-–])\s*", re.IGNORECASE)

# Nhận diện option dạng dòng riêng
RE_OPT_LINE = re.compile(r"^\s*([A-Da-d])\s*([.)\:\-–])\s*(.+?)\s*$")

# Tách option trong 1 dòng inline: tìm các mốc "A." "B." "C." "D."
RE_OPT_MARK = re.compile(r"\b([A-D])\s*([.)\:\-–])\s*", re.IGNORECASE)


@dataclass
class RunSpan:
    start: int
    end: int
    bold: bool


def paragraph_spans(paragraph) -> Tuple[str, List[RunSpan]]:
    """
    Build a plain text string + spans mapping run index ranges into that text,
    preserving concatenation order, so we can locate bold positions.
    """
    parts: List[str] = []
    spans: List[RunSpan] = []
    pos = 0
    for run in paragraph.runs:
        t = run.text or ""
        if not t:
            continue
        parts.append(t)
        start = pos
        pos += len(t)
        spans.append(RunSpan(start=start, end=pos, bold=bool(run.bold)))
    text = "".join(parts)
    return text, spans


def any_bold_in_range(spans: List[RunSpan], start: int, end: int) -> bool:
    for sp in spans:
        if sp.end <= start:
            continue
        if sp.start >= end:
            break
        if sp.bold:
            return True
    return False


# ---------- Mode: default (multi-line) ----------
def parse_default(doc: Document) -> List[Dict]:
    quiz: List[Dict] = []
    current: Optional[Dict] = None
    in_options = False

    def finalize():
        nonlocal current, in_options
        if not current:
            return
        # ensure keys
        current.setdefault("opts", {})
        for k in ["A", "B", "C", "D"]:
            current["opts"].setdefault(k, "")
        opt_count = sum(1 for k in ["A", "B", "C", "D"] if norm(current["opts"][k]))
        if norm(current.get("q", "")) and opt_count >= 2:
            quiz.append(current)
        current = None
        in_options = False

    for p in doc.paragraphs:
        line = norm(p.text)
        if not line:
            continue

        # start new question
        m = RE_Q_PREFIX.match(line)
        if m:
            finalize()
            # remove prefix
            q_text = norm(line[m.end():])
            current = {
                "id": 0,
                "q": q_text or line,
                "opts": {"A": "", "B": "", "C": "", "D": ""},
                "ans": "",
                "type": "mcq",
            }
            in_options = False
            continue

        if current is None:
            # fallback: treat as question
            current = {
                "id": 0,
                "q": line,
                "opts": {"A": "", "B": "", "C": "", "D": ""},
                "ans": "",
                "type": "mcq",
            }
            in_options = False
            continue

        # option line
        om = RE_OPT_LINE.match(line)
        if om:
            in_options = True
            key = om.group(1).upper()
            text = norm(om.group(3))
            current["opts"][key] = text

            # answer: if any bold run in this paragraph -> that option correct
            # (đúng với format options nằm riêng từng dòng)
            if any(r.bold and norm(r.text) for r in p.runs):
                current["ans"] = key
            continue

        # continuation line
        if not in_options:
            current["q"] = norm(current["q"] + " " + line)
        else:
            # append to last option if exists
            last_key = None
            for k in ["D", "C", "B", "A"]:
                if norm(current["opts"][k]):
                    last_key = k
                    break
            if last_key:
                current["opts"][last_key] = norm(current["opts"][last_key] + " " + line)
                if any(r.bold and norm(r.text) for r in p.runs) and not current.get("ans"):
                    current["ans"] = last_key
            else:
                current["q"] = norm(current["q"] + " " + line)

    finalize()

    for i, item in enumerate(quiz, start=1):
        item["id"] = i
    return quiz


# ---------- Mode: inline (single paragraph has q + options) ----------
def split_inline_question_and_options(text: str) -> Optional[Tuple[str, Dict[str, str], Dict[str, Tuple[int, int]]]]:
    """
    Given a paragraph text (already includes q + options),
    returns:
      q_text,
      opts dict,
      opt_ranges: per key -> (start,end) in original 'text' indices
    Uses option markers A/B/C/D to split.
    """
    # Find all option markers
    matches = list(RE_OPT_MARK.finditer(text))
    if len(matches) < 2:
        return None

    # Build segments by marker positions
    # Example: "... D. xxx"
    segments = []
    for i, m in enumerate(matches):
        key = m.group(1).upper()
        start = m.start()
        content_start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segments.append((key, start, content_start, end))

    # require at least A,B and one more; ideally A-D
    keys = [k for (k, *_rest) in segments]
    if "A" not in keys or "B" not in keys:
        return None

    q_text = norm(text[:segments[0][1]])
    opts: Dict[str, str] = {"A": "", "B": "", "C": "", "D": ""}
    ranges: Dict[str, Tuple[int, int]] = {}

    for key, start, content_start, end in segments:
        # option content is between content_start and end
        opt_text = norm(text[content_start:end])
        if key in opts:
            opts[key] = opt_text
            ranges[key] = (start, end)

    # must have at least 2 options
    opt_count = sum(1 for k in ["A", "B", "C", "D"] if norm(opts[k]))
    if not q_text or opt_count < 2:
        return None

    return q_text, opts, ranges


def parse_inline(doc: Document) -> List[Dict]:
    quiz: List[Dict] = []

    for p in doc.paragraphs:
        raw_text, spans = paragraph_spans(p)
        text = norm(raw_text)
        if not text:
            continue

        # remove leading "1." or "Câu 1:" prefix if present (nhưng vẫn cho phép nếu không có)
        m = RE_Q_PREFIX.match(text)
        if m:
            # mapping spans is on raw_text, but norm() changed spaces => index mismatch.
            # To keep it reliable, we will work on raw_text (not normalized) for range detection,
            # and do only light strip for prefix on raw_text.
            raw = raw_text
            m2 = RE_Q_PREFIX.match(raw)
            if m2:
                raw_wo_prefix = raw[m2.end():]
                # But splitting options needs positions in raw string
                split = split_inline_question_and_options(raw_wo_prefix)
                if not split:
                    # try splitting without prefix removal (fallback)
                    split = split_inline_question_and_options(raw)
                    if not split:
                        continue
                    q_text, opts, opt_ranges = split
                    prefix_offset = 0
                else:
                    q_text, opts, opt_ranges = split
                    prefix_offset = m2.end()
            else:
                # fallback raw
                split = split_inline_question_and_options(raw_text)
                if not split:
                    continue
                q_text, opts, opt_ranges = split
                prefix_offset = 0
        else:
            raw = raw_text
            split = split_inline_question_and_options(raw)
            if not split:
                continue
            q_text, opts, opt_ranges = split
            prefix_offset = 0

        # Determine answer by checking bold spans within each option's range
        ans = ""
        for key in ["A", "B", "C", "D"]:
            if key not in opt_ranges:
                continue
            start, end = opt_ranges[key]
            # adjust if we removed prefix in raw_wo_prefix
            start += prefix_offset
            end += prefix_offset
            if any_bold_in_range(spans, start, end):
                ans = key
                break

        quiz.append(
            {
                "id": 0,
                "q": norm(q_text),
                "opts": {k: norm(v) for k, v in opts.items()},
                "ans": ans,
                "type": "mcq",
            }
        )

    # set id int 1..n
    out = []
    for i, item in enumerate(quiz, start=1):
        item["id"] = i
        out.append(item)
    return out


# ---------- Auto mode ----------
def detect_mode(doc: Document) -> str:
    """
    Heuristic:
    - If many paragraphs contain A./B./C./D in same line -> inline
    - Else -> default
    """
    inline_hits = 0
    optline_hits = 0
    checked = 0

    for p in doc.paragraphs:
        t = norm(p.text)
        if not t:
            continue
        checked += 1
        if split_inline_question_and_options(t):
            inline_hits += 1
        if RE_OPT_LINE.match(t):
            optline_hits += 1
        if checked >= 50:
            break

    if inline_hits >= 2 and inline_hits >= optline_hits:
        return "inline"
    return "default"


def docx_to_quiz(docx_path: str, mode: str) -> List[Dict]:
    doc = Document(docx_path)
    if mode == "auto":
        mode = detect_mode(doc)

    if mode == "default":
        return parse_default(doc)
    if mode == "inline":
        return parse_inline(doc)

    raise ValueError("mode must be one of: default, inline, auto")


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Scan DOCX -> JSON quiz (2 mode).")
    ap.add_argument("input", help="Đường dẫn file .docx")
    ap.add_argument("--mode", choices=["default", "inline", "auto"], default="auto")
    ap.add_argument("-o", "--output", default="", help="File output .json (mặc định: stdout)")
    ap.add_argument("--pretty", action="store_true", help="In JSON đẹp (indent=2, UTF-8)")
    args = ap.parse_args()

    quiz = docx_to_quiz(args.input, args.mode)

    s = json.dumps(quiz, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(s)
    else:
        print(s)


if __name__ == "__main__":
    main()
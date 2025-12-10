/* Updated quiz script with:
   - "Làm lại" button: reloads random questions (calls loadQuestions)
   - "Quay về Dashboard" button: navigates to DASHBOARD_URL if defined, otherwise '/dashboard'
   - Buttons are shown after finishing the quiz (score view)
   - Retry restores quiz UI and resets state via loadQuestions()
*/

let questions = [];
let current = 0;
let userAnswers = [];
let quizDone = false;

function getRandomItems(arr, n) {
    let result = [];
    let used = new Set();
    while (result.length < n && result.length < arr.length) {
        let i = Math.floor(Math.random() * arr.length);
        if (!used.has(i)) {
            result.push(arr[i]);
            used.add(i);
        }
    }
    return result;
}

function goToQuestionById(id) {
    const index = questions.findIndex(q => q.id == id);
    if (index !== -1) {
        current = index;
        renderQuestion();
    } else {
        showDialog(`Không tìm thấy câu hỏi với id: ${id}`);
    }
}

function normalizeVN(str) {
    if (!str) return "";
    return str
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[.,?!;:()\[\]{}"']/g, '')
        .replace(/\s+/g, ' ')
        .toLowerCase()
        .trim();
}

function isShortAnswerCorrect(question, userAnswer) {
    if (!question.keywords || !Array.isArray(question.keywords)) return false;
    const answerNorm = normalizeVN(userAnswer);
    let matched = 0;
    for (let kw of question.keywords) {
        const kwNorm = normalizeVN(kw);
        if (answerNorm.includes(kwNorm)) matched++;
    }
    return matched / question.keywords.length >= 0.8;
}

async function loadQuestions() {
    const res = await fetch(QUESTIONS_URL);
    const allQuestions = await res.json();
    const mcqList = allQuestions.filter(q => q.type === "mcq");
    const shortList = allQuestions.filter(q => q.type === "short");

    const mcqs = getRandomItems(mcqList, 10);
    const shorts = getRandomItems(shortList, 5);

    questions = [...mcqs, ...shorts];
    current = 0;
    userAnswers = [];
    quizDone = false;

    // restore UI if previously hidden
    const qa = document.querySelector('.question-area');
    if (qa) qa.style.display = "";
    const nav = document.querySelector('.navigation');
    if (nav) nav.style.display = "";
    const pb = document.querySelector('.progress-bar');
    if (pb) pb.style.display = "";

    renderQuestion();
    updateProgress();
}

function showDialog(message) {
    const el = document.getElementById('dialog-message');
    if (el) el.textContent = message;
    const dialog = document.getElementById('dialog');
    if (dialog) dialog.style.display = 'flex';
}
const dialogCloseBtn = document.getElementById('dialog-close');
if (dialogCloseBtn) {
    dialogCloseBtn.onclick = function() {
        const dialog = document.getElementById('dialog');
        if (dialog) dialog.style.display = 'none';
    };
}

function renderQuestion() {
    if (!questions.length) return;

    const q = questions[current];
    const questionArea = document.querySelector('.question-area');
    let inputHtml = "";
    let imageHtml = "";

    if (q.img) {
        imageHtml = `<div class="question-img">
            <img src="${q.img}" alt="Hình minh họa" style="max-width: 100%; height: auto; margin: 10px 0;">
        </div>`;
    }

    if (q.type === "short") {
        let prev = userAnswers[current] || "";
        inputHtml = `
            <div class="short-answer">
                <input type="text" id="short-answer" placeholder="Nhập câu trả lời..." value="${prev}" autocomplete="off">
            </div>
        `;

        questionArea.innerHTML = `
            <div class="question-number">Câu hỏi ${current + 1} / ${questions.length}</div>
            <div class="question-text">${q.q}</div>
            ${imageHtml}
            ${inputHtml}
        `;

        const sa = document.getElementById('short-answer');
        if (sa) {
            sa.oninput = function () {
                userAnswers[current] = this.value;
            };
        }

    } else {
        let opts = q.opts || q.op;
        let optsHtml = '';
        for (const [key, value] of Object.entries(opts)) {
            optsHtml += `
                <button class="option" data-opt="${key}">
                    <span class="opt-key">${key}.</span> ${value}
                </button>`;
        }

        questionArea.innerHTML = `
            <div class="question-number">Câu hỏi ${current + 1} / ${questions.length}</div>
            <div class="question-text">${q.q}</div>
            ${imageHtml}
            <div class="options">${optsHtml}</div>
        `;

        const userAns = userAnswers[current];
        const correct = q.ans || q.a;

        document.querySelectorAll('.option').forEach(btn => {
            const optKey = btn.dataset.opt;
            btn.disabled = false;

            if (typeof userAns !== "undefined") {
                btn.disabled = true;
                if (optKey === correct) {
                    btn.classList.add('correct');
                }
                if (optKey === userAns) {
                    if (optKey === correct) {
                        btn.classList.add('correct');
                    } else {
                        btn.classList.add('incorrect');
                    }
                }
            } else {
                btn.onclick = () => selectOption(btn, btn.dataset.opt);
            }
        });
    }

    updateProgress();
    updateNav();
}

function selectOption(btn, opt) {
    if (quizDone) return;
    const q = questions[current];
    if (q.type !== "mcq") return;
    if (typeof userAnswers[current] !== "undefined") return;

    userAnswers[current] = opt;
    const correct = q.ans || q.a;

    document.querySelectorAll('.option').forEach(b => {
        const bOpt = b.dataset.opt;
        b.classList.remove('selected', 'correct', 'incorrect');
        b.disabled = true;

        if (bOpt === correct) {
            b.classList.add('correct');
        }
        if (bOpt === opt) {
            b.classList.add(opt === correct ? 'correct' : 'incorrect');
        }
    });
}

function updateNav() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.textContent = current === questions.length - 1 ? "Nộp bài" : "Tiếp";
}

function updateProgress() {
    const progress = document.querySelector('.progress');
    if (progress) progress.style.width = ((current + 1) / questions.length * 100) + "%";
}

const prevBtn = document.getElementById('prevBtn');
if (prevBtn) {
    prevBtn.onclick = () => {
        if (current > 0) {
            current--;
            renderQuestion();
        }
    };
}

const nextBtn = document.getElementById('nextBtn');
if (nextBtn) {
    nextBtn.onclick = () => {
        if (quizDone) return;
        const q = questions[current];
        if (q.type === "short") {
            if (!userAnswers[current] || userAnswers[current].trim() === "") {
                showDialog("Bạn hãy nhập câu trả lời trước khi tiếp tục!");
                return;
            }
        } else if (q.type === "mcq") {
            if (typeof userAnswers[current] === "undefined") {
                showDialog("Bạn hãy chọn đáp án trước khi tiếp tục!");
                return;
            }
        }
        if (current === questions.length - 1) {
            finishQuiz();
        } else {
            current++;
            renderQuestion();
        }
    };
}

function convertAnswersToDict() {
    // Chuyển userAnswers sang dạng {id:ans} để gửi về backend
    let dict = {};
    questions.forEach((q, idx) => {
        dict[q.id] = userAnswers[idx];
    });
    return dict;
}

function computeLocalScoreOutOf100() {
    // Fallback scoring in case server doesn't return a score.
    // mcq: exact match. short: use isShortAnswerCorrect.
    let correct = 0;
    questions.forEach((q, idx) => {
        const ua = userAnswers[idx];
        if (q.type === "mcq") {
            const correctOpt = q.ans || q.a;
            if (ua && ua === correctOpt) correct++;
        } else if (q.type === "short") {
            if (ua && isShortAnswerCorrect(q, ua)) correct++;
        }
    });
    const total = questions.length;
    // score out of 100
    return Math.round((correct / total) * 100);
}

async function finishQuiz() {
    quizDone = true;

    try {
        const res = await fetch(SUBMIT_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(convertAnswersToDict())
        });

        let data;
        try {
            data = await res.json();
        } catch (e) {
            data = null;
        }

        // Determine scoreOutOf100 using server response or local fallback
        let scoreOutOf100 = null;
        if (data && typeof data.score === "number") {
            // assume server returned 0-100
            scoreOutOf100 = data.score;
        } else if (data && typeof data.correct === "number" && typeof data.total === "number") {
            scoreOutOf100 = Math.round((data.correct / data.total) * 100);
        } else {
            // fallback local scoring
            scoreOutOf100 = computeLocalScoreOutOf100();
        }

        // Convert to scale of 10, round to one decimal place
        let scoreOutOf10 = Math.round((scoreOutOf100 / 100) * 10 * 10) / 10;

        // Show only the score on scale of 10 + buttons for retry/dashboard
        const resultHTML = `
            <div class="final-score-box" style="text-align:center;padding:18px;">
                <h3>Kết quả</h3>
                <p style="font-size:1.5rem;margin:8px 0;"><b>Điểm:</b> ${scoreOutOf10} / 10</p>
                <div style="margin-top:14px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">
                    <button id="retryBtn" class="nav-btn" style="background:linear-gradient(180deg,var(--primary),var(--primary-700));">Làm lại</button>
                    <button id="backBtn" class="nav-btn" style="background:#657786;">Quay về Dashboard</button>
                </div>
            </div>
        `;

        const scoreArea = document.querySelector('.score-area');
        if (scoreArea) {
            scoreArea.innerHTML = resultHTML;
            scoreArea.style.display = "block";
        }

        // hide quiz UI
        const qa = document.querySelector('.question-area');
        if (qa) qa.style.display = "none";
        const nav = document.querySelector('.navigation');
        if (nav) nav.style.display = "none";
        const pb = document.querySelector('.progress-bar');
        if (pb) pb.style.display = "none";

        // attach button handlers (elements just created)
        const retryBtn = document.getElementById('retryBtn');
        if (retryBtn) {
            retryBtn.onclick = async function () {
                // Reset state and reload random questions
                quizDone = false;
                // Clear score area UI
                if (scoreArea) {
                    scoreArea.innerHTML = '';
                    scoreArea.style.display = "none";
                }
                // show quiz UI again
                if (qa) qa.style.display = "";
                if (nav) nav.style.display = "";
                if (pb) pb.style.display = "";

                // small delay so UI updates smoothly
                setTimeout(() => {
                    loadQuestions();
                }, 60);
            };
        }

        const backBtn = document.getElementById('backBtn');
        if (backBtn) {
            backBtn.onclick = function () {
                const dest = (typeof DASHBOARD_URL !== 'undefined' && DASHBOARD_URL) ? DASHBOARD_URL : '/dashboard';
                window.location.href = dest;
            };
        }

    } catch (err) {
        showDialog("Có lỗi khi nộp bài: " + (err && err.message ? err.message : err));
    }
}

window.onload = loadQuestions;
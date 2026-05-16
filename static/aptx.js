/* ============================================================
   QUIZ ENGINE
   - Load all questions
   - Support single & multi-answer MCQ (cs403.json)
     -> Multi-answer detected when q.ans is an Array
   - Question navigator sidebar
   - MCQ: đáp án xáo trộn thứ tự mỗi lần làm (chấm theo mã A/B/C)
   - Tiếp / Nộp: không bắt buộc trả lời trước — có thể bỏ qua
   - Score, retry, back to dashboard
   ============================================================ */

let questions = [];
let current = 0;
let userAnswers = [];   // for mcq: string for single, array for multi; for short: string
let quizDone = false;
/** Per-question shuffled [key, label][] for MCQ display (null for short). */
let mcqOptionOrder = [];

/* ============ utils ============ */
function escapeHtml(s) {
    return String(s ?? "")
        .replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function normalizeVN(str) {
    if (!str) return "";
    return String(str)
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .replace(/[.,?!;:()\[\]{}"']/g, "")
        .replace(/\s+/g, " ")
        .toLowerCase()
        .trim();
}

function isShortAnswerCorrect(question, userAnswer) {
    if (!question.keywords || !Array.isArray(question.keywords)) return false;
    const a = normalizeVN(userAnswer);
    let matched = 0;
    for (const kw of question.keywords) {
        if (a.includes(normalizeVN(kw))) matched++;
    }
    return matched / question.keywords.length >= 0.8;
}

function toPublicUrl(p) {
    if (!p) return "";
    let s = String(p).trim().replace(/\\/g, "/");
    if (s.startsWith("static/")) s = s.slice("static/".length);
    if (!s.startsWith("/")) s = "/" + s;
    return s;
}

/** Render question text replacing img[N] placeholders. */
function renderQuestionHtml(q) {
    const raw = String(q?.q ?? q?.question ?? "");
    const escaped = escapeHtml(raw);
    return escaped.replace(/img\[(\d+)\]/g, (_, nStr) => {
        const n = Number(nStr);
        const imgs = Array.isArray(q?.imgs) ? q.imgs : [];
        const src = imgs[n];
        if (!src) return `img[${n}]`;
        const url = toPublicUrl(src);
        return `<img class="inline-q-img" src="${escapeHtml(url)}" alt="img[${n}]" />`;
    });
}

/** Convert answer to canonical Set<string> (uppercase). */
function ansSet(value) {
    if (value === null || value === undefined) return new Set();
    if (Array.isArray(value)) {
        return new Set(value.map(v => String(v).trim().toUpperCase()).filter(Boolean));
    }
    const s = String(value).trim();
    if (!s) return new Set();
    if (s.includes(",") || s.includes(" ")) {
        return new Set(s.split(/[,\s]+/).map(p => p.trim().toUpperCase()).filter(Boolean));
    }
    // If string is "AB" treat as multi
    if (s.length > 1 && /^[A-H]+$/i.test(s)) {
        return new Set(s.toUpperCase().split(""));
    }
    return new Set([s.toUpperCase()]);
}

function isMultiAnswer(q) {
    return Array.isArray(q?.ans) || Array.isArray(q?.a);
}

function setsEqual(a, b) {
    if (a.size !== b.size) return false;
    for (const x of a) if (!b.has(x)) return false;
    return true;
}

function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
}

/** Randomize option order per question (new order each lần làm lại). Chấm điểm vẫn theo mã A/B/C. */
function buildMcqOptionOrder() {
    mcqOptionOrder = questions.map(q => {
        if (q.type === "short") return null;
        const opts = q.opts || q.op || {};
        const entries = Object.entries(opts);
        shuffleInPlace(entries);
        return entries;
    });
}

/* ============ dialog ============ */
function showDialog(message) {
    const el = document.getElementById("dialog-message");
    if (el) el.textContent = message;
    const dialog = document.getElementById("dialog");
    if (dialog) dialog.style.display = "flex";
}
const dialogCloseBtn = document.getElementById("dialog-close");
if (dialogCloseBtn) {
    dialogCloseBtn.onclick = () => {
        const dialog = document.getElementById("dialog");
        if (dialog) dialog.style.display = "none";
    };
}

/* ============ loaders ============ */
async function loadQuestions() {
    const res = await fetch(QUESTIONS_URL);
    const all = await res.json();
    questions = Array.isArray(all) ? all : [];
    current = 0;
    userAnswers = new Array(questions.length).fill(undefined);
    quizDone = false;
    buildMcqOptionOrder();
    collapseQNavMobile();

    document.querySelector(".question-area").style.display = "";
    document.querySelector(".navigation").style.display = "";
    document.querySelector(".score-area").style.display = "none";

    buildNavGrid();
    renderQuestion();
    updateProgress();
}

/* ============ navigator grid ============ */
function buildNavGrid() {
    const grid = document.getElementById("q-nav-grid");
    if (!grid) return;
    grid.innerHTML = "";
    questions.forEach((q, idx) => {
        const btn = document.createElement("button");
        btn.className = "q-num pending";
        btn.textContent = idx + 1;
        btn.dataset.index = idx;
        btn.onclick = () => {
            if (quizDone) return;
            current = idx;
            renderQuestion();
            collapseQNavMobile();
        };
        grid.appendChild(btn);
    });
    document.getElementById("counter-total").textContent = questions.length;
}

function updateQuizNavPullMeta() {
    const meta = document.getElementById("q-nav-pull-meta");
    if (!meta) return;
    if (!questions.length) {
        meta.textContent = "";
        return;
    }
    meta.textContent = `Câu ${current + 1} / ${questions.length}`;
}

/** Thu gọn lưới câu hỏi trên điện thoại sau khi chọn số thứ tự */
function collapseQNavMobile() {
    const nav = document.getElementById("q-nav");
    const pull = document.getElementById("q-nav-pull");
    if (!nav || !pull || !window.matchMedia("(max-width: 600px)").matches) return;
    nav.classList.remove("q-nav--open");
    pull.setAttribute("aria-expanded", "false");
}

function initQuizNavMobile() {
    const nav = document.getElementById("q-nav");
    const pull = document.getElementById("q-nav-pull");
    if (!nav || !pull) return;

    const mq = window.matchMedia("(max-width: 600px)");

    function setAria(open) {
        pull.setAttribute("aria-expanded", open ? "true" : "false");
    }

    pull.addEventListener("click", () => {
        if (!mq.matches) return;
        const open = nav.classList.toggle("q-nav--open");
        setAria(open);
    });

    function onBpChange() {
        if (!mq.matches) {
            nav.classList.remove("q-nav--open");
            setAria(false);
        }
    }
    if (mq.addEventListener) mq.addEventListener("change", onBpChange);
    else mq.addListener(onBpChange); /* safari */
}

window.addEventListener("resize", () => {
    if (!window.matchMedia("(max-width: 600px)").matches) {
        const nav = document.getElementById("q-nav");
        const pull = document.getElementById("q-nav-pull");
        if (!nav || !pull) return;
        nav.classList.remove("q-nav--open");
        pull.setAttribute("aria-expanded", "false");
    }
});

function refreshNavGrid() {
    const grid = document.getElementById("q-nav-grid");
    if (!grid) return;
    grid.querySelectorAll(".q-num").forEach(el => {
        const idx = Number(el.dataset.index);
        el.classList.remove("done", "current", "correct", "incorrect");
        if (idx === current) el.classList.add("current");
        else if (typeof userAnswers[idx] !== "undefined") el.classList.add("done");

        if (quizDone) {
            // After quiz: mark correct/incorrect
            const q = questions[idx];
            const ua = userAnswers[idx];
            let correct = false;
            if (q.type === "short") correct = ua && isShortAnswerCorrect(q, ua);
            else {
                const set = ansSet(q.ans ?? q.a);
                const uSet = ansSet(ua);
                correct = set.size > 0 && setsEqual(set, uSet);
            }
            el.classList.remove("current");
            el.classList.add(correct ? "correct" : "incorrect");
        }
    });
}

/* ============ render question ============ */
function renderQuestion() {
    if (!questions.length) return;
    const q = questions[current];
    const area = document.querySelector(".question-area");

    let imgHtml = "";
    if (q.img) {
        imgHtml = `<div class="question-img"><img src="${escapeHtml(toPublicUrl(q.img))}" alt="img"/></div>`;
    }

    const qText = renderQuestionHtml(q);
    const multi = isMultiAnswer(q);
    const typeBadge = q.type === "short"
        ? `<span class="badge">Tự luận</span>`
        : multi
            ? `<span class="badge multi"><i class="fa-solid fa-list-check"></i> Nhiều đáp án</span>`
            : `<span class="badge">Trắc nghiệm</span>`;

    if (q.type === "short") {
        const prev = userAnswers[current] || "";
        area.innerHTML = `
            <div class="question-number">${typeBadge} Câu ${current + 1} / ${questions.length}</div>
            <div class="question-text">${qText}</div>
            ${imgHtml}
            <div class="short-answer">
                <input type="text" id="short-answer" placeholder="Nhập câu trả lời..." value="${escapeHtml(prev)}" autocomplete="off">
            </div>
        `;
        const inp = document.getElementById("short-answer");
        if (inp) inp.oninput = () => { userAnswers[current] = inp.value; refreshNavGrid(); };
    } else {
        const correctSet = ansSet(q.ans ?? q.a);
        const userVal = userAnswers[current];
        const userSet = ansSet(userVal);
        const answered = typeof userVal !== "undefined";
        const orderedPairs = (mcqOptionOrder[current] && mcqOptionOrder[current].length)
            ? mcqOptionOrder[current]
            : Object.entries(q.opts || q.op || {});

        let optsHtml = "";
        for (const [key, label] of orderedPairs) {
            const K = String(key).toUpperCase();
            let cls = "option";
            let suffix = "";

            if (answered) {
                if (correctSet.has(K)) { cls += " correct"; suffix = '<i class="ans-icon fa-solid fa-circle-check"></i>'; }
                if (userSet.has(K) && !correctSet.has(K)) { cls += " incorrect"; suffix = '<i class="ans-icon fa-solid fa-circle-xmark"></i>'; }
            } else if (multi && userSet.has(K)) {
                cls += " selected";
                suffix = '<i class="ans-icon fa-solid fa-check"></i>';
            }
            optsHtml += `
                <button class="${cls}" data-opt="${escapeHtml(K)}" ${answered ? "disabled" : ""}>
                    <span class="opt-key">${escapeHtml(K)}</span>
                    <span class="opt-label">${escapeHtml(label)}</span>
                    ${suffix}
                </button>`;
        }

        const multiHint = (multi && !answered)
            ? `<div class="multi-hint"><i class="fa-solid fa-circle-info"></i> Câu hỏi có <b>nhiều đáp án đúng</b> - chọn tất cả các đáp án bạn cho là đúng rồi nhấn <b>Xác nhận</b>.</div>`
            : "";
        const submitMulti = (multi && !answered)
            ? `<div class="multi-submit">
                  <button id="multi-confirm-btn" disabled>
                    <i class="fa-solid fa-check"></i> Xác nhận đáp án
                  </button>
               </div>`
            : "";

        area.innerHTML = `
            <div class="question-number">${typeBadge} Câu ${current + 1} / ${questions.length}</div>
            <div class="question-text">${qText}</div>
            ${imgHtml}
            ${multiHint}
            <div class="options">${optsHtml}</div>
            ${submitMulti}
        `;

        // wire up clicks
        const optButtons = area.querySelectorAll(".option");
        if (multi && !answered) {
            const confirmBtn = area.querySelector("#multi-confirm-btn");
            const updateConfirm = () => {
                const anySelected = area.querySelectorAll(".option.selected").length > 0;
                if (confirmBtn) confirmBtn.disabled = !anySelected;
            };
            optButtons.forEach(btn => {
                btn.onclick = () => {
                    btn.classList.toggle("selected");
                    const icon = btn.querySelector(".ans-icon");
                    if (btn.classList.contains("selected") && !icon) {
                        btn.insertAdjacentHTML("beforeend", '<i class="ans-icon fa-solid fa-check"></i>');
                    } else if (!btn.classList.contains("selected") && icon) {
                        icon.remove();
                    }
                    updateConfirm();
                };
            });
            if (confirmBtn) {
                confirmBtn.onclick = () => {
                    const chosen = [...area.querySelectorAll(".option.selected")].map(b => b.dataset.opt);
                    if (!chosen.length) return showDialog("Hãy chọn ít nhất 1 đáp án!");
                    userAnswers[current] = chosen;
                    renderQuestion();
                    refreshNavGrid();
                };
            }
        } else if (!answered) {
            optButtons.forEach(btn => {
                btn.onclick = () => {
                    userAnswers[current] = btn.dataset.opt;
                    renderQuestion();
                    refreshNavGrid();
                };
            });
        }
    }

    document.getElementById("counter-current").textContent = current + 1;
    updateProgress();
    updateNav();
    refreshNavGrid();
    updateQuizNavPullMeta();
}

function updateNav() {
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const hintEl = document.getElementById("nav-skip-hint");
    if (prevBtn) prevBtn.disabled = current === 0;
    const isLast = questions.length && current === questions.length - 1;
    if (nextBtn) {
        nextBtn.innerHTML = isLast
            ? `<i class="fa-solid fa-flag-checkered"></i> Nộp bài`
            : `Tiếp <i class="fa-solid fa-chevron-right"></i>`;
    }
    if (hintEl) {
        if (quizDone || !questions.length) {
            hintEl.style.display = "none";
        } else {
            hintEl.style.display = "";
            hintEl.textContent = isLast
                ? "Có thể nộp bài khi còn câu chưa trả lời."
                : "Có thể bỏ qua câu chưa trả lời — nhấn Tiếp.";
        }
    }
}

function updateProgress() {
    const answeredCount = userAnswers.filter(v => typeof v !== "undefined").length;
    const pct = Math.round((answeredCount / questions.length) * 100);
    const progress = document.querySelector(".progress");
    if (progress) progress.style.width = pct + "%";
}

/* ============ nav buttons ============ */
const prevBtn = document.getElementById("prevBtn");
if (prevBtn) prevBtn.onclick = () => { if (current > 0) { current--; renderQuestion(); } };

const nextBtn = document.getElementById("nextBtn");
if (nextBtn) nextBtn.onclick = () => {
    if (quizDone) return;
    if (current === questions.length - 1) finishQuiz();
    else { current++; renderQuestion(); }
};

/* ============ submit / finish ============ */
function convertAnswersToDict() {
    const dict = {};
    questions.forEach((q, idx) => { dict[q.id] = userAnswers[idx]; });
    return dict;
}

function computeLocalScore() {
    let correct = 0;
    questions.forEach((q, idx) => {
        const ua = userAnswers[idx];
        if (q.type === "short") {
            if (ua && isShortAnswerCorrect(q, ua)) correct++;
        } else {
            const cSet = ansSet(q.ans ?? q.a);
            const uSet = ansSet(ua);
            if (cSet.size && setsEqual(cSet, uSet)) correct++;
        }
    });
    return { correct, total: questions.length, score: Math.round(correct / questions.length * 100) };
}

async function finishQuiz() {
    quizDone = true;

    let score = null, correct = null, total = questions.length;
    try {
        const res = await fetch(SUBMIT_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(convertAnswersToDict())
        });
        const data = await res.json().catch(() => null);
        if (data && typeof data.score === "number") { score = data.score; correct = data.correct; total = data.total || total; }
    } catch (e) { /* fallback local */ }

    if (score === null) {
        const local = computeLocalScore();
        score = local.score; correct = local.correct; total = local.total;
    }

    const scale10 = Math.round((score / 100) * 100) / 10; // 0.1 precision
    const passing = score >= 50;

    const html = `
        <div class="final-score-box">
            <div class="dialog-icon" style="background:${passing ? '#dcfce7' : '#fee2e2'};color:${passing ? '#16a34a' : '#dc2626'};margin:0 auto 10px;">
                <i class="fa-solid ${passing ? 'fa-trophy' : 'fa-face-frown'}"></i>
            </div>
            <h3>${passing ? 'Chúc mừng!' : 'Cố gắng thêm nhé!'}</h3>
            <div class="score-big">${scale10.toFixed(1)} / 10</div>
            <p class="score-sub">${correct}/${total} câu đúng (${score}%)</p>
            <div class="score-actions">
                <button id="retryBtn" class="nav-btn">
                    <i class="fa-solid fa-rotate"></i> Làm lại
                </button>
                <button id="reviewBtn" class="nav-btn ghost">
                    <i class="fa-solid fa-list"></i> Xem lại bài
                </button>
                <button id="backBtn" class="nav-btn ghost">
                    <i class="fa-solid fa-house"></i> Về Dashboard
                </button>
            </div>
        </div>
    `;
    const scoreArea = document.querySelector(".score-area");
    scoreArea.innerHTML = html;
    scoreArea.style.display = "block";

    // hide question / nav, show navigator with review state
    document.querySelector(".question-area").style.display = "none";
    document.querySelector(".navigation").style.display = "none";
    refreshNavGrid();
    updateQuizNavPullMeta();

    document.getElementById("retryBtn").onclick = () => { loadQuestions(); };
    document.getElementById("backBtn").onclick = () => {
        window.location.href = (typeof DASHBOARD_URL !== "undefined") ? DASHBOARD_URL : "/dashboard";
    };
    document.getElementById("reviewBtn").onclick = () => {
        scoreArea.style.display = "none";
        document.querySelector(".question-area").style.display = "";
        // keep navigation hidden, but allow jump via grid
        current = 0;
        renderQuestion();
    };
}

window.addEventListener("DOMContentLoaded", () => {
    initQuizNavMobile();
    loadQuestions();
});

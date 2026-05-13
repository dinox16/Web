/* ============================================================
   CHATBOT - Frontend only (backend AI sẽ thêm sau)
   - Quản lý hội thoại trong DOM
   - Hỗ trợ Enter để gửi, Shift+Enter để xuống dòng
   - Tải PDF (chỉ giữ tên file trong UI, không upload thật)
   - Quick tags
   ============================================================ */

(function () {
    "use strict";

    const $ = id => document.getElementById(id);
    const messagesEl   = $("chat-messages");
    const formEl       = $("chat-form");
    const inputEl      = $("chat-input");
    const sendBtn      = $("send-btn");
    const subjectSel   = $("chat-subject");
    const statusEl     = $("chat-status");
    const clearBtn     = $("chat-clear");
    const attachBtn    = $("attach-btn");
    const pdfInput     = $("pdf-input");
    const uploadZone   = $("upload-zone");
    const fileList     = $("file-list");

    const ENDPOINT = "/api/chatbot/ask";   // backend stub
    let uploadedFiles = [];

    /* ---------- helpers ---------- */
    function escapeHtml(s) {
        return String(s ?? "")
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function scrollBottom() {
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function addUserMessage(text) {
        const html = `
            <div class="msg msg-user">
                <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
                <div class="msg-bubble">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
            </div>`;
        messagesEl.insertAdjacentHTML("beforeend", html);
        scrollBottom();
    }

    function addBotMessage(htmlContent) {
        const html = `
            <div class="msg msg-bot">
                <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="msg-bubble">${htmlContent}</div>
            </div>`;
        messagesEl.insertAdjacentHTML("beforeend", html);
        scrollBottom();
    }

    function showTyping() {
        const html = `
            <div class="msg msg-bot typing" id="typing-indicator">
                <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="msg-bubble">
                    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                </div>
            </div>`;
        messagesEl.insertAdjacentHTML("beforeend", html);
        scrollBottom();
    }
    function hideTyping() {
        const el = document.getElementById("typing-indicator");
        if (el) el.remove();
    }

    /* ---------- input autoresize + enable send ---------- */
    function syncSendState() {
        sendBtn.disabled = !inputEl.value.trim();
    }
    function autoResize() {
        inputEl.style.height = "auto";
        inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
    }
    inputEl.addEventListener("input", () => { syncSendState(); autoResize(); });
    inputEl.addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            formEl.requestSubmit();
        }
    });

    /* ---------- submit ---------- */
    formEl.addEventListener("submit", async e => {
        e.preventDefault();
        const text = inputEl.value.trim();
        if (!text) return;
        addUserMessage(text);
        inputEl.value = "";
        autoResize();
        syncSendState();
        showTyping();
        statusEl.textContent = "Đang suy nghĩ...";

        const payload = {
            question: text,
            subject: subjectSel.value || null,
            files: uploadedFiles.map(f => f.name),
        };

        try {
            const res = await fetch(ENDPOINT, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => ({}));
            hideTyping();
            statusEl.textContent = "Sẵn sàng - đang ở chế độ demo";

            if (!data.ok) {
                return addBotMessage(`<i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(data.error || "Lỗi không xác định.")}`);
            }
            const subjectTag = subjectSel.value
                ? `<small style="display:block;color:var(--muted);margin-bottom:4px;">📚 Môn: <b>${escapeHtml(subjectSel.options[subjectSel.selectedIndex].text)}</b></small>`
                : "";
            addBotMessage(subjectTag + escapeHtml(data.answer || "").replace(/\n/g, "<br>"));

            if (Array.isArray(data.sources) && data.sources.length) {
                const list = data.sources.map(s =>
                    `<li><i class="fa-solid fa-file-lines"></i> ${escapeHtml(s)}</li>`).join("");
                addBotMessage(`<small style="color:var(--muted)">📎 Nguồn tham khảo:</small><ul>${list}</ul>`);
            }
        } catch (err) {
            hideTyping();
            statusEl.textContent = "Lỗi kết nối";
            addBotMessage(`<i class="fa-solid fa-circle-xmark"></i> Không kết nối được tới máy chủ: ${escapeHtml(err.message || err)}`);
        }
    });

    /* ---------- clear conversation ---------- */
    clearBtn.addEventListener("click", () => {
        if (!confirm("Xoá toàn bộ hội thoại?")) return;
        messagesEl.innerHTML = "";
        addBotMessage("Đã xoá hội thoại. Bạn có thể bắt đầu chat lại từ đầu. 💬");
    });

    /* ---------- quick tags ---------- */
    document.querySelectorAll(".quick-tag").forEach(b => {
        b.addEventListener("click", () => {
            inputEl.value = b.dataset.q;
            autoResize();
            syncSendState();
            inputEl.focus();
        });
    });

    /* ---------- PDF upload (frontend only) ---------- */
    function renderFileList() {
        fileList.innerHTML = uploadedFiles.map((f, i) => `
            <li>
                <i class="fa-solid fa-file-pdf"></i>
                <span>${escapeHtml(f.name)}</span>
                <button type="button" class="remove" data-i="${i}" title="Xoá">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </li>
        `).join("");
        fileList.querySelectorAll(".remove").forEach(btn => {
            btn.addEventListener("click", () => {
                const i = Number(btn.dataset.i);
                uploadedFiles.splice(i, 1);
                renderFileList();
            });
        });
    }

    function addFiles(files) {
        for (const f of files) {
            if (f.type !== "application/pdf") continue;
            if (uploadedFiles.some(x => x.name === f.name && x.size === f.size)) continue;
            uploadedFiles.push({ name: f.name, size: f.size });
        }
        renderFileList();
    }

    attachBtn.addEventListener("click", () => pdfInput.click());
    uploadZone.addEventListener("click", () => pdfInput.click());
    pdfInput.addEventListener("change", () => addFiles(pdfInput.files));

    ["dragenter", "dragover"].forEach(ev =>
        uploadZone.addEventListener(ev, e => {
            e.preventDefault(); uploadZone.classList.add("drag");
        })
    );
    ["dragleave", "drop"].forEach(ev =>
        uploadZone.addEventListener(ev, e => {
            e.preventDefault(); uploadZone.classList.remove("drag");
        })
    );
    uploadZone.addEventListener("drop", e => addFiles(e.dataTransfer.files));

    /* ---------- init ---------- */
    syncSendState();
    autoResize();
})();

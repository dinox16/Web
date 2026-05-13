/* ============================================================
   Auth page interactions: tabs, OTP register, OTP forgot, login
   ============================================================ */

(function () {
    "use strict";

    const tabs = document.querySelectorAll(".auth-tabs .tab");
    const panels = document.querySelectorAll(".panel");
    const toastEl = document.getElementById("toast");

    function showTab(name) {
        tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === name));
        panels.forEach(p => p.classList.toggle("active", p.dataset.panel === name));
    }

    tabs.forEach(t => t.addEventListener("click", () => showTab(t.dataset.tab)));
    document.querySelectorAll("[data-go]").forEach(a => {
        a.addEventListener("click", e => {
            e.preventDefault();
            showTab(a.dataset.go);
        });
    });

    // ---- toast ----
    let toastTimer = null;
    function toast(message, type = "info") {
        if (!toastEl) return;
        toastEl.className = "toast show " + type;
        toastEl.innerHTML = `<i class="fa-solid ${
            type === "success" ? "fa-circle-check"
            : type === "error" ? "fa-circle-exclamation"
            : "fa-circle-info"}"></i> ${message}`;
        if (toastTimer) clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toastEl.classList.remove("show"), 3600);
    }

    // ---- password show/hide ----
    document.querySelectorAll(".pwd-toggle").forEach(btn => {
        btn.addEventListener("click", () => {
            const input = btn.parentElement.querySelector("input");
            const icon = btn.querySelector("i");
            if (!input) return;
            if (input.type === "password") {
                input.type = "text";
                icon.className = "fa-solid fa-eye-slash";
            } else {
                input.type = "password";
                icon.className = "fa-solid fa-eye";
            }
        });
    });

    // ---- helpers ----
    async function postJson(url, body) {
        try {
            const res = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body || {}),
            });
            const data = await res.json().catch(() => ({}));
            return { ok: res.ok && data.ok !== false, status: res.status, data };
        } catch (e) {
            return { ok: false, status: 0, data: { error: String(e) } };
        }
    }

    function setLoading(btn, loading, label) {
        if (!btn) return;
        if (loading) {
            btn.dataset.origText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${label || "Đang xử lý..."}`;
        } else {
            btn.disabled = false;
            if (btn.dataset.origText) btn.innerHTML = btn.dataset.origText;
        }
    }

    function startResendTimer(linkEl, timerEl, seconds = 60) {
        if (!linkEl) return;
        let s = seconds;
        linkEl.classList.add("disabled");
        if (timerEl) timerEl.textContent = `(còn ${s}s)`;
        const iv = setInterval(() => {
            s--;
            if (s <= 0) {
                clearInterval(iv);
                linkEl.classList.remove("disabled");
                if (timerEl) timerEl.textContent = "";
            } else if (timerEl) {
                timerEl.textContent = `(còn ${s}s)`;
            }
        }, 1000);
    }

    // ============================================================
    // SIGN IN
    // ============================================================
    const formSignIn = document.getElementById("form-signin");
    if (formSignIn) {
        formSignIn.addEventListener("submit", async e => {
            e.preventDefault();
            const fd = new FormData(formSignIn);
            const btn = formSignIn.querySelector("button[type=submit]");
            setLoading(btn, true, "Đang đăng nhập...");
            const { ok, data } = await postJson("/api/login", {
                username: fd.get("username"),
                passwd: fd.get("passwd"),
            });
            setLoading(btn, false);
            if (!ok) return toast(data.error || "Đăng nhập thất bại.", "error");
            toast("Đăng nhập thành công!", "success");
            setTimeout(() => window.location.href = data.redirect || "/dashboard", 600);
        });
    }

    // ============================================================
    // SIGN UP - 2 steps with OTP
    // ============================================================
    let signupEmail = "";
    const formSignupStart = document.getElementById("form-signup-start");
    const formSignupVerify = document.getElementById("form-signup-verify");
    const signupEmailDisplay = document.getElementById("signup-email-display");
    const signupResendLink = document.getElementById("signup-resend");
    const signupResendTimer = document.getElementById("signup-resend-timer");

    if (formSignupStart) {
        formSignupStart.addEventListener("submit", async e => {
            e.preventDefault();
            const fd = new FormData(formSignupStart);
            const btn = formSignupStart.querySelector("button[type=submit]");
            setLoading(btn, true, "Đang gửi OTP...");
            const { ok, data } = await postJson("/api/register/start", {
                username: fd.get("username"),
                email: fd.get("email"),
                passwd: fd.get("passwd"),
            });
            setLoading(btn, false);
            if (!ok) return toast(data.error || "Có lỗi xảy ra.", "error");

            signupEmail = data.email;
            signupEmailDisplay.textContent = signupEmail;
            formSignupStart.classList.add("hidden");
            formSignupVerify.classList.remove("hidden");
            toast("Đã gửi mã OTP đến email của bạn!", "success");
            startResendTimer(signupResendLink, signupResendTimer, 60);
        });
    }

    if (formSignupVerify) {
        formSignupVerify.addEventListener("submit", async e => {
            e.preventDefault();
            const fd = new FormData(formSignupVerify);
            const btn = formSignupVerify.querySelector("button[type=submit]");
            setLoading(btn, true, "Đang xác thực...");
            const { ok, data } = await postJson("/api/register/verify", {
                email: signupEmail,
                otp: (fd.get("otp") || "").trim(),
            });
            setLoading(btn, false);
            if (!ok) return toast(data.error || "Xác thực thất bại.", "error");
            toast("Đăng ký thành công! Hãy đăng nhập.", "success");
            // reset and switch to signin
            formSignupVerify.reset();
            formSignupStart.reset();
            formSignupVerify.classList.add("hidden");
            formSignupStart.classList.remove("hidden");
            setTimeout(() => showTab("signin"), 1000);
        });

        const backLink = document.getElementById("signup-back");
        if (backLink) {
            backLink.addEventListener("click", e => {
                e.preventDefault();
                formSignupVerify.classList.add("hidden");
                formSignupStart.classList.remove("hidden");
            });
        }

        if (signupResendLink) {
            signupResendLink.addEventListener("click", async e => {
                e.preventDefault();
                if (signupResendLink.classList.contains("disabled")) return;
                const { ok, data } = await postJson("/api/otp/resend", {
                    email: signupEmail, purpose: "register",
                });
                if (!ok) return toast(data.error || "Không gửi lại được.", "error");
                toast("Đã gửi lại OTP!", "success");
                startResendTimer(signupResendLink, signupResendTimer, 60);
            });
        }
    }

    // ============================================================
    // FORGOT PASSWORD
    // ============================================================
    let forgotEmail = "";
    const formForgotStart = document.getElementById("form-forgot-start");
    const formForgotVerify = document.getElementById("form-forgot-verify");
    const forgotEmailDisplay = document.getElementById("forgot-email-display");
    const forgotResendLink = document.getElementById("forgot-resend");
    const forgotResendTimer = document.getElementById("forgot-resend-timer");

    if (formForgotStart) {
        formForgotStart.addEventListener("submit", async e => {
            e.preventDefault();
            const fd = new FormData(formForgotStart);
            const btn = formForgotStart.querySelector("button[type=submit]");
            setLoading(btn, true, "Đang gửi OTP...");
            const { ok, data } = await postJson("/api/forgot/start", { email: fd.get("email") });
            setLoading(btn, false);
            if (!ok) return toast(data.error || "Có lỗi xảy ra.", "error");
            forgotEmail = data.email;
            forgotEmailDisplay.textContent = forgotEmail;
            formForgotStart.classList.add("hidden");
            formForgotVerify.classList.remove("hidden");
            toast("Đã gửi mã OTP!", "success");
            startResendTimer(forgotResendLink, forgotResendTimer, 60);
        });
    }

    if (formForgotVerify) {
        formForgotVerify.addEventListener("submit", async e => {
            e.preventDefault();
            const fd = new FormData(formForgotVerify);
            const btn = formForgotVerify.querySelector("button[type=submit]");
            setLoading(btn, true, "Đang đặt lại...");
            const { ok, data } = await postJson("/api/forgot/verify", {
                email: forgotEmail,
                otp: (fd.get("otp") || "").trim(),
                new_passwd: fd.get("new_passwd"),
            });
            setLoading(btn, false);
            if (!ok) return toast(data.error || "Đặt lại thất bại.", "error");
            toast("Đặt lại mật khẩu thành công!", "success");
            formForgotVerify.reset();
            formForgotStart.reset();
            formForgotVerify.classList.add("hidden");
            formForgotStart.classList.remove("hidden");
            setTimeout(() => showTab("signin"), 1000);
        });

        if (forgotResendLink) {
            forgotResendLink.addEventListener("click", async e => {
                e.preventDefault();
                if (forgotResendLink.classList.contains("disabled")) return;
                const { ok, data } = await postJson("/api/otp/resend", {
                    email: forgotEmail, purpose: "reset",
                });
                if (!ok) return toast(data.error || "Không gửi lại được.", "error");
                toast("Đã gửi lại OTP!", "success");
                startResendTimer(forgotResendLink, forgotResendTimer, 60);
            });
        }
    }
})();

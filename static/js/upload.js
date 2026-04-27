document.addEventListener("DOMContentLoaded", function () {
    /* =====================================================
       HEALTH-DOC VIRTUAL ASSISTANT - FRONTEND JS
    ===================================================== */

    /* ================= THEME TOGGLE ================= */

    const root = document.documentElement;
    const themeToggle = document.getElementById("themeToggle");
    const themeIcon = document.getElementById("themeIcon");
    const themeText = document.getElementById("themeText");

    function applyTheme(theme) {
        root.setAttribute("data-theme", theme);
        localStorage.setItem("healthDocTheme", theme);

        if (theme === "dark") {
            if (themeIcon) themeIcon.innerText = "☀️";
            if (themeText) themeText.innerText = "Light";
        } else {
            if (themeIcon) themeIcon.innerText = "🌙";
            if (themeText) themeText.innerText = "Dark";
        }
    }

    const savedTheme = localStorage.getItem("healthDocTheme") || "light";
    applyTheme(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            const currentTheme = root.getAttribute("data-theme") || "light";
            const nextTheme = currentTheme === "dark" ? "light" : "dark";
            applyTheme(nextTheme);
        });
    }

    /* ================= UPLOAD PAGE LOADING ================= */

    const uploadForm = document.getElementById("uploadForm");
    const loadingOverlay = document.getElementById("loadingOverlay");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const loadingTitle = document.getElementById("loadingTitle");
    const loadingText = document.getElementById("loadingText");

    if (uploadForm) {
        uploadForm.addEventListener("submit", function () {
            const selectedLanguage = document.querySelector('input[name="language"]:checked');

            if (selectedLanguage && selectedLanguage.value === "bn") {
                if (loadingTitle) loadingTitle.innerText = "আপনার রিপোর্ট বিশ্লেষণ করা হচ্ছে...";
                if (loadingText) {
                    loadingText.innerText =
                        "Health-Doc Virtual Assistant আপনার রিপোর্ট থেকে তথ্য বের করছে এবং AI summary প্রস্তুত করছে। অনুগ্রহ করে অপেক্ষা করুন।";
                }
            } else {
                if (loadingTitle) loadingTitle.innerText = "Analyzing your report...";
                if (loadingText) {
                    loadingText.innerText =
                        "Health-Doc Virtual Assistant is extracting text and preparing your AI summary. Please wait.";
                }
            }

            if (analyzeBtn) {
                analyzeBtn.innerText = "Processing...";
                analyzeBtn.classList.add("loading");
                analyzeBtn.disabled = true;
            }

            if (loadingOverlay) {
                loadingOverlay.classList.add("show");
            }
        });
    }

    /* ================= CHAT ELEMENTS ================= */

    const chatMessages = document.getElementById("chatMessages");
    const chatInput = document.getElementById("chatInput");
    const chatForm = document.getElementById("chatForm");
    const chatLoading = document.getElementById("chatLoading");

    /* ================= SUGGESTED QUESTIONS ================= */

    const questionButtons = document.querySelectorAll(".question-chip");

    questionButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const question = button.getAttribute("data-question");

            if (chatInput && question) {
                chatInput.value = question;
                autoResizeTextarea(chatInput);
                chatInput.focus();
            }
        });
    });

    /* ================= TEXTAREA AUTO RESIZE ================= */

    function autoResizeTextarea(textarea) {
        if (!textarea) return;

        textarea.style.height = "auto";
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + "px";
    }

    if (chatInput) {
        chatInput.addEventListener("input", function () {
            autoResizeTextarea(chatInput);
        });

        autoResizeTextarea(chatInput);
    }

    /* ================= AI ANSWER SECTION CARD FORMATTER ================= */

    const assistantMessages = document.querySelectorAll(".assistant-row .message-content");

    function escapeHTML(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatBodyText(text) {
        let safeText = escapeHTML(text);

        safeText = safeText
            .replace(/\*\*/g, "")
            .replace(/^\s*\*\s+/gm, "• ")
            .replace(/^\s*-\s+/gm, "• ")
            .replace(/\n/g, "<br>");

        return safeText;
    }

    function formatAssistantMessages() {
        assistantMessages.forEach(function (messageContent) {
            if (messageContent.dataset.formatted === "true") return;

            const rawText = messageContent.innerText.trim();

            if (!rawText) return;

            /*
                Only detect numbered section headings that start at a new line:
                1. Report Summary:
                2. Low / High Values:
                3. Important Notes:

                This avoids breaking decimal values like 11.5 or 50.5.
            */
            const sectionPattern = /(?:^|\n)\s*(?:\*\*)?([1-9১-৯])[\.)]\s*([^:\n*]+):?(?:\*\*)?/g;
            const matches = [...rawText.matchAll(sectionPattern)];

            // Simple short answers should remain normal chat bubbles
            if (matches.length < 2) return;

            const sections = [];

            matches.forEach(function (match, index) {
                const headerEnd = match.index + match[0].length;
                const nextStart = index + 1 < matches.length
                    ? matches[index + 1].index
                    : rawText.length;

                const title = match[2]
                    .replace(/\*\*/g, "")
                    .trim();

                const body = rawText
                    .slice(headerEnd, nextStart)
                    .trim();

                if (title && body) {
                    sections.push({
                        title: title,
                        body: body
                    });
                }
            });

            if (!sections.length) return;

            const wrapper = document.createElement("div");
            wrapper.className = "ai-section-wrapper";

            sections.forEach(function (section) {
                const card = document.createElement("div");
                card.className = "ai-answer-section";

                const title = document.createElement("h3");
                title.innerText = section.title;

                const body = document.createElement("div");
                body.className = "ai-answer-body";
                body.innerHTML = formatBodyText(section.body);

                card.appendChild(title);
                card.appendChild(body);
                wrapper.appendChild(card);
            });

            messageContent.innerHTML = "";
            messageContent.appendChild(wrapper);
            messageContent.dataset.formatted = "true";
        });
    }

    formatAssistantMessages();

    /* ================= CHAT SUBMIT LOADING ================= */

    if (chatForm) {
        chatForm.addEventListener("submit", function (event) {
            if (!chatInput) return;

            const message = chatInput.value.trim();

            if (!message) {
                event.preventDefault();
                chatInput.focus();
                return;
            }

            if (chatLoading) {
                chatLoading.classList.add("show");

                setTimeout(function () {
                    chatLoading.scrollIntoView({
                        behavior: "smooth",
                        block: "end"
                    });
                }, 100);
            }

            const sendButton = chatForm.querySelector("button[type='submit']");

            if (sendButton) {
                sendButton.disabled = true;
                sendButton.innerText = "Sending...";
            }
        });
    }

    /* ================= AUTO SCROLL TO LATEST MESSAGE ================= */

    function scrollToLatestMessage() {
        if (!chatMessages) return;

        chatMessages.scrollTop = chatMessages.scrollHeight;

        const lastMessage = chatMessages.querySelector(".message-row:last-child");

        if (lastMessage) {
            lastMessage.scrollIntoView({
                behavior: "smooth",
                block: "end"
            });
        }
    }

    if (chatMessages) {
        scrollToLatestMessage();
        setTimeout(scrollToLatestMessage, 250);
        setTimeout(scrollToLatestMessage, 700);
    }

    if (chatInput) {
        setTimeout(function () {
            chatInput.focus();
        }, 850);
    }

    /* ================= SOURCES TOGGLE ================= */

    const sourceButtons = document.querySelectorAll(".source-toggle");

    sourceButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            const sourceContent = button.nextElementSibling;

            if (sourceContent) {
                sourceContent.classList.toggle("show");
            }
        });
    });

    /* ================= INLINE MESSENGER STYLE FILE ATTACH ================= */

    const openAttachFile = document.getElementById("openAttachFile");
    const inlineAttachInput = document.getElementById("inlineAttachInput");
    const inlineAttachForm = document.getElementById("inlineAttachForm");
    const inlineAttachLoading = document.getElementById("inlineAttachLoading");

    if (openAttachFile && inlineAttachInput && inlineAttachForm) {
        openAttachFile.addEventListener("click", function () {
            inlineAttachInput.click();
        });

        inlineAttachInput.addEventListener("change", function () {
            if (!inlineAttachInput.files || inlineAttachInput.files.length === 0) {
                return;
            }

            if (inlineAttachLoading) {
                inlineAttachLoading.classList.add("show");

                inlineAttachLoading.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });
            }

            openAttachFile.disabled = true;
            openAttachFile.innerText = "…";

            inlineAttachForm.submit();
        });
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const fileZones = document.querySelectorAll(".file-drop-zone");

    fileZones.forEach(function (zone) {
        const input = zone.querySelector('input[type="file"]');
        const title = zone.querySelector("strong");
        const subtitle = zone.querySelector("small");

        if (!input || !title || !subtitle) return;

        input.addEventListener("change", function () {
            if (!input.files || input.files.length === 0) return;

            if (input.files.length === 1) {
                title.innerText = input.files[0].name;
                subtitle.innerText = "Selected successfully";
            } else {
                title.innerText = input.files.length + " files selected";
                subtitle.innerText = "Selected successfully";
            }
        });
    });
});
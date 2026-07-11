(function () {
    const form = document.getElementById("freeCheckForm");
    const input = document.getElementById("siteUrl");
    const loading = document.getElementById("freeCheckLoading");
    const errorBox = document.getElementById("freeCheckError");
    const resultBox = document.getElementById("freeCheckResult");
    const scoreEl = document.getElementById("freeCheckScore");
    const summaryEl = document.getElementById("freeCheckSummary");
    const findingsEl = document.getElementById("freeCheckFindings");
    const strengthsEl = document.getElementById("freeCheckStrengths");
    const winsEl = document.getElementById("freeCheckWins");
    const registerLink = document.getElementById("freeCheckRegister");
    const submitButton = document.getElementById("freeCheckSubmit") || form?.querySelector("button[type='submit']");

    if (!form) {
        return;
    }

    function setHidden(element, hidden) {
        if (element) {
            element.hidden = hidden;
        }
    }

    function fillList(element, items) {
        element.innerHTML = "";
        (items || []).slice(0, 3).forEach((item) => {
            const li = document.createElement("li");
            li.textContent = item;
            element.appendChild(li);
        });
    }

    function setSubmitting(isSubmitting) {
        if (input) {
            input.disabled = isSubmitting;
        }
        if (submitButton) {
            if (!submitButton.dataset.originalText) {
                submitButton.dataset.originalText = submitButton.textContent;
            }
            submitButton.disabled = isSubmitting;
            submitButton.textContent = isSubmitting ? "Проверяем..." : submitButton.dataset.originalText;
        }
        form.classList.toggle("is-submitting", isSubmitting);
    }

    function showError(message) {
        errorBox.textContent = message || "Не удалось проверить сайт.";
        setHidden(errorBox, false);
        setHidden(resultBox, true);
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const url = input.value.trim();
        if (!url) {
            showError("Введите адрес сайта.");
            return;
        }

        setHidden(errorBox, true);
        setHidden(resultBox, true);
        setHidden(loading, false);
        setSubmitting(true);

        try {
            const response = await fetch("/api/public/site-check", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url }),
            });
            const data = await response.json();
            if (!response.ok || data.status !== "ok") {
                showError(data.message || "Не удалось проверить сайт.");
                return;
            }

            scoreEl.textContent = data.score;
            summaryEl.textContent = data.summary;
            fillList(findingsEl, data.findings);
            if (strengthsEl) {
                fillList(strengthsEl, data.strengths || []);
            }
            fillList(winsEl, data.quick_wins);
            registerLink.href = `/register?site_url=${encodeURIComponent(data.url || url)}`;
            setHidden(resultBox, false);
            resultBox.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (error) {
            showError("Сайт не ответил или проверка временно недоступна.");
        } finally {
            setHidden(loading, true);
            setSubmitting(false);
        }
    });
})();

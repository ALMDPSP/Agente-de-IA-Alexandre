const sidebar = document.querySelector("#sidebar");
const menuToggle = document.querySelector("#menuToggle");
const sidebarClose = document.querySelector("#sidebarClose");
const mobileOverlay = document.querySelector("#mobileOverlay");

function setSidebar(open) {
    sidebar?.classList.toggle("open", open);
    mobileOverlay?.classList.toggle("show", open);
}

menuToggle?.addEventListener("click", () => setSidebar(true));
sidebarClose?.addEventListener("click", () => setSidebar(false));
mobileOverlay?.addEventListener("click", () => setSidebar(false));

document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
        if (window.innerWidth <= 850) setSidebar(false);
    });
});

const chatForm = document.querySelector("#chatForm");
const chatInput = document.querySelector("#chatInput");
const chatWindow = document.querySelector("#chatWindow");
const csrfToken = document.querySelector("#csrfToken")?.value;
const agentStatus = document.querySelector("#agentStatus");

const CHAT_KEY = "alexandre_ai_chat_history_v2";

function getHistory() {
    try {
        return JSON.parse(localStorage.getItem(CHAT_KEY) || "[]");
    } catch {
        return [];
    }
}

function saveHistory(history) {
    localStorage.setItem(CHAT_KEY, JSON.stringify(history.slice(-100)));
}

function appendMessage(text, type, persist = true, provider = "") {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${type === "user" ? "user-message" : "assistant-message"}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = type === "user" ? "A" : "AI";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const textEl = document.createElement("div");
    textEl.textContent = text;
    bubble.appendChild(textEl);

    if (type === "assistant" && provider) {
        const meta = document.createElement("small");
        meta.style.display = "block";
        meta.style.marginTop = "8px";
        meta.style.opacity = ".55";
        meta.textContent = `via ${provider}`;
        bubble.appendChild(meta);
    }

    wrapper.append(avatar, bubble);
    chatWindow.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    if (persist) {
        const history = getHistory();
        history.push({ text, type, provider, ts: Date.now() });
        saveHistory(history);
    }
}

function loadHistory() {
    const history = getHistory();
    if (!history.length) return;

    const initial = chatWindow.querySelector(".assistant-message");
    if (initial) initial.remove();

    history.forEach(item => appendMessage(
        item.text,
        item.type,
        false,
        item.provider || ""
    ));
}

async function loadAgentStatus() {
    if (!agentStatus) return;

    try {
        const response = await fetch("/api/agent/status");
        const data = await response.json();

        if (!response.ok || !data.configured?.length) {
            agentStatus.innerHTML = "<i></i> IA não configurada";
            return;
        }

        const names = data.configured.map(item => item.provider).join(" → ");
        agentStatus.innerHTML = `<i></i> ${names}`;
    } catch {
        agentStatus.innerHTML = "<i></i> Status indisponível";
    }
}

async function sendMessage(text) {
    const message = text.trim();
    if (!message) return;

    appendMessage(message, "user");
    chatInput.value = "";
    chatInput.style.height = "auto";

    const history = getHistory().slice(-16).map(item => ({
        role: item.type === "assistant" ? "assistant" : "user",
        content: item.text
    }));

    try {
        const response = await fetch("/api/agent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify({ message, history })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Não foi possível enviar a mensagem.");
        }

        appendMessage(
            data.reply,
            "assistant",
            true,
            `${data.provider} · ${data.model}`
        );
    } catch (error) {
        appendMessage(`Erro: ${error.message}`, "assistant");
    }
}

chatForm?.addEventListener("submit", event => {
    event.preventDefault();
    sendMessage(chatInput.value);
});

chatInput?.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});

chatInput?.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
});

document.querySelectorAll("[data-prompt]").forEach(button => {
    button.addEventListener("click", () => sendMessage(button.dataset.prompt || ""));
});

loadHistory();
loadAgentStatus();

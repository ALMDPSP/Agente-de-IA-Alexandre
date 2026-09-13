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

function appendMessage(text, type) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${type === "user" ? "user-message" : "assistant-message"}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = type === "user" ? "A" : "AI";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.textContent = text;

    wrapper.append(avatar, bubble);
    chatWindow.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendMessage(text) {
    const message = text.trim();
    if (!message) return;

    appendMessage(message, "user");
    chatInput.value = "";
    chatInput.style.height = "auto";

    try {
        const response = await fetch("/api/agent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Não foi possível enviar a mensagem.");
        }

        appendMessage(data.reply, "assistant");
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

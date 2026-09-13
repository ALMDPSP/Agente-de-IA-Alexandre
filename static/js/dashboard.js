const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const csrfToken = $("#csrfToken")?.value;

const STORAGE = {
    projects: "alexandre_ai_projects_v1",
    chat: "alexandre_ai_chat_history_v2",
    history: "alexandre_ai_search_history_v1",
    activeProject: "alexandre_ai_active_project_v1",
};

const state = {
    projects: loadJson(STORAGE.projects, []),
    activeProjectId: localStorage.getItem(STORAGE.activeProject) || "",
    msConnected: false,
    msConfigured: false,
    oneDriveFolderStack: [],
};

function loadJson(key, fallback) {
    try {
        const parsed = JSON.parse(localStorage.getItem(key));
        return parsed ?? fallback;
    } catch {
        return fallback;
    }
}

function saveJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
}

function uid(prefix = "id") {
    if (crypto?.randomUUID) return `${prefix}_${crypto.randomUUID()}`;
    return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function escapeText(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function formatDate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "—";
    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(d);
}

function humanSize(bytes = 0) {
    const value = Number(bytes) || 0;
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function getProject(projectId) {
    return state.projects.find(p => p.id === projectId);
}

function saveProjects() {
    saveJson(STORAGE.projects, state.projects);
    renderAllProjectDependentUI();
}

function totalSources() {
    return state.projects.reduce((sum, p) => sum + (p.sources?.length || 0), 0);
}

function ensureProjectShape(project) {
    project.sources = Array.isArray(project.sources) ? project.sources : [];
    project.status = project.status || "Planejamento";
    return project;
}

state.projects = state.projects.map(ensureProjectShape);

function getSearchHistory() {
    return loadJson(STORAGE.history, []);
}

function addSearchHistory(query, projectId, provider = "") {
    const items = getSearchHistory();
    const project = getProject(projectId);
    items.unshift({
        id: uid("search"),
        query,
        projectId: projectId || "",
        projectName: project?.name || "Conversa geral",
        provider,
        createdAt: new Date().toISOString(),
    });
    saveJson(STORAGE.history, items.slice(0, 500));
    renderHistory();
    updateStats();
}

function getChatHistory() {
    return loadJson(STORAGE.chat, []);
}

function saveChatHistory(items) {
    saveJson(STORAGE.chat, items.slice(-100));
}

function buildProjectContext(projectId) {
    const project = getProject(projectId);
    if (!project) return "";

    const lines = [
        `PROJETO: ${project.name}`,
        `STATUS: ${project.status || "Não informado"}`,
        `DESCRIÇÃO: ${project.description || "Sem descrição"}`,
    ];

    const sources = project.sources || [];
    if (sources.length) {
        lines.push("", "FONTES IMPORTADAS:");
        let remaining = 42000;

        for (const source of sources) {
            if (remaining <= 0) break;
            const content = String(source.content || "");
            const slice = content.slice(0, Math.min(12000, remaining));
            lines.push(
                "",
                `--- FONTE: ${source.title} (${source.type}) ---`,
                slice
            );
            remaining -= slice.length;
        }
    }

    return lines.join("\n").slice(0, 45000);
}

// Sidebar
const sidebar = $("#sidebar");
const mobileOverlay = $("#mobileOverlay");

function setSidebar(open) {
    sidebar?.classList.toggle("open", open);
    mobileOverlay?.classList.toggle("show", open);
}

$("#menuToggle")?.addEventListener("click", () => setSidebar(true));
$("#sidebarClose")?.addEventListener("click", () => setSidebar(false));
mobileOverlay?.addEventListener("click", () => setSidebar(false));

$$(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
        if (window.innerWidth <= 850) setSidebar(false);
    });
});

// Projeto
function renderProjectOptions() {
    const selects = [
        $("#activeProjectSelect"),
        $("#fileProjectSelect"),
        $("#onenoteProjectSelect"),
        $("#onedriveProjectSelect"),
        $("#sourceProjectFilter"),
    ].filter(Boolean);

    selects.forEach(select => {
        const isActive = select.id === "activeProjectSelect";
        const isFilter = select.id === "sourceProjectFilter";
        const current = select.value;

        select.innerHTML = "";

        if (isActive) {
            select.add(new Option("Sem projeto — conversa geral", ""));
        } else if (isFilter) {
            select.add(new Option("Todos os projetos", ""));
        } else {
            select.add(new Option("Selecione um projeto", ""));
        }

        state.projects.forEach(project => {
            select.add(new Option(project.name, project.id));
        });

        if (isActive) {
            select.value = getProject(state.activeProjectId) ? state.activeProjectId : "";
        } else if ([...select.options].some(o => o.value === current)) {
            select.value = current;
        }
    });

    updateContextStatus();
}

function renderProjects() {
    const grid = $("#projectGrid");
    const empty = $("#projectEmpty");
    if (!grid || !empty) return;

    grid.innerHTML = "";

    if (!state.projects.length) {
        empty.classList.remove("hidden-panel");
        return;
    }

    empty.classList.add("hidden-panel");

    state.projects.forEach(project => {
        const card = document.createElement("article");
        card.className = "project-card";
        const sources = project.sources?.length || 0;

        card.innerHTML = `
            <div class="project-card-top">
                <span class="project-status">${escapeText(project.status)}</span>
                <span class="project-source-count">${sources} fonte(s)</span>
            </div>
            <h3>${escapeText(project.name)}</h3>
            <p>${escapeText(project.description || "Sem descrição.")}</p>
            <div class="project-card-footer">
                <small>Atualizado ${formatDate(project.updatedAt || project.createdAt)}</small>
                <div class="project-card-actions">
                    <button type="button" data-action="activate">Ativar</button>
                    <button type="button" data-action="edit">Editar</button>
                    <button type="button" data-action="delete" class="danger-text-btn">Excluir</button>
                </div>
            </div>
        `;

        card.querySelector('[data-action="activate"]').addEventListener("click", () => {
            state.activeProjectId = project.id;
            localStorage.setItem(STORAGE.activeProject, project.id);
            renderProjectOptions();
            document.querySelector("#agent")?.scrollIntoView({ behavior: "smooth" });
        });

        card.querySelector('[data-action="edit"]').addEventListener("click", () => openProjectForm(project));
        card.querySelector('[data-action="delete"]').addEventListener("click", () => {
            if (!confirm(`Excluir o projeto "${project.name}" e suas fontes locais?`)) return;
            state.projects = state.projects.filter(p => p.id !== project.id);
            if (state.activeProjectId === project.id) {
                state.activeProjectId = "";
                localStorage.removeItem(STORAGE.activeProject);
            }
            saveProjects();
        });

        grid.appendChild(card);
    });
}

function openProjectForm(project = null) {
    $("#projectForm")?.classList.remove("hidden-panel");
    $("#projectId").value = project?.id || "";
    $("#projectName").value = project?.name || "";
    $("#projectStatus").value = project?.status || "Planejamento";
    $("#projectDescription").value = project?.description || "";
    $("#projectName")?.focus();
}

function closeProjectForm() {
    $("#projectForm")?.classList.add("hidden-panel");
    $("#projectForm")?.reset();
    $("#projectId").value = "";
}

$("#newProjectBtn")?.addEventListener("click", () => openProjectForm());
$("#cancelProjectBtn")?.addEventListener("click", closeProjectForm);

$("#projectForm")?.addEventListener("submit", event => {
    event.preventDefault();

    const id = $("#projectId").value;
    const name = $("#projectName").value.trim();
    const description = $("#projectDescription").value.trim();
    const status = $("#projectStatus").value;

    if (!name) return;

    if (id) {
        const project = getProject(id);
        if (project) {
            project.name = name;
            project.description = description;
            project.status = status;
            project.updatedAt = new Date().toISOString();
        }
    } else {
        const project = {
            id: uid("project"),
            name,
            description,
            status,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            sources: [],
        };
        state.projects.unshift(project);

        if (!state.activeProjectId) {
            state.activeProjectId = project.id;
            localStorage.setItem(STORAGE.activeProject, project.id);
        }
    }

    saveProjects();
    closeProjectForm();
});

$("#activeProjectSelect")?.addEventListener("change", event => {
    state.activeProjectId = event.target.value;
    if (state.activeProjectId) {
        localStorage.setItem(STORAGE.activeProject, state.activeProjectId);
    } else {
        localStorage.removeItem(STORAGE.activeProject);
    }
    updateContextStatus();
});

function updateContextStatus() {
    const label = $("#contextStatus");
    const project = getProject($("#activeProjectSelect")?.value || "");
    if (!label) return;

    if (!project) {
        label.textContent = "Nenhum contexto de projeto será enviado.";
        return;
    }

    const sourceCount = project.sources?.length || 0;
    label.textContent = `${project.name}: descrição + ${sourceCount} fonte(s) serão usadas como contexto.`;
}

// Fontes
function addSourceToProject(projectId, source) {
    const project = getProject(projectId);
    if (!project) throw new Error("Projeto não encontrado.");

    project.sources = project.sources || [];
    project.sources.unshift({
        id: uid("source"),
        title: source.title || "Fonte sem título",
        type: source.sourceType || source.type || "arquivo",
        content: source.content || "",
        webUrl: source.webUrl || "",
        importedAt: new Date().toISOString(),
        lastModifiedTime: source.lastModifiedTime || "",
        size: source.size || 0,
    });
    project.updatedAt = new Date().toISOString();
    saveProjects();
}

function renderSources() {
    const grid = $("#sourceGrid");
    const empty = $("#sourceEmpty");
    if (!grid || !empty) return;

    grid.innerHTML = "";
    const filterId = $("#sourceProjectFilter")?.value || "";
    const projects = filterId ? state.projects.filter(p => p.id === filterId) : state.projects;

    const all = [];
    projects.forEach(project => {
        (project.sources || []).forEach(source => all.push({ project, source }));
    });

    if (!all.length) {
        empty.classList.remove("hidden-panel");
        return;
    }

    empty.classList.add("hidden-panel");

    all.forEach(({ project, source }) => {
        const card = document.createElement("article");
        card.className = "source-card";
        card.innerHTML = `
            <div class="source-card-head">
                <span class="source-type">${escapeText(source.type)}</span>
                <span>${escapeText(project.name)}</span>
            </div>
            <h3>${escapeText(source.title)}</h3>
            <p>${escapeText((source.content || "").slice(0, 240))}${(source.content || "").length > 240 ? "…" : ""}</p>
            <div class="source-card-footer">
                <small>Importado ${formatDate(source.importedAt)}</small>
                <div>
                    ${source.webUrl ? `<a href="${escapeText(source.webUrl)}" target="_blank" rel="noopener">Abrir origem</a>` : ""}
                    <button type="button" class="danger-text-btn">Remover</button>
                </div>
            </div>
        `;

        card.querySelector("button")?.addEventListener("click", () => {
            if (!confirm(`Remover a fonte "${source.title}" deste projeto?`)) return;
            project.sources = (project.sources || []).filter(s => s.id !== source.id);
            saveProjects();
        });

        grid.appendChild(card);
    });
}

$("#sourceProjectFilter")?.addEventListener("change", renderSources);

// Arquivo local
$("#importLocalFileBtn")?.addEventListener("click", async () => {
    const projectId = $("#fileProjectSelect")?.value;
    const input = $("#localFileInput");
    const file = input?.files?.[0];
    const status = $("#fileImportStatus");

    if (!projectId) {
        status.textContent = "Selecione um projeto de destino.";
        return;
    }

    if (!file) {
        status.textContent = "Selecione um arquivo.";
        return;
    }

    if (file.size > 12 * 1024 * 1024) {
        status.textContent = "O arquivo deve ter no máximo 12 MB.";
        return;
    }

    status.textContent = `Lendo ${file.name}...`;

    const form = new FormData();
    form.append("file", file);

    try {
        const response = await fetch("/api/files/extract", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: form,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Falha ao importar.");

        addSourceToProject(projectId, data);
        input.value = "";
        status.textContent = `${file.name} importado para o projeto com sucesso.`;
    } catch (error) {
        status.textContent = `Erro: ${error.message}`;
    }
});

// Microsoft
async function loadMicrosoftStatus() {
    try {
        const response = await fetch("/api/microsoft/status");
        const data = await response.json();

        state.msConfigured = Boolean(data.configured);
        state.msConnected = Boolean(data.connected);

        const title = $("#msStatusTitle");
        const detail = $("#msStatusDetail");
        const connectBtn = $("#msConnectBtn");
        const disconnectBtn = $("#msDisconnectBtn");

        if (!data.configured) {
            title.textContent = "Integração ainda não configurada";
            detail.textContent = "Cadastre MS_CLIENT_ID, MS_CLIENT_SECRET e MS_REDIRECT_URI no Render.";
            connectBtn?.classList.add("disabled-link");
            $("#msStat").textContent = "SETUP";
        } else if (data.connected) {
            const profileName = data.profile?.displayName || data.profile?.mail || "Conta Microsoft";
            title.textContent = `Microsoft conectado: ${profileName}`;
            detail.textContent = "OneNote e OneDrive estão disponíveis nesta sessão.";
            connectBtn?.classList.add("hidden-panel");
            disconnectBtn?.classList.remove("hidden-panel");
            $("#msStat").textContent = "ON";
            loadOneNote();
            loadOneDrive("");
        } else {
            title.textContent = "Microsoft pronto para conectar";
            detail.textContent = "Conecte sua conta para acessar OneNote e OneDrive.";
            connectBtn?.classList.remove("hidden-panel");
            disconnectBtn?.classList.add("hidden-panel");
            $("#msStat").textContent = "OFF";
        }
    } catch {
        $("#msStatusTitle").textContent = "Status Microsoft indisponível";
    }
}

$("#msDisconnectBtn")?.addEventListener("click", async () => {
    try {
        await fetch("/microsoft/disconnect", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: "{}",
        });
        state.msConnected = false;
        $("#onenoteList").innerHTML = "";
        $("#onedriveList").innerHTML = "";
        loadMicrosoftStatus();
    } catch {
        alert("Não foi possível desconectar a conta Microsoft.");
    }
});

$$("[data-integration-tab]").forEach(button => {
    button.addEventListener("click", () => {
        $$("[data-integration-tab]").forEach(b => b.classList.remove("active"));
        button.classList.add("active");
        const tab = button.dataset.integrationTab;
        $("#onenotePanel").classList.toggle("hidden-panel", tab !== "onenote");
        $("#onedrivePanel").classList.toggle("hidden-panel", tab !== "onedrive");
    });
});

async function loadOneNote() {
    const list = $("#onenoteList");
    const empty = $("#onenoteEmpty");
    if (!state.msConnected) return;

    list.innerHTML = `<div class="loading-resource">Carregando páginas do OneNote...</div>`;

    try {
        const response = await fetch("/api/microsoft/onenote/pages");
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Erro no OneNote.");

        list.innerHTML = "";
        const pages = data.pages || [];

        if (!pages.length) {
            empty.classList.remove("hidden-panel");
            empty.querySelector("span").textContent = "Nenhuma página encontrada no OneNote.";
            return;
        }

        empty.classList.add("hidden-panel");

        pages.forEach(page => {
            const item = document.createElement("div");
            item.className = "resource-item";
            item.innerHTML = `
                <div class="resource-main">
                    <div class="resource-icon">N</div>
                    <div>
                        <strong>${escapeText(page.title)}</strong>
                        <small>${escapeText(page.section || "OneNote")} · ${formatDate(page.lastModifiedTime)}</small>
                    </div>
                </div>
                <button type="button" class="resource-import-btn">Importar</button>
            `;

            item.querySelector("button").addEventListener("click", async () => {
                const projectId = $("#onenoteProjectSelect")?.value;
                if (!projectId) {
                    alert("Selecione um projeto de destino.");
                    return;
                }

                const btn = item.querySelector("button");
                btn.disabled = true;
                btn.textContent = "Importando...";

                try {
                    const response = await fetch(`/api/microsoft/onenote/page/${encodeURIComponent(page.id)}`);
                    const source = await response.json();
                    if (!response.ok) throw new Error(source.error || "Falha ao importar.");
                    source.webUrl = page.webUrl || "";
                    addSourceToProject(projectId, source);
                    btn.textContent = "Importado ✓";
                } catch (error) {
                    btn.textContent = "Tentar novamente";
                    alert(error.message);
                } finally {
                    btn.disabled = false;
                }
            });

            list.appendChild(item);
        });
    } catch (error) {
        list.innerHTML = `<div class="integration-error">${escapeText(error.message)}</div>`;
    }
}

$("#loadOneNoteBtn")?.addEventListener("click", loadOneNote);

function updateOneDrivePath() {
    const names = state.oneDriveFolderStack.map(item => item.name);
    $("#onedrivePath").textContent = `OneDrive / ${names.join(" / ")}`;
}

async function loadOneDrive(folderId = "") {
    const list = $("#onedriveList");
    const empty = $("#onedriveEmpty");
    if (!state.msConnected) return;

    list.innerHTML = `<div class="loading-resource">Carregando OneDrive...</div>`;

    try {
        const query = folderId ? `?item_id=${encodeURIComponent(folderId)}` : "";
        const response = await fetch(`/api/microsoft/onedrive/items${query}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Erro no OneDrive.");

        list.innerHTML = "";
        const items = data.items || [];

        if (!items.length) {
            empty.classList.remove("hidden-panel");
            empty.querySelector("span").textContent = "Esta pasta está vazia.";
            return;
        }

        empty.classList.add("hidden-panel");

        items.forEach(itemData => {
            const item = document.createElement("div");
            item.className = "resource-item";
            const extension = itemData.isFolder ? "Pasta" : (itemData.name.split(".").pop() || "Arquivo").toUpperCase();

            item.innerHTML = `
                <div class="resource-main">
                    <div class="resource-icon">${itemData.isFolder ? "▣" : "F"}</div>
                    <div>
                        <strong>${escapeText(itemData.name)}</strong>
                        <small>${escapeText(extension)} · ${itemData.isFolder ? "" : humanSize(itemData.size)} ${formatDate(itemData.lastModifiedDateTime)}</small>
                    </div>
                </div>
                <button type="button" class="resource-import-btn">${itemData.isFolder ? "Abrir" : "Importar"}</button>
            `;

            item.querySelector("button").addEventListener("click", async () => {
                if (itemData.isFolder) {
                    state.oneDriveFolderStack.push({ id: itemData.id, name: itemData.name });
                    updateOneDrivePath();
                    loadOneDrive(itemData.id);
                    return;
                }

                const projectId = $("#onedriveProjectSelect")?.value;
                if (!projectId) {
                    alert("Selecione um projeto de destino.");
                    return;
                }

                const btn = item.querySelector("button");
                btn.disabled = true;
                btn.textContent = "Importando...";

                try {
                    const response = await fetch(`/api/microsoft/onedrive/file/${encodeURIComponent(itemData.id)}`);
                    const source = await response.json();
                    if (!response.ok) throw new Error(source.error || "Falha ao importar.");
                    addSourceToProject(projectId, source);
                    btn.textContent = "Importado ✓";
                } catch (error) {
                    btn.textContent = "Tentar novamente";
                    alert(error.message);
                } finally {
                    btn.disabled = false;
                }
            });

            list.appendChild(item);
        });
    } catch (error) {
        list.innerHTML = `<div class="integration-error">${escapeText(error.message)}</div>`;
    }
}

$("#loadOneDriveBtn")?.addEventListener("click", () => {
    const current = state.oneDriveFolderStack.at(-1)?.id || "";
    loadOneDrive(current);
});

$("#onedriveRootBtn")?.addEventListener("click", () => {
    state.oneDriveFolderStack = [];
    updateOneDrivePath();
    loadOneDrive("");
});

// Chat
const chatWindow = $("#chatWindow");
const chatInput = $("#chatInput");

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
        meta.className = "message-meta";
        meta.textContent = `via ${provider}`;
        bubble.appendChild(meta);
    }

    wrapper.append(avatar, bubble);
    chatWindow.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    if (persist) {
        const history = getChatHistory();
        history.push({ text, type, provider, ts: Date.now() });
        saveChatHistory(history);
    }
}

function renderDefaultAssistant() {
    chatWindow.innerHTML = "";
    appendMessage(
        "Olá. Sua central pessoal está pronta. Selecione um projeto ativo para eu usar os arquivos e fontes dele como contexto.",
        "assistant",
        false
    );
}

function loadChat() {
    const history = getChatHistory();
    if (!history.length) {
        renderDefaultAssistant();
        return;
    }

    chatWindow.innerHTML = "";
    history.forEach(item => appendMessage(item.text, item.type, false, item.provider || ""));
}

async function loadAgentStatus() {
    const status = $("#agentStatus");
    try {
        const response = await fetch("/api/agent/status");
        const data = await response.json();

        if (!response.ok || !data.configured?.length) {
            status.innerHTML = "<i></i> IA não configurada";
            $("#sidebarAiChain").textContent = "IA não configurada";
            return;
        }

        const names = data.configured.map(item => item.provider).join(" → ");
        status.innerHTML = `<i></i> ${escapeText(names)}`;
        $("#sidebarAiChain").textContent = names;
    } catch {
        status.innerHTML = "<i></i> Status indisponível";
        $("#sidebarAiChain").textContent = "Status indisponível";
    }
}

async function sendMessage(text) {
    const message = text.trim();
    if (!message) return;

    const projectId = $("#activeProjectSelect")?.value || "";
    const projectContext = buildProjectContext(projectId);

    appendMessage(message, "user");
    chatInput.value = "";
    chatInput.style.height = "auto";

    const history = getChatHistory().slice(-16).map(item => ({
        role: item.type === "assistant" ? "assistant" : "user",
        content: item.text,
    }));

    try {
        const response = await fetch("/api/agent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
                message,
                history,
                projectContext,
            }),
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Não foi possível enviar a mensagem.");

        const providerLabel = `${data.provider} · ${data.model}`;
        appendMessage(data.reply, "assistant", true, providerLabel);
        addSearchHistory(message, projectId, providerLabel);
    } catch (error) {
        appendMessage(`Erro: ${error.message}`, "assistant");
        addSearchHistory(message, projectId, "Erro");
    }
}

$("#chatForm")?.addEventListener("submit", event => {
    event.preventDefault();
    sendMessage(chatInput.value);
});

chatInput?.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        $("#chatForm")?.requestSubmit();
    }
});

chatInput?.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
});

$$("[data-prompt]").forEach(button => {
    button.addEventListener("click", () => sendMessage(button.dataset.prompt || ""));
});

$("#clearChatBtn")?.addEventListener("click", () => {
    if (!confirm("Limpar a conversa atual? O histórico de pesquisas continuará disponível na seção Histórico.")) return;
    localStorage.removeItem(STORAGE.chat);
    renderDefaultAssistant();
});

// Histórico
function renderHistory() {
    const list = $("#historyList");
    const empty = $("#historyEmpty");
    if (!list || !empty) return;

    const term = ($("#historySearch")?.value || "").trim().toLowerCase();
    const items = getSearchHistory().filter(item => {
        if (!term) return true;
        return `${item.query} ${item.projectName} ${item.provider}`.toLowerCase().includes(term);
    });

    list.innerHTML = "";

    if (!items.length) {
        empty.classList.remove("hidden-panel");
        return;
    }

    empty.classList.add("hidden-panel");

    items.forEach(item => {
        const row = document.createElement("article");
        row.className = "history-row";
        row.innerHTML = `
            <div class="history-query">
                <strong>${escapeText(item.query)}</strong>
                <small>${escapeText(item.projectName)} · ${formatDate(item.createdAt)}</small>
            </div>
            <div class="history-provider">${escapeText(item.provider || "—")}</div>
            <button type="button" class="history-reuse-btn">Reutilizar</button>
            <button type="button" class="history-delete-btn" aria-label="Excluir pesquisa">×</button>
        `;

        row.querySelector(".history-reuse-btn").addEventListener("click", () => {
            chatInput.value = item.query;
            document.querySelector("#agent")?.scrollIntoView({ behavior: "smooth" });
            chatInput.focus();
        });

        row.querySelector(".history-delete-btn").addEventListener("click", () => {
            const next = getSearchHistory().filter(h => h.id !== item.id);
            saveJson(STORAGE.history, next);
            renderHistory();
            updateStats();
        });

        list.appendChild(row);
    });
}

$("#historySearch")?.addEventListener("input", renderHistory);

$("#clearHistoryBtn")?.addEventListener("click", () => {
    if (!confirm("Apagar todo o histórico de pesquisas deste navegador?")) return;
    localStorage.removeItem(STORAGE.history);
    renderHistory();
    updateStats();
});

// Backup
$("#exportBackupBtn")?.addEventListener("click", () => {
    const backup = {
        version: 1,
        exportedAt: new Date().toISOString(),
        projects: state.projects,
        chat: getChatHistory(),
        searchHistory: getSearchHistory(),
        activeProjectId: state.activeProjectId,
    };

    const blob = new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `alexandre-ai-backup-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    $("#backupStatus").textContent = "Backup exportado com sucesso.";
});

$("#importBackupInput")?.addEventListener("change", async event => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
        const data = JSON.parse(await file.text());
        if (!Array.isArray(data.projects)) throw new Error("Backup inválido.");

        state.projects = data.projects.map(ensureProjectShape);
        state.activeProjectId = data.activeProjectId || "";

        saveJson(STORAGE.projects, state.projects);
        saveJson(STORAGE.chat, Array.isArray(data.chat) ? data.chat : []);
        saveJson(STORAGE.history, Array.isArray(data.searchHistory) ? data.searchHistory : []);

        if (state.activeProjectId) {
            localStorage.setItem(STORAGE.activeProject, state.activeProjectId);
        } else {
            localStorage.removeItem(STORAGE.activeProject);
        }

        renderAllProjectDependentUI();
        loadChat();
        renderHistory();
        $("#backupStatus").textContent = "Backup restaurado com sucesso.";
    } catch (error) {
        $("#backupStatus").textContent = `Erro ao importar backup: ${error.message}`;
    } finally {
        event.target.value = "";
    }
});

function updateStats() {
    $("#projectCount").textContent = state.projects.length;
    $("#sourceCount").textContent = totalSources();
    $("#historyCount").textContent = getSearchHistory().length;
}

function renderAllProjectDependentUI() {
    renderProjectOptions();
    renderProjects();
    renderSources();
    updateStats();
}

renderAllProjectDependentUI();
loadChat();
renderHistory();
loadAgentStatus();
loadMicrosoftStatus();
updateOneDrivePath();

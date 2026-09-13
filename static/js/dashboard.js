const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const csrfToken = $("#csrfToken")?.value;

const STORAGE = {
    projects: "alexandre_ai_projects_v2",
    chat: "alexandre_ai_chat_history_v2",
    history: "alexandre_ai_search_history_v1",
    activeProject: "alexandre_ai_active_project_v1",
};

const state = {
    projects: loadJson(STORAGE.projects, []),
    activeProjectId: localStorage.getItem(STORAGE.activeProject) || "",
};

function loadJson(key, fallback) {
    try {
        const value = JSON.parse(localStorage.getItem(key));
        return value ?? fallback;
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

function normalizeForSearch(text) {
    return String(text || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
}

function tokenize(text) {
    const stopwords = new Set([
        "de","da","do","das","dos","a","o","as","os","e","em","para","por","com","um","uma",
        "que","se","no","na","nos","nas","ao","aos","como","mais","menos","sobre","qual","quais",
        "me","meu","minha","meus","minhas","este","esta","esse","essa","isso","isto","ser","tem",
        "ter","foi","sao","é","é","the","and","of","to","in"
    ]);

    return normalizeForSearch(text)
        .split(/[^a-z0-9]+/)
        .filter(token => token.length >= 3 && !stopwords.has(token));
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

function ensureProjectShape(project) {
    project.documents = Array.isArray(project.documents) ? project.documents : [];
    project.status = project.status || "Planejamento";
    return project;
}

state.projects = state.projects.map(ensureProjectShape);

function getProject(id) {
    return state.projects.find(project => project.id === id);
}

function saveProjects() {
    saveJson(STORAGE.projects, state.projects);
    renderProjectDependentUI();
}

function allDocuments(projects = state.projects) {
    return projects.flatMap(project => (project.documents || []).map(document => ({ project, document })));
}

function totalChunks() {
    return allDocuments().reduce((sum, item) => sum + (item.document.chunks?.length || 0), 0);
}

function getSearchHistory() {
    return loadJson(STORAGE.history, []);
}

function getChatHistory() {
    return loadJson(STORAGE.chat, []);
}

function saveChatHistory(history) {
    saveJson(STORAGE.chat, history.slice(-100));
}

function addSearchHistory(query, projectId, provider = "", usedDocuments = []) {
    const history = getSearchHistory();
    const project = getProject(projectId);

    history.unshift({
        id: uid("search"),
        query,
        projectId: projectId || "",
        projectName: project?.name || "Conversa geral",
        provider,
        usedDocuments,
        createdAt: new Date().toISOString(),
    });

    saveJson(STORAGE.history, history.slice(0, 500));
    renderHistory();
    updateStats();
}

function scoreChunk(chunk, queryTokens) {
    if (!queryTokens.length) return 0;

    const text = normalizeForSearch(chunk.text);
    let score = 0;

    for (const token of queryTokens) {
        const count = text.split(token).length - 1;
        if (count > 0) {
            score += Math.min(count, 6) * (token.length >= 7 ? 2.2 : 1.5);
        }
    }

    const joined = queryTokens.join(" ");
    if (joined.length > 8 && text.includes(joined)) score += 8;

    return score;
}

function retrieveRelevantChunks(projectId, query, maxChunks = 8) {
    const project = getProject(projectId);
    if (!project) return [];

    const tokens = tokenize(query);
    const candidates = [];

    for (const document of project.documents || []) {
        for (const chunk of document.chunks || []) {
            const score = scoreChunk(chunk, tokens);
            candidates.push({
                ...chunk,
                documentId: document.id,
                documentTitle: document.title,
                score,
            });
        }
    }

    candidates.sort((a, b) => b.score - a.score);

    const positive = candidates.filter(item => item.score > 0).slice(0, maxChunks);
    if (positive.length) return positive;

    return candidates.slice(0, Math.min(3, maxChunks));
}

function buildProjectContext(projectId, query) {
    const project = getProject(projectId);
    if (!project) return { context: "", usedDocuments: [], chunkCount: 0 };

    const chunks = retrieveRelevantChunks(projectId, query, 8);
    const names = [...new Set(chunks.map(chunk => chunk.documentTitle))];

    const parts = [
        `PROJETO: ${project.name}`,
        `STATUS: ${project.status || "Não informado"}`,
        `DESCRIÇÃO: ${project.description || "Sem descrição"}`,
    ];

    if (chunks.length) {
        parts.push("", "TRECHOS RELEVANTES DOS DOCUMENTOS:");

        chunks.forEach((chunk, index) => {
            parts.push(
                "",
                `[Trecho ${index + 1} | Arquivo: ${chunk.documentTitle}]`,
                chunk.text
            );
        });
    }

    return {
        context: parts.join("\n").slice(0, 52000),
        usedDocuments: names,
        chunkCount: chunks.length,
    };
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

// Projetos
function renderProjectOptions() {
    const selects = [
        $("#activeProjectSelect"),
        $("#fileProjectSelect"),
        $("#knowledgeProjectFilter"),
    ].filter(Boolean);

    selects.forEach(select => {
        const isActive = select.id === "activeProjectSelect";
        const isFilter = select.id === "knowledgeProjectFilter";
        const currentValue = select.value;

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
        } else if ([...select.options].some(option => option.value === currentValue)) {
            select.value = currentValue;
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

        const documentCount = project.documents?.length || 0;
        const chunks = (project.documents || []).reduce((sum, doc) => sum + (doc.chunks?.length || 0), 0);

        card.innerHTML = `
            <div class="project-card-top">
                <span class="project-status">${escapeText(project.status)}</span>
                <span class="project-source-count">${documentCount} doc · ${chunks} trechos</span>
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
            $("#agent")?.scrollIntoView({ behavior: "smooth" });
        });

        card.querySelector('[data-action="edit"]').addEventListener("click", () => openProjectForm(project));

        card.querySelector('[data-action="delete"]').addEventListener("click", () => {
            if (!confirm(`Excluir o projeto "${project.name}" e todos os documentos importados nele?`)) return;

            state.projects = state.projects.filter(item => item.id !== project.id);

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
            documents: [],
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
    const project = getProject($("#activeProjectSelect")?.value || "");
    const label = $("#contextStatus");

    if (!label) return;

    if (!project) {
        label.textContent = "Nenhum arquivo será usado como contexto.";
        return;
    }

    const documents = project.documents?.length || 0;
    const chunks = (project.documents || []).reduce((sum, doc) => sum + (doc.chunks?.length || 0), 0);
    label.textContent = `${project.name}: ${documents} documento(s) e ${chunks} trecho(s) disponíveis para busca.`;
}

// Upload conhecimento
function renderSelectedFilesPreview() {
    const container = $("#selectedFilesPreview");
    const files = [...($("#localFileInput")?.files || [])];

    if (!container) return;

    container.innerHTML = "";

    files.forEach(file => {
        const tag = document.createElement("span");
        tag.className = "selected-file-tag";
        tag.textContent = `${file.name} · ${humanSize(file.size)}`;
        container.appendChild(tag);
    });
}

$("#localFileInput")?.addEventListener("change", renderSelectedFilesPreview);

async function importSingleFile(file, projectId) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("/api/files/extract", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Falha ao importar.");

    const project = getProject(projectId);
    if (!project) throw new Error("Projeto não encontrado.");

    project.documents = project.documents || [];
    project.documents.unshift({
        id: uid("doc"),
        title: data.title,
        size: file.size,
        importedAt: new Date().toISOString(),
        characters: data.characters || data.content?.length || 0,
        chunks: data.chunks || [],
    });

    project.updatedAt = new Date().toISOString();
}

$("#importLocalFileBtn")?.addEventListener("click", async () => {
    const projectId = $("#fileProjectSelect")?.value;
    const files = [...($("#localFileInput")?.files || [])];
    const status = $("#fileImportStatus");
    const button = $("#importLocalFileBtn");

    if (!projectId) {
        status.textContent = "Selecione um projeto de destino.";
        return;
    }

    if (!files.length) {
        status.textContent = "Selecione pelo menos um arquivo.";
        return;
    }

    const tooLarge = files.find(file => file.size > 15 * 1024 * 1024);
    if (tooLarge) {
        status.textContent = `${tooLarge.name} ultrapassa o limite de 15 MB.`;
        return;
    }

    button.disabled = true;
    let success = 0;
    const errors = [];

    for (const [index, file] of files.entries()) {
        status.textContent = `Importando ${index + 1}/${files.length}: ${file.name}...`;

        try {
            await importSingleFile(file, projectId);
            success += 1;
        } catch (error) {
            errors.push(`${file.name}: ${error.message}`);
        }
    }

    saveProjects();

    $("#localFileInput").value = "";
    renderSelectedFilesPreview();

    if (errors.length) {
        status.textContent = `${success} arquivo(s) importado(s). Falhas: ${errors.join(" | ")}`;
    } else {
        status.textContent = `${success} arquivo(s) importado(s) com sucesso. A IA já pode consultar esse conteúdo.`;
    }

    button.disabled = false;
});

// Documentos
function renderKnowledgeDocuments() {
    const grid = $("#knowledgeDocumentGrid");
    const empty = $("#knowledgeEmpty");
    if (!grid || !empty) return;

    const projectFilter = $("#knowledgeProjectFilter")?.value || "";
    const term = normalizeForSearch($("#knowledgeSearch")?.value || "");

    const projects = projectFilter
        ? state.projects.filter(project => project.id === projectFilter)
        : state.projects;

    const items = allDocuments(projects).filter(({ project, document }) => {
        if (!term) return true;

        const sample = (document.chunks || []).slice(0, 4).map(chunk => chunk.text).join(" ");
        return normalizeForSearch(`${project.name} ${document.title} ${sample}`).includes(term);
    });

    grid.innerHTML = "";

    if (!items.length) {
        empty.classList.remove("hidden-panel");
        return;
    }

    empty.classList.add("hidden-panel");

    items.forEach(({ project, document }) => {
        const card = document.createElement("article");
        card.className = "knowledge-document-card";

        card.innerHTML = `
            <div class="knowledge-doc-head">
                <div class="knowledge-doc-icon">F</div>
                <div>
                    <strong>${escapeText(document.title)}</strong>
                    <small>${escapeText(project.name)}</small>
                </div>
            </div>
            <div class="knowledge-doc-stats">
                <span>${document.chunks?.length || 0} trechos</span>
                <span>${humanSize(document.size || 0)}</span>
                <span>${Number(document.characters || 0).toLocaleString("pt-BR")} caracteres</span>
            </div>
            <p>${escapeText((document.chunks?.[0]?.text || "Documento sem prévia.").slice(0, 260))}</p>
            <div class="knowledge-doc-footer">
                <small>${formatDate(document.importedAt)}</small>
                <div>
                    <button type="button" data-action="activate">Usar projeto</button>
                    <button type="button" data-action="delete" class="danger-text-btn">Excluir</button>
                </div>
            </div>
        `;

        card.querySelector('[data-action="activate"]').addEventListener("click", () => {
            state.activeProjectId = project.id;
            localStorage.setItem(STORAGE.activeProject, project.id);
            renderProjectOptions();
            $("#agent")?.scrollIntoView({ behavior: "smooth" });
        });

        card.querySelector('[data-action="delete"]').addEventListener("click", () => {
            if (!confirm(`Excluir "${document.title}" da base de conhecimento?`)) return;

            project.documents = (project.documents || []).filter(item => item.id !== document.id);
            project.updatedAt = new Date().toISOString();
            saveProjects();
        });

        grid.appendChild(card);
    });
}

$("#knowledgeProjectFilter")?.addEventListener("change", renderKnowledgeDocuments);
$("#knowledgeSearch")?.addEventListener("input", renderKnowledgeDocuments);

// Chat
const chatWindow = $("#chatWindow");
const chatInput = $("#chatInput");

function appendMessage(text, type, persist = true, provider = "", documents = []) {
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

    if (type === "assistant" && (provider || documents.length)) {
        const meta = document.createElement("small");
        meta.className = "message-meta";

        const parts = [];
        if (provider) parts.push(`via ${provider}`);
        if (documents.length) parts.push(`fontes: ${documents.join(", ")}`);

        meta.textContent = parts.join(" · ");
        bubble.appendChild(meta);
    }

    wrapper.append(avatar, bubble);
    chatWindow.appendChild(wrapper);
    chatWindow.scrollTop = chatWindow.scrollHeight;

    if (persist) {
        const history = getChatHistory();
        history.push({ text, type, provider, documents, ts: Date.now() });
        saveChatHistory(history);
    }
}

function renderDefaultAssistant() {
    chatWindow.innerHTML = "";
    appendMessage(
        "Olá. Selecione um projeto ativo e envie documentos. Quando você fizer uma pergunta, vou procurar automaticamente os trechos mais relevantes nesses arquivos.",
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

    history.forEach(item => {
        appendMessage(
            item.text,
            item.type,
            false,
            item.provider || "",
            item.documents || []
        );
    });
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
    const retrieval = buildProjectContext(projectId, message);

    appendMessage(message, "user");
    chatInput.value = "";
    chatInput.style.height = "auto";

    const indicator = $("#retrievalIndicator");

    if (projectId) {
        indicator?.classList.add("retrieval-active");
        indicator.querySelector("strong").textContent = `Contexto preparado: ${retrieval.chunkCount} trecho(s) relevante(s)`;
        indicator.querySelector("small").textContent = retrieval.usedDocuments.length
            ? `Arquivos consultados: ${retrieval.usedDocuments.join(", ")}`
            : "Nenhum trecho relevante foi encontrado; o agente usará a descrição do projeto.";
    }

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
                projectContext: retrieval.context,
            }),
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Não foi possível enviar a mensagem.");

        const providerLabel = `${data.provider} · ${data.model}`;

        appendMessage(
            data.reply,
            "assistant",
            true,
            providerLabel,
            retrieval.usedDocuments
        );

        addSearchHistory(
            message,
            projectId,
            providerLabel,
            retrieval.usedDocuments
        );

    } catch (error) {
        appendMessage(`Erro: ${error.message}`, "assistant");
        addSearchHistory(message, projectId, "Erro", retrieval.usedDocuments);
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
    if (!confirm("Limpar a conversa atual? O histórico de pesquisas continuará disponível.")) return;
    localStorage.removeItem(STORAGE.chat);
    renderDefaultAssistant();
});

// Histórico
function renderHistory() {
    const list = $("#historyList");
    const empty = $("#historyEmpty");

    if (!list || !empty) return;

    const term = normalizeForSearch($("#historySearch")?.value || "");

    const history = getSearchHistory().filter(item => {
        if (!term) return true;

        return normalizeForSearch(
            `${item.query} ${item.projectName} ${item.provider} ${(item.usedDocuments || []).join(" ")}`
        ).includes(term);
    });

    list.innerHTML = "";

    if (!history.length) {
        empty.classList.remove("hidden-panel");
        return;
    }

    empty.classList.add("hidden-panel");

    history.forEach(item => {
        const row = document.createElement("article");
        row.className = "history-row";

        row.innerHTML = `
            <div class="history-query">
                <strong>${escapeText(item.query)}</strong>
                <small>${escapeText(item.projectName)} · ${formatDate(item.createdAt)}${item.usedDocuments?.length ? ` · ${escapeText(item.usedDocuments.join(", "))}` : ""}</small>
            </div>
            <div class="history-provider">${escapeText(item.provider || "—")}</div>
            <button type="button" class="history-reuse-btn">Reutilizar</button>
            <button type="button" class="history-delete-btn" aria-label="Excluir pesquisa">×</button>
        `;

        row.querySelector(".history-reuse-btn").addEventListener("click", () => {
            chatInput.value = item.query;

            if (item.projectId && getProject(item.projectId)) {
                state.activeProjectId = item.projectId;
                localStorage.setItem(STORAGE.activeProject, item.projectId);
                renderProjectOptions();
            }

            $("#agent")?.scrollIntoView({ behavior: "smooth" });
            chatInput.focus();
        });

        row.querySelector(".history-delete-btn").addEventListener("click", () => {
            const next = getSearchHistory().filter(historyItem => historyItem.id !== item.id);
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
        version: 2,
        exportedAt: new Date().toISOString(),
        projects: state.projects,
        chat: getChatHistory(),
        searchHistory: getSearchHistory(),
        activeProjectId: state.activeProjectId,
    };

    const blob = new Blob(
        [JSON.stringify(backup, null, 2)],
        { type: "application/json" }
    );

    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `alexandre-ai-backup-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);

    $("#backupStatus").textContent = "Backup completo exportado com sucesso.";
});

$("#importBackupInput")?.addEventListener("change", async event => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
        const data = JSON.parse(await file.text());

        if (!Array.isArray(data.projects)) {
            throw new Error("Backup inválido.");
        }

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

        renderProjectDependentUI();
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
    $("#documentCount").textContent = allDocuments().length;
    $("#chunkCount").textContent = totalChunks();
    $("#historyCount").textContent = getSearchHistory().length;
}

function renderProjectDependentUI() {
    renderProjectOptions();
    renderProjects();
    renderKnowledgeDocuments();
    updateStats();
}

renderProjectDependentUI();
renderSelectedFilesPreview();
loadChat();
renderHistory();
loadAgentStatus();


function startDashboardMatrixRain() {
    const canvas = document.getElementById('matrixCanvasDashboard');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const chars = '01ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&@<>/[]{}*+-=0123456789';
    let fontSize = 14;
    let columns = 0;
    let drops = [];
    let animationFrame = null;

    function resize() {
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(window.innerWidth * dpr);
        canvas.height = Math.floor(window.innerHeight * dpr);
        canvas.style.width = `${window.innerWidth}px`;
        canvas.style.height = `${window.innerHeight}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        fontSize = window.innerWidth < 768 ? 11 : 14;
        columns = Math.floor(window.innerWidth / fontSize);
        drops = Array.from({ length: columns }, () => Math.random() * -120);
    }

    function draw() {
        ctx.fillStyle = 'rgba(2, 6, 5, 0.075)';
        ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);
        ctx.font = `${fontSize}px monospace`;

        for (let i = 0; i < drops.length; i += 1) {
            const ch = chars.charAt(Math.floor(Math.random() * chars.length));
            const x = i * fontSize;
            const y = drops[i] * fontSize;
            ctx.fillStyle = 'rgba(150,255,188,0.70)';
            ctx.fillText(ch, x, y);
            if (y > window.innerHeight && Math.random() > 0.982) drops[i] = Math.random() * -20;
            drops[i] += 0.55;
        }
        animationFrame = window.requestAnimationFrame(draw);
    }

    resize();
    draw();
    window.addEventListener('resize', resize);
    window.addEventListener('beforeunload', () => {
        if (animationFrame) window.cancelAnimationFrame(animationFrame);
    });
}

function initActiveSectionNav() {
    const links = [...document.querySelectorAll('.nav-menu .nav-item[href^="#"]')];
    const ids = links.map(link => link.getAttribute('href')).filter(Boolean);
    const sections = ids.map(id => document.querySelector(id)).filter(Boolean);
    if (!sections.length) return;

    const observer = new IntersectionObserver(entries => {
        const visible = entries
            .filter(entry => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        links.forEach(link => link.classList.toggle('active', link.getAttribute('href') === `#${visible.target.id}`));
    }, { threshold: [0.2, 0.35, 0.6] });

    sections.forEach(section => observer.observe(section));
}

startDashboardMatrixRain();
initActiveSectionNav();


function initMobileBottomNav() {
    const items = [...document.querySelectorAll('.mobile-nav-item')];
    if (!items.length) return;

    items.forEach(item => {
        item.addEventListener('click', () => {
            items.forEach(other => other.classList.remove('active'));
            item.classList.add('active');
        });
    });

    const sectionIds = ['dashboard', 'agent', 'projects', 'knowledge'];
    const sections = sectionIds.map(id => document.getElementById(id)).filter(Boolean);
    if (!sections.length) return;

    const observer = new IntersectionObserver(entries => {
        const visible = entries
            .filter(entry => entry.isIntersecting)
            .sort((a,b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const id = visible.target.id;
        items.forEach(item => item.classList.toggle('active', item.getAttribute('href') === `#${id}`));
    }, { rootMargin: '-25% 0px -55% 0px', threshold: [0, .1, .25] });

    sections.forEach(section => observer.observe(section));
}

initMobileBottomNav();

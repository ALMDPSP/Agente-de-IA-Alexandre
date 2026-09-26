const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const csrfToken = $("#csrfToken")?.value;

const LEGACY_STORAGE = {
    projects: "alexandre_ai_projects_v2",
    chat: "alexandre_ai_chat_history_v2",
    history: "alexandre_ai_search_history_v1",
    activeProject: "alexandre_ai_active_project_v1",
};

const state = {
    projects: [],
    chat: [],
    history: [],
    activeProjectId: "",
};

async function apiRequest(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }
    if (options.method && options.method !== "GET" && csrfToken) {
        headers["X-CSRFToken"] = csrfToken;
    }
    const response = await fetch(url, { ...options, headers });
    const contentType = response.headers.get("content-type") || "";
    const raw = await response.text();
    let data = {};
    if (raw && contentType.includes("application/json")) {
        try { data = JSON.parse(raw); } catch { data = {}; }
    }
    if (!response.ok) {
        const detail = data.error || (raw && !raw.trim().startsWith("<") ? raw.slice(0, 300) : "");
        throw new Error(detail || `Erro HTTP ${response.status}. Consulte os logs do Render.`);
    }
    if (raw && !contentType.includes("application/json")) {
        console.error("Resposta não JSON recebida de", url, raw.slice(0, 500));
        throw new Error("O servidor respondeu em formato inesperado. Atualize a página; se persistir, consulte os logs do Render.");
    }
    return data;
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
        "ter","foi","sao","é","the","and","of","to","in"
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

function getProject(id) {
    return state.projects.find(project => project.id === id);
}

function allDocuments(projects = state.projects) {
    return projects.flatMap(project => (project.documents || []).map(document => ({ project, document })));
}

function totalChunks() {
    return allDocuments().reduce((sum, item) => sum + (item.document.chunks?.length || 0), 0);
}

function getSearchHistory() {
    return state.history;
}

function getChatHistory() {
    return state.chat;
}

async function persistActiveProject() {
    await apiRequest("/api/settings/active-project", {
        method: "PUT",
        body: JSON.stringify({ projectId: state.activeProjectId || "" }),
    });
}

async function addSearchHistory(query, projectId, provider = "", usedDocuments = []) {
    const project = getProject(projectId);
    const item = {
        id: uid("search"),
        query,
        projectId: projectId || "",
        projectName: project?.name || "Toda a base",
        provider,
        usedDocuments,
        createdAt: new Date().toISOString(),
    };
    state.history.unshift(item);
    state.history = state.history.slice(0, 500);
    renderHistory();
    updateStats();
    try {
        await apiRequest("/api/history", { method: "POST", body: JSON.stringify(item) });
    } catch (error) {
        console.error("Falha ao persistir histórico:", error);
    }
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

function retrieveRelevantChunksFromAllKnowledge(query, maxChunks = 12) {
    const tokens = tokenize(query);
    const candidates = [];

    for (const project of state.projects) {
        for (const document of project.documents || []) {
            for (const chunk of document.chunks || []) {
                const score = scoreChunk(chunk, tokens);
                candidates.push({
                    ...chunk,
                    projectId: project.id,
                    projectName: project.name,
                    documentId: document.id,
                    documentTitle: document.title,
                    sourcePath: document.sourcePath || document.title,
                    score,
                });
            }
        }
    }

    candidates.sort((a, b) => b.score - a.score);
    const positive = candidates.filter(item => item.score > 0).slice(0, maxChunks);
    if (positive.length) return positive;

    return candidates.slice(0, Math.min(4, maxChunks));
}

function buildGlobalKnowledgeContext(query) {
    const chunks = retrieveRelevantChunksFromAllKnowledge(query, 12);
    const names = [...new Set(chunks.map(chunk => chunk.sourcePath || chunk.documentTitle))];
    const documentCount = allDocuments().length;
    const chunkCount = totalChunks();

    const parts = [
        'BASE PESSOAL DE CONHECIMENTO DO USUÁRIO',
        `Documentos disponíveis: ${documentCount}`,
        `Trechos indexados: ${chunkCount}`,
        'A busca abaixo percorreu automaticamente todos os documentos sincronizados, sem filtro por projeto.',
    ];

    if (chunks.length) {
        parts.push('', 'TRECHOS MAIS RELEVANTES ENCONTRADOS EM TODA A BASE:');
        chunks.forEach((chunk, index) => {
            parts.push(
                '',
                `[Trecho ${index + 1} | Arquivo: ${chunk.sourcePath || chunk.documentTitle} | Coleção: ${chunk.projectName}]`,
                chunk.text
            );
        });
    }

    return {
        context: parts.join('\n').slice(0, 60000),
        usedDocuments: names,
        chunkCount: chunks.length,
        totalDocuments: documentCount,
        totalChunks: chunkCount,
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
        $("#fileProjectSelect"),
        $("#knowledgeProjectFilter"),
    ].filter(Boolean);

    selects.forEach(select => {
        const isFilter = select.id === "knowledgeProjectFilter";
        const currentValue = select.value;

        select.innerHTML = "";

        if (isFilter) {
            select.add(new Option("Todos os projetos", ""));
        } else {
            select.add(new Option("Selecione um projeto", ""));
        }

        state.projects.forEach(project => {
            select.add(new Option(project.name, project.id));
        });

        if ([...select.options].some(option => option.value === currentValue)) {
            select.value = currentValue;
        }
    });

    updateKnowledgeContextStatus();
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
                    <button type="button" data-action="knowledge">Ver arquivos</button>
                    <button type="button" data-action="edit">Editar</button>
                    <button type="button" data-action="delete" class="danger-text-btn">Excluir</button>
                </div>
            </div>
        `;

        card.querySelector('[data-action="knowledge"]').addEventListener("click", () => {
            const filter = $("#knowledgeProjectFilter");
            if (filter) {
                filter.value = project.id;
                filter.dispatchEvent(new Event("change"));
            }
            $("#knowledge")?.scrollIntoView({ behavior: "smooth" });
        });

        card.querySelector('[data-action="edit"]').addEventListener("click", () => openProjectForm(project));

        card.querySelector('[data-action="delete"]').addEventListener("click", async () => {
            if (!confirm(`Excluir o projeto "${project.name}" e todos os documentos importados nele?`)) return;
            try {
                await apiRequest(`/api/projects/${encodeURIComponent(project.id)}`, { method: "DELETE" });
                state.projects = state.projects.filter(item => item.id !== project.id);
                if (state.activeProjectId === project.id) state.activeProjectId = "";
                renderProjectDependentUI();
            } catch (error) {
                alert(`Não foi possível excluir: ${error.message}`);
            }
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

$("#projectForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const id = $("#projectId").value;
    const name = $("#projectName").value.trim();
    const description = $("#projectDescription").value.trim();
    const status = $("#projectStatus").value;
    if (!name) return;

    try {
        if (id) {
            await apiRequest(`/api/projects/${encodeURIComponent(id)}`, {
                method: "PUT",
                body: JSON.stringify({ name, description, status }),
            });
            const project = getProject(id);
            if (project) {
                project.name = name;
                project.description = description;
                project.status = status;
                project.updatedAt = new Date().toISOString();
            }
        } else {
            const project = await apiRequest("/api/projects", {
                method: "POST",
                body: JSON.stringify({ id: uid("project"), name, description, status }),
            });
            state.projects.unshift(ensureProjectShape(project));
            if (!state.activeProjectId) {
                state.activeProjectId = project.id;
                await persistActiveProject();
            }
        }
        renderProjectDependentUI();
        closeProjectForm();
    } catch (error) {
        alert(`Não foi possível salvar o projeto: ${error.message}`);
    }
});

function updateKnowledgeContextStatus() {
    const label = $("#contextStatus");
    if (!label) return;
    const documents = allDocuments().length;
    const chunks = totalChunks();
    label.textContent = documents
        ? `${documents} documento(s) e ${chunks} trecho(s) disponíveis. Toda a base será pesquisada automaticamente.`
        : "Nenhum documento sincronizado ainda. Adicione ou sincronize arquivos em C:\\agenteIA.";
}

// Upload conhecimento
let selectedKnowledgeFiles = [];
const ALLOWED_LOCAL_EXTENSIONS = new Set(["pdf","docx","xlsx","xlsm","txt","md","csv","json","xml","html","htm","log"]);

function mergeSelectedFiles(files) {
    const map = new Map(selectedKnowledgeFiles.map(file => [`${file.name}:${file.size}:${file.lastModified}`, file]));
    for (const file of files) {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        if (!ALLOWED_LOCAL_EXTENSIONS.has(ext)) continue;
        map.set(`${file.name}:${file.size}:${file.lastModified}`, file);
    }
    selectedKnowledgeFiles = [...map.values()];
    renderSelectedFilesPreview();
}

function renderSelectedFilesPreview() {
    const container = $("#selectedFilesPreview");
    if (!container) return;
    container.innerHTML = "";

    if (!selectedKnowledgeFiles.length) {
        container.innerHTML = '<span class="selected-files-empty">Nenhum arquivo local selecionado.</span>';
        return;
    }

    selectedKnowledgeFiles.forEach((file, index) => {
        const tag = document.createElement("span");
        tag.className = "selected-file-tag";
        const relative = file.webkitRelativePath || file.name;
        tag.innerHTML = `<span>${escapeText(relative)} · ${humanSize(file.size)}</span><button type="button" aria-label="Remover arquivo">×</button>`;
        tag.querySelector("button").addEventListener("click", () => {
            selectedKnowledgeFiles.splice(index, 1);
            renderSelectedFilesPreview();
        });
        container.appendChild(tag);
    });
}

$("#localFileInput")?.addEventListener("change", event => mergeSelectedFiles([...(event.target.files || [])]));
$("#localFolderInput")?.addEventListener("change", event => mergeSelectedFiles([...(event.target.files || [])]));

const localDropZone = $("#localDropZone");
["dragenter", "dragover"].forEach(name => localDropZone?.addEventListener(name, event => {
    event.preventDefault();
    localDropZone.classList.add("is-dragging");
}));
["dragleave", "drop"].forEach(name => localDropZone?.addEventListener(name, event => {
    event.preventDefault();
    localDropZone.classList.remove("is-dragging");
}));
localDropZone?.addEventListener("drop", event => mergeSelectedFiles([...(event.dataTransfer?.files || [])]));

async function importSingleFile(file, projectId) {
    const formData = new FormData();
    formData.append("file", file);
    if (file.webkitRelativePath) formData.append("relativePath", file.webkitRelativePath);
    const data = await apiRequest(`/api/projects/${encodeURIComponent(projectId)}/documents`, {
        method: "POST",
        body: formData,
    });
    const project = getProject(projectId);
    if (!project) throw new Error("Projeto não encontrado.");
    project.documents = project.documents || [];
    project.documents.unshift(data);
    project.updatedAt = new Date().toISOString();
}

$("#importLocalFileBtn")?.addEventListener("click", async () => {
    const projectId = $("#fileProjectSelect")?.value;
    const files = [...selectedKnowledgeFiles];
    const status = $("#fileImportStatus");
    const button = $("#importLocalFileBtn");

    if (!projectId) {
        status.textContent = "Selecione um projeto de destino.";
        return;
    }
    if (!files.length) {
        status.textContent = "Selecione arquivos ou uma pasta da sua máquina.";
        return;
    }
    const tooLarge = files.find(file => file.size > 15 * 1024 * 1024);
    if (tooLarge) {
        status.textContent = `${tooLarge.name} ultrapassa o limite de 15 MB.`;
        return;
    }

    button.disabled = true;
    button.textContent = "Lendo arquivos locais...";
    let success = 0;
    const errors = [];

    for (const [index, file] of files.entries()) {
        const relative = file.webkitRelativePath || file.name;
        status.textContent = `Analisando ${index + 1}/${files.length}: ${relative}...`;
        try {
            await importSingleFile(file, projectId);
            success += 1;
        } catch (error) {
            errors.push(`${file.name}: ${error.message}`);
        }
    }

    renderProjectDependentUI();
    selectedKnowledgeFiles = [];
    if ($("#localFileInput")) $("#localFileInput").value = "";
    if ($("#localFolderInput")) $("#localFolderInput").value = "";
    renderSelectedFilesPreview();

    status.textContent = errors.length
        ? `${success} arquivo(s) adicionados. Falhas: ${errors.join(" | ")}`
        : `${success} arquivo(s) locais adicionados com sucesso. A IA já pode consultar esse conteúdo.`;

    button.disabled = false;
    button.textContent = "Adicionar à base local";
});


async function loadLocalFolderStatus() {
    const pathEl = $("#localFolderPath");
    const statusEl = $("#localFolderStatus");
    const button = $("#scanLocalFolderBtn");
    if (!pathEl || !statusEl || !button) return;
    try {
        const response = await fetch("/api/local-folder/status");
        const data = await response.json();
        pathEl.textContent = data.path || "C:\\agenteIA";
        if (data.available) {
            statusEl.textContent = "Pasta disponível. O agente pode indexar esse conteúdo diretamente.";
            button.disabled = false;
        } else {
            statusEl.textContent = data.mode === "cloud"
                ? "Versão online: use o sincronizador local para enviar C:\\agenteIA para a rede."
                : "Pasta ainda não encontrada. Crie C:\\agenteIA ou configure LOCAL_KNOWLEDGE_DIR.";
            button.disabled = true;
        }
    } catch {
        statusEl.textContent = "Não foi possível verificar a pasta local.";
        button.disabled = true;
    }
}

$("#scanLocalFolderBtn")?.addEventListener("click", async () => {
    const button = $("#scanLocalFolderBtn");
    const status = $("#localFolderStatus");
    button.disabled = true;
    button.textContent = "Analisando pasta...";
    status.textContent = "Lendo arquivos e atualizando a base de conhecimento...";
    try {
        const data = await apiRequest("/api/local-folder/scan", { method: "POST" });
        status.textContent = `${data.imported} arquivo(s) indexados em ${data.folder}.` + (data.failures?.length ? ` ${data.failures.length} falha(s).` : "");
        await loadInitialState();
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.textContent = "Ler C:\\agenteIA agora";
        await loadLocalFolderStatus();
    }
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

        card.querySelector('[data-action="knowledge"]').addEventListener("click", () => {
            const filter = $("#knowledgeProjectFilter");
            if (filter) {
                filter.value = project.id;
                filter.dispatchEvent(new Event("change"));
            }
            $("#knowledge")?.scrollIntoView({ behavior: "smooth" });
        });

        card.querySelector('[data-action="delete"]').addEventListener("click", async () => {
            if (!confirm(`Excluir "${document.title}" da base de conhecimento?`)) return;
            try {
                await apiRequest(`/api/documents/${encodeURIComponent(document.id)}`, { method: "DELETE" });
                project.documents = (project.documents || []).filter(item => item.id !== document.id);
                project.updatedAt = new Date().toISOString();
                renderProjectDependentUI();
            } catch (error) {
                alert(`Não foi possível excluir: ${error.message}`);
            }
        });

        grid.appendChild(card);
    });
}

$("#knowledgeProjectFilter")?.addEventListener("change", renderKnowledgeDocuments);
$("#knowledgeSearch")?.addEventListener("input", renderKnowledgeDocuments);

// Chat
const chatWindow = $("#chatWindow");
const chatInput = $("#chatInput");
const chatSendBtn = $("#chatSendBtn");
let chatBusy = false;
let thinkingTimer = null;
let thinkingStartedAt = 0;

function scrollChat() {
    if (chatWindow) chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setAiActivity(mode, title, detail = "") {
    const strip = $("#aiActivityStrip");
    const titleEl = $("#aiActivityTitle");
    const detailEl = $("#aiActivityDetail");
    if (!strip || !titleEl || !detailEl) return;
    strip.dataset.mode = mode;
    titleEl.textContent = title;
    detailEl.textContent = detail;
}

function startThinkingActivity(hasProject, documentCount) {
    thinkingStartedAt = Date.now();
    setAiActivity(
        "thinking",
        "Alexandre AI está pensando",
        hasProject ? `Analisando contexto e ${documentCount} arquivo(s) relevante(s)...` : "Interpretando sua pergunta e preparando a resposta..."
    );
    clearInterval(thinkingTimer);
    thinkingTimer = setInterval(() => {
        const seconds = Math.floor((Date.now() - thinkingStartedAt) / 1000);
        const elapsed = $("#aiElapsed");
        if (elapsed) elapsed.textContent = `${seconds}s`;
        if (seconds >= 3 && seconds < 7) setAiActivity("thinking", "Consultando conhecimento", "Buscando os trechos mais úteis para responder com contexto.");
        if (seconds >= 7) setAiActivity("thinking", "Gerando resposta", "Organizando a resposta final para você.");
    }, 500);
}

function stopThinkingActivity(detail = "Resposta concluída") {
    clearInterval(thinkingTimer);
    thinkingTimer = null;
    const elapsed = $("#aiElapsed");
    if (elapsed) elapsed.textContent = "";
    setAiActivity("ready", "Agente pronto", detail);
}

function addThinkingBubble() {
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant-message thinking-message";
    wrapper.id = "activeThinkingBubble";
    wrapper.innerHTML = `
        <div class="message-avatar ai-avatar-live">AI</div>
        <div class="message-bubble thinking-bubble">
            <span class="thinking-label">Pensando</span>
            <span class="thinking-dots"><i></i><i></i><i></i></span>
        </div>`;
    chatWindow.appendChild(wrapper);
    scrollChat();
}

function removeThinkingBubble() {
    $("#activeThinkingBubble")?.remove();
}

function appendMessage(text, type, persist = true, provider = "", documents = [], animate = false) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${type === "user" ? "user-message" : "assistant-message"}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = type === "user" ? "A" : "AI";

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    const textEl = document.createElement("div");
    textEl.className = "message-text";
    bubble.appendChild(textEl);

    if (!animate) textEl.textContent = text;

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
    scrollChat();

    if (animate) {
        const chars = [...text];
        const step = Math.max(1, Math.ceil(chars.length / 220));
        let cursor = 0;
        const timer = setInterval(() => {
            cursor = Math.min(chars.length, cursor + step);
            textEl.textContent = chars.slice(0, cursor).join("");
            scrollChat();
            if (cursor >= chars.length) clearInterval(timer);
        }, 12);
    }

    if (persist) {
        const item = { text, type, provider, documents, ts: Date.now() };
        state.chat.push(item);
        state.chat = state.chat.slice(-500);
        apiRequest("/api/chat", { method: "POST", body: JSON.stringify(item) })
            .catch(error => console.error("Falha ao persistir conversa:", error));
    }
}

function renderDefaultAssistant() {
    chatWindow.innerHTML = "";
    appendMessage(
        "Olá, Alexandre. Minha busca agora percorre automaticamente toda a sua base de conhecimento sincronizada. Pergunte sobre seus documentos e eu vou localizar os trechos mais relevantes antes de responder.",
        "assistant",
        false
    );
}

function loadChat() {
    const history = getChatHistory();
    if (!history.length) return renderDefaultAssistant();
    chatWindow.innerHTML = "";
    history.forEach(item => appendMessage(item.text, item.type, false, item.provider || "", item.documents || []));
}

async function loadKnowledgeStatus() {
    try {
        const data = await apiRequest("/api/knowledge/status");
        const status = $("#contextStatus");
        if (!status) return;
        if (!data.documents) {
            status.textContent = "Nenhum documento sincronizado ainda. O Agente Local sincronizará C:\\agenteIA automaticamente.";
            return;
        }
        const syncText = data.lastSync ? ` · última sincronização ${formatDate(data.lastSync)}` : "";
        const monitor = data.localAgent || {};
        const monitorText = monitor.online ? " · Agente Local online" : " · Agente Local offline";
        status.textContent = `${data.documents} documento(s) · ${data.chunks} trecho(s) disponíveis${syncText}${monitorText}. Busca global automática ativa.`;
    } catch (error) {
        console.warn("Não foi possível atualizar o status da base:", error);
    }
}

async function loadAgentStatus() {
    const status = $("#agentStatus");
    try {
        const data = await apiRequest("/api/agent/status");
        if (!data.configured?.length) {
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
    if (!message || chatBusy) return;
    chatBusy = true;
    chatSendBtn?.classList.add("is-loading");
    if (chatSendBtn) chatSendBtn.disabled = true;
    if (chatInput) chatInput.disabled = true;

    appendMessage(message, "user");
    chatInput.value = "";
    chatInput.style.height = "auto";

    const indicator = $("#retrievalIndicator");
    indicator?.classList.add("retrieval-active");
    if (indicator) {
        indicator.querySelector("strong").textContent = "Pesquisando toda a base pessoal...";
        indicator.querySelector("small").textContent = "Consultando automaticamente todos os arquivos sincronizados e importados.";
    }

    const history = getChatHistory().slice(-16).map(item => ({
        role: item.type === "assistant" ? "assistant" : "user",
        content: item.text,
    }));

    startThinkingActivity(true, 0);
    addThinkingBubble();

    try {
        const data = await apiRequest("/api/agent", {
            method: "POST",
            body: JSON.stringify({ message, history }),
        });

        const usedDocuments = Array.isArray(data.usedDocuments) ? data.usedDocuments : [];
        if (indicator) {
            indicator.querySelector("strong").textContent = `Busca global concluída: ${data.retrievalCount || 0} trecho(s) relevante(s)`;
            indicator.querySelector("small").textContent = usedDocuments.length
                ? `Arquivos usados: ${usedDocuments.join(", ")}`
                : `A base possui ${data.totalDocuments || 0} documento(s), mas nenhum trecho relevante foi encontrado para esta pergunta.`;
        }

        removeThinkingBubble();
        const providerLabel = `${data.provider} · ${data.model}`;
        appendMessage(data.reply, "assistant", true, providerLabel, usedDocuments, true);
        await addSearchHistory(message, "", providerLabel, usedDocuments);
        stopThinkingActivity(`Resposta concluída via ${data.provider}.`);
        loadKnowledgeStatus();
    } catch (error) {
        removeThinkingBubble();
        appendMessage(`Erro: ${error.message}`, "assistant");
        await addSearchHistory(message, "", "Erro", []);
        stopThinkingActivity("Não foi possível concluir a resposta.");
    } finally {
        chatBusy = false;
        chatSendBtn?.classList.remove("is-loading");
        if (chatSendBtn) chatSendBtn.disabled = false;
        if (chatInput) {
            chatInput.disabled = false;
            chatInput.focus();
        }
    }
}

$("#chatForm")?.addEventListener("submit", event => { event.preventDefault(); sendMessage(chatInput.value); });
chatInput?.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("#chatForm")?.requestSubmit(); }
});
chatInput?.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 150)}px`;
});
$$('[data-prompt]').forEach(button => button.addEventListener("click", () => sendMessage(button.dataset.prompt || "")));

$("#clearChatBtn")?.addEventListener("click", async () => {
    if (!confirm("Limpar a conversa atual? O histórico de pesquisas continuará disponível.")) return;
    try {
        await apiRequest("/api/chat", { method: "DELETE" });
        state.chat = [];
        renderDefaultAssistant();
        stopThinkingActivity("Conversa limpa. Pronto para uma nova pergunta.");
    } catch (error) {
        alert(`Não foi possível limpar a conversa: ${error.message}`);
    }
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

            $("#agent")?.scrollIntoView({ behavior: "smooth" });
            chatInput.focus();
        });

        row.querySelector(".history-delete-btn").addEventListener("click", async () => {
            try {
                await apiRequest(`/api/history?id=${encodeURIComponent(item.id)}`, { method: "DELETE" });
                state.history = state.history.filter(historyItem => historyItem.id !== item.id);
                renderHistory();
                updateStats();
            } catch (error) {
                alert(`Não foi possível excluir: ${error.message}`);
            }
        });

        list.appendChild(row);
    });
}

$("#historySearch")?.addEventListener("input", renderHistory);

$("#clearHistoryBtn")?.addEventListener("click", async () => {
    if (!confirm("Apagar todo o histórico de pesquisas salvo no banco?")) return;
    try {
        await apiRequest("/api/history", { method: "DELETE" });
        state.history = [];
        renderHistory();
        updateStats();
    } catch (error) {
        alert(`Não foi possível apagar o histórico: ${error.message}`);
    }
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

        await apiRequest("/api/backup/import", { method: "POST", body: JSON.stringify(data) });
        await loadInitialState();
        $("#backupStatus").textContent = "Backup restaurado no armazenamento local com sucesso.";
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

async function migrateLegacyLocalStorageIfNeeded(serverState) {
    if (serverState.projects?.length || serverState.chat?.length || serverState.searchHistory?.length) return serverState;
    try {
        const projects = JSON.parse(localStorage.getItem(LEGACY_STORAGE.projects) || "[]");
        const chat = JSON.parse(localStorage.getItem(LEGACY_STORAGE.chat) || "[]");
        const searchHistory = JSON.parse(localStorage.getItem(LEGACY_STORAGE.history) || "[]");
        const activeProjectId = localStorage.getItem(LEGACY_STORAGE.activeProject) || "";
        if (!projects.length && !chat.length && !searchHistory.length) return serverState;
        const legacy = { projects, chat, searchHistory, activeProjectId };
        await apiRequest("/api/state/import", { method: "POST", body: JSON.stringify(legacy) });
        Object.values(LEGACY_STORAGE).forEach(key => localStorage.removeItem(key));
        return await apiRequest("/api/state");
    } catch (error) {
        console.warn("Migração automática do localStorage não concluída:", error);
        return serverState;
    }
}

async function loadInitialState() {
    try {
        let data = await apiRequest("/api/state");
        data = await migrateLegacyLocalStorageIfNeeded(data);
        state.projects = (data.projects || []).map(ensureProjectShape);
        state.chat = Array.isArray(data.chat) ? data.chat : [];
        state.history = Array.isArray(data.searchHistory) ? data.searchHistory : [];
        state.activeProjectId = data.activeProjectId || "";
        renderProjectDependentUI();
        renderSelectedFilesPreview();
        loadChat();
        renderHistory();
    } catch (error) {
        console.error(error);
        const status = $("#backupStatus");
        if (status) status.textContent = `Armazenamento indisponível: ${error.message}`;
        renderProjectDependentUI();
        renderDefaultAssistant();
        renderHistory();
    }
}

loadInitialState();
loadAgentStatus();
loadKnowledgeStatus();


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

loadLocalFolderStatus();

setInterval(() => { if (!document.hidden) loadKnowledgeStatus(); }, 30000);

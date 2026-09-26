import base64
import hashlib
import hmac
import io
import logging
import os
import re
import time
import uuid
from datetime import timedelta
from pathlib import Path

import pyotp
import qrcode
import requests
from docx import Document
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from openpyxl import load_workbook
from pypdf import PdfReader

from storage import (
    add_chat_message, add_history, clear_chat, create_project, storage_configured,
    delete_document, delete_document_by_source, delete_history, delete_project, init_storage, insert_document,
    load_state, replace_state, set_active_project, update_project,
)

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alexandre-ai")

app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-me"),
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    MAX_CONTENT_LENGTH=15 * 1024 * 1024,
)

if os.getenv("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = True

csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"

try:
    init_storage()
except Exception as exc:
    logger.exception("Não foi possível inicializar o armazenamento local: %s", exc)


SYSTEM_PROMPT = """Você é Alexandre AI, o assistente pessoal de Alexandre.
Responda sempre em português do Brasil, salvo se o usuário pedir outro idioma.
Seja claro, objetivo, técnico quando necessário e útil.

Você pode receber CONTEXTO PRIVADO DA BASE PESSOAL com trechos selecionados automaticamente de todos os documentos sincronizados do usuário.
Use esse conteúdo como fonte primária quando a pergunta puder ser respondida pelos documentos.
A pesquisa não depende da seleção de projeto e pode combinar informações de arquivos diferentes.
Nunca invente informações ausentes no contexto.
Quando utilizar um documento, mencione naturalmente o nome do arquivo quando isso ajudar.
Se o contexto for insuficiente, diga o que falta.
"""

PREAUTH_TTL_SECONDS = 300
MAX_MFA_ATTEMPTS = 5


class GeminiHTTPError(RuntimeError):
    """Erro HTTP do Gemini preservando status e indicação de retry."""
    def __init__(self, status_code, detail, retry_after=None):
        self.status_code = int(status_code)
        self.detail = str(detail)
        self.retry_after = retry_after
        self.retryable = self.status_code in {429, 503}
        super().__init__(f"Gemini retornou HTTP {self.status_code}: {self.detail}")


SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".log", ".xml", ".html", ".htm",
}
SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xlsm",
}
SUPPORTED_EXTENSIONS = SUPPORTED_TEXT_EXTENSIONS | SUPPORTED_DOCUMENT_EXTENSIONS


class EnvUser(UserMixin):
    def __init__(self):
        self.id = "admin"
        self.name = os.getenv("ADMIN_NAME", "Alexandre")
        self.email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        self.role = "admin"


def get_admin_user():
    return EnvUser()


@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return get_admin_user()
    return None


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "sim"}


def mfa_enabled():
    return env_bool("MFA_ENABLED", False)


def mfa_setup_enabled():
    return env_bool("MFA_SETUP_ENABLED", False)


def mfa_secret():
    source = app.config["SECRET_KEY"]
    digest = hmac.new(
        str(source).encode("utf-8"),
        b"alexandre-ai-mfa-v1",
        hashlib.sha256,
    ).digest()
    return base64.b32encode(digest).decode("ascii").rstrip("=")


def mfa_totp():
    return pyotp.TOTP(mfa_secret(), digits=6, interval=30)


def mfa_uri():
    user = get_admin_user()
    account_name = user.email or "Alexandre"
    return mfa_totp().provisioning_uri(
        name=account_name,
        issuer_name="Alexandre AI",
    )


def qr_data_uri(text):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def start_preauth(remember):
    session["preauth"] = True
    session["preauth_at"] = int(time.time())
    session["remember_after_mfa"] = bool(remember)
    session["mfa_attempts"] = 0


def clear_preauth():
    for key in ("preauth", "preauth_at", "remember_after_mfa", "mfa_attempts"):
        session.pop(key, None)


def preauth_valid():
    if not session.get("preauth"):
        return False

    try:
        age = time.time() - float(session.get("preauth_at", 0))
    except (TypeError, ValueError):
        return False

    return 0 <= age <= PREAUTH_TTL_SECONDS


def finish_login():
    remember = bool(session.get("remember_after_mfa"))
    login_user(get_admin_user(), remember=remember)
    clear_preauth()


def normalize_text(text, max_chars=200000):
    text = (text or "").replace("\x00", "")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()[:max_chars]


def split_text_chunks(text, filename, chunk_size=2400, overlap=350):
    text = normalize_text(text)
    if not text:
        return []

    chunks = []
    cursor = 0
    index = 1

    while cursor < len(text):
        end = min(len(text), cursor + chunk_size)
        piece = text[cursor:end]

        if end < len(text):
            natural_break = max(
                piece.rfind("\n\n"),
                piece.rfind(". "),
                piece.rfind("\n"),
            )
            if natural_break > chunk_size * 0.55:
                end = cursor + natural_break + 1
                piece = text[cursor:end]

        piece = piece.strip()
        if piece:
            chunks.append({
                "id": f"chunk_{index}",
                "index": index,
                "filename": filename,
                "text": piece,
            })

        if end >= len(text):
            break

        cursor = max(cursor + 1, end - overlap)
        index += 1

    return chunks[:180]


def extract_pdf_with_gemini(pdf_bytes, filename="documento.pdf"):
    """Fallback visual para PDFs escaneados/imagem usando somente Gemini."""
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(
            "O PDF parece ser escaneado e não possui texto pesquisável. "
            "Configure GEMINI_API_KEY para permitir a leitura visual do documento."
        )

    model = (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "text": (
                        "Leia visualmente este PDF como um documento privado do usuário. "
                        "Transcreva todo o texto legível com fidelidade, preservando nomes, "
                        "instituições, curso, datas, títulos, números e demais informações relevantes. "
                        "Não resuma e não invente nada. Se houver um diploma ou certificado, "
                        "registre explicitamente o nome da pessoa, o curso/formação, a instituição "
                        "e a data quando estiverem visíveis. Documento: " + filename
                    )
                },
                {
                    "inlineData": {
                        "mimeType": "application/pdf",
                        "data": base64.b64encode(pdf_bytes).decode("ascii"),
                    }
                },
            ],
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 8192,
        },
    }

    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=90,
    )
    if not response.ok:
        detail = response.text[:500]
        raise ValueError(f"Falha na leitura visual do PDF pelo Gemini ({response.status_code}): {detail}")

    data = response.json()
    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    text = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict))
    text = normalize_text(text)
    if not text:
        raise ValueError("O Gemini não conseguiu identificar texto legível neste PDF.")
    return "[Leitura visual do PDF pelo Gemini]\n" + text


def extract_pdf(file_obj, filename="documento.pdf"):
    # Lê os bytes uma única vez para permitir extração tradicional + fallback visual.
    pdf_bytes = file_obj.read()
    if not pdf_bytes:
        return ""

    parts = []
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for idx, page in enumerate(reader.pages[:100], start=1):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(f"[Página {idx}]\n{text}")
    except Exception as exc:
        logger.warning("Falha na extração textual do PDF %s: %s", filename, str(exc)[:300])

    extracted = normalize_text("\n\n".join(parts))

    # Diplomas, certificados e documentos digitalizados costumam ser apenas imagens.
    # Se quase nenhum texto foi encontrado, o próprio Gemini faz a leitura visual.
    if len(extracted.strip()) < 120:
        logger.info("PDF sem texto pesquisável suficiente; acionando leitura visual Gemini: %s", filename)
        return extract_pdf_with_gemini(pdf_bytes, filename)

    return extracted


def extract_docx(file_obj):
    document = Document(file_obj)
    parts = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text.strip())

    for table in document.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells]
            if any(values):
                parts.append(" | ".join(values))

    return normalize_text("\n".join(parts))


def extract_xlsx(file_obj):
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    parts = []

    for sheet in workbook.worksheets[:25]:
        parts.append(f"[Planilha: {sheet.title}]")
        included = 0

        for row in sheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(value.strip() for value in values):
                parts.append(" | ".join(values))
                included += 1

            if included >= 2500:
                parts.append("[Conteúdo truncado nesta planilha]")
                break

    return normalize_text("\n".join(parts))


def extract_text_file(file_obj):
    data = file_obj.read()
    if isinstance(data, bytes):
        return normalize_text(data.decode("utf-8", errors="replace"))
    return normalize_text(str(data))


def extract_file_content(file_obj, filename):
    suffix = Path(filename or "").suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Formato não suportado. Use PDF, DOCX, XLSX, TXT, MD, CSV, JSON, XML, HTML ou LOG."
        )

    if suffix == ".pdf":
        return extract_pdf(file_obj, filename)
    if suffix == ".docx":
        return extract_docx(file_obj)
    if suffix in {".xlsx", ".xlsm"}:
        return extract_xlsx(file_obj)

    return extract_text_file(file_obj)


def sanitize_history(raw_history):
    clean = []
    if not isinstance(raw_history, list):
        return clean

    for item in raw_history[-16:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role") or item.get("type")
        content = item.get("content") or item.get("text")

        if role == "assistant":
            normalized_role = "assistant"
        elif role == "user":
            normalized_role = "user"
        else:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()
        if content:
            clean.append({
                "role": normalized_role,
                "content": content[:12000],
            })

    return clean


def sanitize_project_context(raw_context):
    if not isinstance(raw_context, str):
        return ""
    return normalize_text(raw_context, max_chars=52000)


_SEARCH_STOPWORDS = {
    "de", "da", "do", "das", "dos", "a", "o", "as", "os", "e", "em", "para", "por", "com",
    "um", "uma", "que", "se", "no", "na", "nos", "nas", "ao", "aos", "como", "mais", "menos",
    "sobre", "qual", "quais", "me", "meu", "minha", "meus", "minhas", "este", "esta", "esse",
    "essa", "isso", "isto", "ser", "tem", "ter", "foi", "sao", "the", "and", "of", "to", "in",
}


def _search_tokens(text):
    normalized = normalize_text(str(text or ""), max_chars=12000).lower()
    return [token for token in re.findall(r"[a-zA-Z0-9À-ÿ]+", normalized) if len(token) >= 3 and token not in _SEARCH_STOPWORDS]


def build_global_knowledge_context(owner_id, query, limit=12):
    state = load_state(owner_id)
    tokens = _search_tokens(query)
    normalized_query = normalize_text(query, max_chars=2000).lower()
    scored = []
    total_documents = 0
    total_chunks = 0

    for project in state.get("projects", []):
        for document in project.get("documents") or []:
            total_documents += 1
            title = str(document.get("title") or "Documento")
            source_path = str(document.get("sourcePath") or "")
            metadata = f"{title} {source_path}".lower()
            chunks = document.get("chunks") or []
            total_chunks += len(chunks)
            for chunk in chunks:
                text = str(chunk.get("text") or "").strip()
                if not text:
                    continue
                haystack = text.lower()
                score = 0
                for token in tokens:
                    score += haystack.count(token)
                    if token in metadata:
                        score += 4
                if normalized_query and len(normalized_query) >= 8 and normalized_query in haystack:
                    score += 12
                if not tokens and text:
                    score = 1
                if score > 0:
                    scored.append((score, title, source_path, text))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = scored[:limit]
    context_parts = []
    used_documents = []
    for _, title, source_path, text in selected:
        label = source_path or title
        if label not in used_documents:
            used_documents.append(label)
        context_parts.append(f"ARQUIVO: {label}\n{text}")

    context = "\n\n---\n\n".join(context_parts)
    context = normalize_text(context, max_chars=52000)
    return {
        "context": context,
        "usedDocuments": used_documents,
        "chunkCount": len(selected),
        "totalDocuments": total_documents,
        "totalChunks": total_chunks,
    }


def provider_configurations():
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not gemini_key:
        return []
    return [{
        "name": "Gemini",
        "model": (os.getenv("GEMINI_MODEL") or "gemini-3.8-flash").strip(),
    }]


def _gemini_error_message(response):
    try:
        payload = response.json()
        error = payload.get("error") or {}
        message = error.get("message") if isinstance(error, dict) else None
        if message:
            return str(message)
    except Exception:
        pass
    body = (response.text or "").strip().replace("\n", " ")
    return body[:500] or f"HTTP {response.status_code}"


def _retry_after_seconds(response):
    value = (response.headers.get("Retry-After") or "").strip()
    if not value:
        return None
    try:
        return max(0, min(int(float(value)), 120))
    except (TypeError, ValueError):
        return None


def ask_with_gemini(messages):
    providers = provider_configurations()
    if not providers:
        raise RuntimeError("Gemini não está configurado. Defina GEMINI_API_KEY.")

    provider = providers[0]
    model = provider["model"]
    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    logger.info("Tentando provedor=Gemini modelo=%s via API nativa", model)

    system_parts = []
    contents = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_parts.append(content)
            continue
        contents.append({
            "role": "model" if role == "assistant" else "user",
            "parts": [{"text": content}],
        })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 1800,
        },
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        response = requests.post(url, params={"key": api_key}, json=payload, timeout=60)
    except requests.RequestException as exc:
        logger.warning("Falha de conexão com Gemini: %s", exc)
        raise RuntimeError(f"Falha de conexão com o Gemini: {exc}") from exc

    if not response.ok:
        detail = _gemini_error_message(response)
        logger.warning("Gemini HTTP %s: %s", response.status_code, detail[:500])
        raise GeminiHTTPError(
            response.status_code,
            detail,
            retry_after=_retry_after_seconds(response),
        )

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Gemini respondeu em formato não JSON: %s", (response.text or "")[:300])
        raise RuntimeError("O Gemini respondeu em formato inválido.") from exc

    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    content = "\n".join(str(part.get("text") or "") for part in parts if part.get("text")).strip()
    if not content:
        block_reason = ((data.get("promptFeedback") or {}).get("blockReason") or "").strip()
        if block_reason:
            raise RuntimeError(f"O Gemini bloqueou a solicitação: {block_reason}.")
        raise RuntimeError("O Gemini retornou uma resposta vazia.")

    return {"reply": content, "provider": "Gemini", "model": model}


@app.errorhandler(CSRFError)
def handle_csrf_error(exc):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Sessão ou token de segurança expirado. Atualize a página e tente novamente."}), 400
    return str(exc), 400


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "Sua sessão expirou. Faça login novamente."}), 401
    return redirect(url_for("login"))


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        email_ok = bool(admin_email) and hmac.compare_digest(email, admin_email)
        password_ok = bool(admin_password) and hmac.compare_digest(password, admin_password)

        if email_ok and password_ok:
            if mfa_enabled():
                start_preauth(remember)
                return redirect(url_for("mfa_challenge"))

            login_user(get_admin_user(), remember=remember)
            return redirect(url_for("dashboard"))

        error = "E-mail ou senha inválidos."

    return render_template("login.html", error=error, mfa_enabled=mfa_enabled())


@app.route("/mfa", methods=["GET", "POST"])
def mfa_challenge():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if not mfa_enabled():
        return redirect(url_for("login"))

    if not preauth_valid():
        clear_preauth()
        return redirect(url_for("login"))

    error = None

    if request.method == "POST":
        attempts = int(session.get("mfa_attempts", 0))
        if attempts >= MAX_MFA_ATTEMPTS:
            clear_preauth()
            return redirect(url_for("login"))

        code = "".join(ch for ch in request.form.get("code", "") if ch.isdigit())

        if len(code) == 6 and mfa_totp().verify(code, valid_window=1):
            finish_login()
            return redirect(url_for("dashboard"))

        attempts += 1
        session["mfa_attempts"] = attempts

        if attempts >= MAX_MFA_ATTEMPTS:
            clear_preauth()
            return render_template(
                "mfa.html",
                error="Limite de tentativas atingido. Faça o login novamente.",
                setup_enabled=False,
                locked=True,
            )

        error = f"Código inválido. Restam {MAX_MFA_ATTEMPTS - attempts} tentativa(s)."

    return render_template(
        "mfa.html",
        error=error,
        setup_enabled=mfa_setup_enabled(),
        locked=False,
    )


@app.route("/mfa/setup", methods=["GET", "POST"])
def mfa_setup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if not mfa_enabled() or not mfa_setup_enabled():
        return redirect(url_for("mfa_challenge"))

    if not preauth_valid():
        clear_preauth()
        return redirect(url_for("login"))

    error = None

    if request.method == "POST":
        code = "".join(ch for ch in request.form.get("code", "") if ch.isdigit())

        if len(code) == 6 and mfa_totp().verify(code, valid_window=1):
            finish_login()
            return redirect(url_for("dashboard"))

        error = "Código inválido. Confira o relógio do celular e tente novamente."

    return render_template(
        "mfa_setup.html",
        error=error,
        qr_data=qr_data_uri(mfa_uri()),
        manual_key=mfa_secret(),
        account_email=get_admin_user().email,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        user=current_user,
        mfa_enabled=mfa_enabled(),
    )


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    clear_preauth()
    return redirect(url_for("login"))


@app.route("/api/files/extract", methods=["POST"])
@login_required
def extract_uploaded_file():
    """Mantido para compatibilidade; extrai sem persistir."""
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Selecione um arquivo."}), 400
    try:
        text = extract_file_content(uploaded.stream, uploaded.filename)
        if not text:
            return jsonify({"error": "O arquivo não possui texto legível para importar."}), 400
        chunks = split_text_chunks(text, uploaded.filename)
        return jsonify({
            "title": uploaded.filename,
            "content": text,
            "chunks": chunks,
            "sourceType": "local_file",
            "characters": len(text),
            "chunkCount": len(chunks),
            "size": request.content_length or 0,
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Erro ao extrair arquivo")
        return jsonify({"error": f"Não foi possível ler o arquivo: {str(exc)[:160]}"}), 400


def _owner_id():
    return str(current_user.get_id())


def _storage_error(exc):
    logger.exception("Erro de armazenamento local")
    return jsonify({"error": f"Falha no armazenamento local: {str(exc)[:180]}"}), 500


def _ensure_project(owner_id, name="Conhecimento Local", description="Arquivos sincronizados da pasta local do computador."):
    state = load_state(owner_id)
    for project in state.get("projects", []):
        if str(project.get("name") or "").strip().lower() == name.strip().lower():
            return project
    return create_project(owner_id, {
        "id": f"project_{uuid.uuid4()}",
        "name": name,
        "description": description,
        "status": "Ativo",
    })


def _replace_source_document(owner_id, project_id, document):
    state = load_state(owner_id)
    source_path = str(document.get("sourcePath") or "")
    for project in state.get("projects", []):
        if project.get("id") != project_id:
            continue
        for current in list(project.get("documents") or []):
            same_source = source_path and str(current.get("sourcePath") or "") == source_path
            same_title = not source_path and current.get("title") == document.get("title")
            if same_source or same_title:
                delete_document(owner_id, current.get("id"))
    return insert_document(owner_id, project_id, document)


def _document_from_stream(file_obj, filename, size=0, source_path="", source_mtime=None):
    text = extract_file_content(file_obj, filename)
    if not text:
        raise ValueError("O arquivo não possui texto legível para importar.")
    chunks = split_text_chunks(text, filename)
    document = {
        "id": f"doc_{uuid.uuid4()}",
        "title": filename,
        "size": int(size or 0),
        "characters": len(text),
        "chunks": chunks,
        "sourceType": "local_folder" if source_path else "uploaded_file",
    }
    if source_path:
        document["sourcePath"] = source_path
    if source_mtime is not None:
        document["sourceMtime"] = source_mtime
    return document


def _configured_local_dir():
    raw = (os.getenv("LOCAL_KNOWLEDGE_DIR") or "").strip()
    if raw:
        return Path(raw)
    if os.name == "nt":
        return Path(r"C:\agenteIA")
    return None


@app.route("/api/local-folder/status")
@login_required
def api_local_folder_status():
    folder = _configured_local_dir()
    available = bool(folder and folder.exists() and folder.is_dir())
    return jsonify({
        "configured": bool(folder),
        "available": available,
        "path": str(folder) if folder else "C:\\agenteIA (somente quando executado no Windows)",
        "mode": "local" if os.name == "nt" else "cloud",
    })


@app.route("/api/local-folder/scan", methods=["POST"])
@login_required
def api_local_folder_scan():
    folder = _configured_local_dir()
    if not folder or not folder.exists() or not folder.is_dir():
        return jsonify({
            "error": "A pasta local não está disponível neste servidor. No Windows, crie C:\\agenteIA ou configure LOCAL_KNOWLEDGE_DIR."
        }), 400

    owner_id = _owner_id()
    project = _ensure_project(owner_id)
    success = 0
    skipped = 0
    failures = []

    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > app.config["MAX_CONTENT_LENGTH"]:
                skipped += 1
                continue
            relative = str(path.relative_to(folder)).replace("\\", "/")
            with path.open("rb") as handle:
                document = _document_from_stream(
                    handle, relative, size=path.stat().st_size,
                    source_path=relative, source_mtime=path.stat().st_mtime,
                )
            _replace_source_document(owner_id, project["id"], document)
            success += 1
        except Exception as exc:
            failures.append(f"{path.name}: {str(exc)[:120]}")

    return jsonify({
        "ok": True,
        "projectId": project["id"],
        "projectName": project["name"],
        "folder": str(folder),
        "imported": success,
        "skipped": skipped,
        "failures": failures[:20],
    })


@app.route("/api/sync/local-file", methods=["POST"])
@csrf.exempt
def api_sync_local_file():
    expected = (os.getenv("SYNC_TOKEN") or "").strip()
    provided = (request.headers.get("X-Sync-Token") or "").strip()
    if not expected or not hmac.compare_digest(expected, provided):
        return jsonify({"error": "Token de sincronização inválido."}), 401

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Arquivo ausente."}), 400

    relative_path = str(request.form.get("relativePath") or uploaded.filename).replace("\\", "/")[:1000]
    project_name = str(request.form.get("projectName") or "Conhecimento Local")[:200]
    source_mtime = request.form.get("sourceMtime")
    try:
        source_mtime = float(source_mtime) if source_mtime not in (None, "") else None
    except ValueError:
        source_mtime = None

    try:
        owner_id = "admin"
        project = _ensure_project(owner_id, project_name)
        document = _document_from_stream(
            uploaded.stream, relative_path,
            size=request.content_length or 0,
            source_path=relative_path, source_mtime=source_mtime,
        )
        saved = _replace_source_document(owner_id, project["id"], document)
        return jsonify({"ok": True, "projectId": project["id"], "document": saved}), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/sync/delete", methods=["POST"])
@csrf.exempt
def api_sync_delete():
    expected = (os.getenv("SYNC_TOKEN") or "").strip()
    provided = (request.headers.get("X-Sync-Token") or "").strip()
    if not expected or not hmac.compare_digest(expected, provided):
        return jsonify({"error": "Token de sincronização inválido."}), 401
    data = request.get_json(silent=True) or {}
    relative_path = str(data.get("relativePath") or "").replace("\\", "/")[:1000]
    if not relative_path:
        return jsonify({"error": "relativePath ausente."}), 400
    removed = delete_document_by_source("admin", relative_path)
    return jsonify({"ok": True, "removed": removed, "relativePath": relative_path})


@app.route("/api/sync/heartbeat", methods=["POST"])
@csrf.exempt
def api_sync_heartbeat():
    expected = (os.getenv("SYNC_TOKEN") or "").strip()
    provided = (request.headers.get("X-Sync-Token") or "").strip()
    if not expected or not hmac.compare_digest(expected, provided):
        return jsonify({"error": "Token de sincronização inválido."}), 401
    data = request.get_json(silent=True) or {}
    payload = {
        "lastSeen": time.time(),
        "computer": str(data.get("computer") or "")[:120],
        "folder": str(data.get("folder") or r"C:\agenteIA")[:500],
        "status": str(data.get("status") or "online")[:40],
        "pending": int(data.get("pending") or 0),
        "synced": int(data.get("synced") or 0),
        "errors": int(data.get("errors") or 0),
        "detectedFiles": int(data.get("detectedFiles") or 0),
    }
    app.config["LOCAL_AGENT_HEARTBEAT"] = payload
    return jsonify({"ok": True})


@app.route("/api/state")
@login_required
def api_state():
    try:
        return jsonify(load_state(_owner_id()))
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/state/import", methods=["POST"])
@login_required
def api_state_import():
    try:
        replace_state(_owner_id(), request.get_json(silent=True) or {})
        return jsonify({"ok": True})
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/projects", methods=["POST"])
@login_required
def api_projects_create():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Informe o nome do projeto."}), 400
    project = {
        "id": str(data.get("id") or f"project_{uuid.uuid4()}"),
        "name": name[:200],
        "description": str(data.get("description") or "")[:10000],
        "status": str(data.get("status") or "Planejamento")[:100],
    }
    try:
        return jsonify(create_project(_owner_id(), project)), 201
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/projects/<project_id>", methods=["PUT", "DELETE"])
@login_required
def api_project_item(project_id):
    try:
        if request.method == "DELETE":
            delete_project(_owner_id(), project_id)
            return jsonify({"ok": True})
        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Informe o nome do projeto."}), 400
        row = update_project(_owner_id(), project_id, {
            "name": name[:200],
            "description": str(data.get("description") or "")[:10000],
            "status": str(data.get("status") or "Planejamento")[:100],
        })
        if not row:
            return jsonify({"error": "Projeto não encontrado."}), 404
        return jsonify({"ok": True, "updatedAt": row["updated_at"].isoformat()})
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/settings/active-project", methods=["PUT"])
@login_required
def api_active_project():
    data = request.get_json(silent=True) or {}
    try:
        set_active_project(_owner_id(), str(data.get("projectId") or ""))
        return jsonify({"ok": True})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/projects/<project_id>/documents", methods=["POST"])
@login_required
def api_project_document(project_id):
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Selecione um arquivo."}), 400
    try:
        relative_path = str(request.form.get("relativePath") or uploaded.filename).replace("\\", "/")[:1000]
        document = _document_from_stream(
            uploaded.stream, relative_path,
            size=request.content_length or 0,
            source_path=relative_path if request.form.get("relativePath") else "",
        )
        saved = _replace_source_document(_owner_id(), project_id, document)
        return jsonify(saved), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/documents/<document_id>", methods=["DELETE"])
@login_required
def api_document_delete(document_id):
    try:
        if not delete_document(_owner_id(), document_id):
            return jsonify({"error": "Documento não encontrado."}), 404
        return jsonify({"ok": True})
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/chat", methods=["POST", "DELETE"])
@login_required
def api_chat():
    try:
        if request.method == "DELETE":
            clear_chat(_owner_id())
            return jsonify({"ok": True})
        data = request.get_json(silent=True) or {}
        text = str(data.get("text") or "").strip()
        if not text:
            return jsonify({"error": "Mensagem vazia."}), 400
        row = add_chat_message(_owner_id(), {
            "text": text,
            "type": data.get("type"),
            "provider": data.get("provider") or "",
            "documents": data.get("documents") or [],
        })
        return jsonify({"ok": True, "id": row["id"]}), 201
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/history", methods=["POST", "DELETE"])
@login_required
def api_history():
    try:
        if request.method == "DELETE":
            history_id = request.args.get("id")
            delete_history(_owner_id(), history_id)
            return jsonify({"ok": True})
        data = request.get_json(silent=True) or {}
        query = str(data.get("query") or "").strip()
        if not query:
            return jsonify({"error": "Consulta vazia."}), 400
        item = {
            "id": str(data.get("id") or f"search_{uuid.uuid4()}"),
            "query": query[:20000],
            "projectId": str(data.get("projectId") or ""),
            "projectName": str(data.get("projectName") or "Toda a base"),
            "provider": str(data.get("provider") or ""),
            "usedDocuments": data.get("usedDocuments") or [],
        }
        add_history(_owner_id(), item)
        return jsonify(item), 201
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/backup/export")
@login_required
def api_backup_export():
    try:
        payload = load_state(_owner_id())
        payload["version"] = 3
        payload["storage"] = "local-filesystem"
        return jsonify(payload)
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/backup/import", methods=["POST"])
@login_required
def api_backup_import():
    try:
        replace_state(_owner_id(), request.get_json(silent=True) or {})
        return jsonify({"ok": True})
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return _storage_error(exc)


@app.route("/api/knowledge/status")
@login_required
def api_knowledge_status():
    state = load_state(_owner_id())
    documents = []
    for project in state.get("projects", []):
        documents.extend(project.get("documents") or [])
    synced = [doc for doc in documents if doc.get("sourceType") == "local_folder"]
    imported_at = [str(doc.get("importedAt") or "") for doc in synced if doc.get("importedAt")]
    heartbeat = app.config.get("LOCAL_AGENT_HEARTBEAT") or {}
    last_seen = float(heartbeat.get("lastSeen") or 0)
    online = bool(last_seen and (time.time() - last_seen) < 180)
    return jsonify({
        "documents": len(documents),
        "chunks": sum(len(doc.get("chunks") or []) for doc in documents),
        "syncedDocuments": len(synced),
        "lastSync": max(imported_at) if imported_at else None,
        "source": "C:\\agenteIA",
        "localAgent": {
            "online": online,
            "lastSeen": last_seen or None,
            "computer": heartbeat.get("computer"),
            "folder": heartbeat.get("folder") or "C:\\agenteIA",
            "pending": heartbeat.get("pending", 0),
            "synced": heartbeat.get("synced", 0),
            "errors": heartbeat.get("errors", 0),
            "detectedFiles": heartbeat.get("detectedFiles", 0),
        },
    })


@app.route("/api/agent/status")
@login_required
def agent_status():
    configured = [
        {"provider": provider["name"], "model": provider["model"]}
        for provider in provider_configurations()
    ]

    return jsonify({
        "configured": configured,
        "mfa": mfa_enabled(),
    })


@app.route("/api/agent", methods=["POST"])
@login_required
def agent():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Digite uma mensagem."}), 400

    history = sanitize_history(data.get("history", []))
    retrieval = build_global_knowledge_context(_owner_id(), message)
    project_context = retrieval["context"]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if project_context:
        messages.append({
            "role": "system",
            "content": (
                "CONTEXTO PRIVADO DA BASE PESSOAL:\n"
                "Os trechos abaixo foram selecionados automaticamente no servidor entre TODOS os arquivos "
                "sincronizados/importados. A seleção de projeto não limita esta pesquisa.\n\n"
                f"{project_context}"
            ),
        })

    messages.extend(history)

    if not history or history[-1].get("role") != "user" or history[-1].get("content") != message:
        messages.append({"role": "user", "content": message})

    try:
        result = ask_with_gemini(messages)
        result.update({
            "usedDocuments": retrieval["usedDocuments"],
            "retrievalCount": retrieval["chunkCount"],
            "totalDocuments": retrieval["totalDocuments"],
            "totalChunks": retrieval["totalChunks"],
        })
        return jsonify(result)
    except GeminiHTTPError as exc:
        payload = {
            "error": str(exc),
            "geminiStatus": exc.status_code,
            "retryable": exc.retryable,
        }
        if exc.retry_after is not None:
            payload["retryAfter"] = exc.retry_after
        return jsonify(payload), exc.status_code
    except RuntimeError as exc:
        return jsonify({"error": str(exc), "retryable": False}), 503
    except Exception:
        logger.exception("Erro inesperado no Agente IA")
        return jsonify({"error": "Erro interno ao processar a solicitação."}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "storage": "local-filesystem", "gemini": "configured" if os.getenv("GEMINI_API_KEY") else "missing"}), 200


if __name__ == "__main__":
    app.run(debug=True)

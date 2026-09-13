import base64
import hashlib
import hmac
import io
import logging
import os
import time
from datetime import timedelta
from pathlib import Path

import msal
import pyotp
import qrcode
import requests
from bs4 import BeautifulSoup
from docx import Document
from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI
from openpyxl import load_workbook
from pypdf import PdfReader

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alexandre-ai")

session_dir = Path(os.getenv("SESSION_FILE_DIR", "/tmp/alexandre_ai_sessions"))
session_dir.mkdir(parents=True, exist_ok=True)

app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-me"),
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR=str(session_dir),
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    MAX_CONTENT_LENGTH=12 * 1024 * 1024,
)

if os.getenv("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = True

Session(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"

SYSTEM_PROMPT = """Você é Alexandre AI, o assistente pessoal de Alexandre.
Responda sempre em português do Brasil, a menos que o usuário peça outro idioma.
Seja claro, objetivo, técnico quando necessário e útil.
Você pode receber um CONTEXTO DE PROJETO com descrição, notas e dados de arquivos.
Use esse contexto quando for relevante para a pergunta.
Nunca diga que acessou ou alterou algo que não esteja presente no contexto ou nas ferramentas do sistema.
Quando não tiver certeza de uma informação, deixe isso explícito.
"""

PREAUTH_TTL_SECONDS = 300
MAX_MFA_ATTEMPTS = 5

MICROSOFT_SCOPES = ["User.Read", "Files.Read", "Notes.Read"]
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"

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


# ------------------------
# MFA
# ------------------------

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
    started = session.get("preauth_at", 0)
    try:
        age = time.time() - float(started)
    except (TypeError, ValueError):
        return False
    return 0 <= age <= PREAUTH_TTL_SECONDS


def finish_login():
    remember = bool(session.get("remember_after_mfa"))
    login_user(get_admin_user(), remember=remember)
    clear_preauth()


# ------------------------
# Microsoft Graph / OAuth
# ------------------------

def microsoft_configured():
    return bool(
        os.getenv("MS_CLIENT_ID")
        and os.getenv("MS_CLIENT_SECRET")
    )


def microsoft_authority():
    tenant = os.getenv("MS_TENANT", "common").strip() or "common"
    return f"https://login.microsoftonline.com/{tenant}"


def microsoft_redirect_uri():
    configured = os.getenv("MS_REDIRECT_URI", "").strip()
    if configured:
        return configured
    return url_for("microsoft_callback", _external=True, _scheme="https" if os.getenv("RENDER") else "http")


def load_token_cache():
    cache = msal.SerializableTokenCache()
    serialized = session.get("ms_token_cache")
    if serialized:
        try:
            cache.deserialize(serialized)
        except Exception:
            logger.warning("Não foi possível restaurar cache Microsoft.")
    return cache


def save_token_cache(cache):
    if cache.has_state_changed:
        session["ms_token_cache"] = cache.serialize()


def build_msal_app(cache=None):
    if not microsoft_configured():
        return None
    return msal.ConfidentialClientApplication(
        os.getenv("MS_CLIENT_ID"),
        authority=microsoft_authority(),
        client_credential=os.getenv("MS_CLIENT_SECRET"),
        token_cache=cache,
    )


def get_graph_token():
    if not microsoft_configured():
        return None

    cache = load_token_cache()
    msal_app = build_msal_app(cache)
    accounts = msal_app.get_accounts()
    if not accounts:
        save_token_cache(cache)
        return None

    result = msal_app.acquire_token_silent(
        MICROSOFT_SCOPES,
        account=accounts[0],
    )
    save_token_cache(cache)

    if result and result.get("access_token"):
        return result["access_token"]

    return None


def graph_request(method, path_or_url, *, timeout=35, **kwargs):
    token = get_graph_token()
    if not token:
        raise PermissionError("Conta Microsoft não conectada ou sessão expirada.")

    url = path_or_url if path_or_url.startswith("http") else f"{GRAPH_ROOT}{path_or_url}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"

    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=timeout,
        **kwargs,
    )

    if response.status_code == 401:
        session.pop("ms_token_cache", None)
        raise PermissionError("A conexão Microsoft expirou. Conecte novamente.")

    response.raise_for_status()
    return response


def microsoft_profile():
    try:
        response = graph_request("GET", "/me?$select=displayName,userPrincipalName,mail")
        return response.json()
    except Exception:
        return None


# ------------------------
# Extração de arquivos
# ------------------------

def normalize_text(text, max_chars=120000):
    text = (text or "").replace("\x00", "")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()[:max_chars]


def extract_pdf(file_obj):
    reader = PdfReader(file_obj)
    chunks = []
    for idx, page in enumerate(reader.pages[:80], start=1):
        text = page.extract_text() or ""
        if text.strip():
            chunks.append(f"[Página {idx}]\n{text}")
    return normalize_text("\n\n".join(chunks))


def extract_docx(file_obj):
    document = Document(file_obj)
    chunks = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            chunks.append(paragraph.text.strip())

    for table in document.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells]
            if any(values):
                chunks.append(" | ".join(values))

    return normalize_text("\n".join(chunks))


def extract_xlsx(file_obj):
    workbook = load_workbook(file_obj, read_only=True, data_only=True)
    chunks = []
    for sheet in workbook.worksheets[:20]:
        chunks.append(f"[Planilha: {sheet.title}]")
        row_count = 0
        for row in sheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            if any(v.strip() for v in values):
                chunks.append(" | ".join(values))
                row_count += 1
            if row_count >= 2000:
                chunks.append("[Conteúdo truncado nesta planilha]")
                break
    return normalize_text("\n".join(chunks))


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
        return extract_pdf(file_obj)
    if suffix == ".docx":
        return extract_docx(file_obj)
    if suffix in {".xlsx", ".xlsm"}:
        return extract_xlsx(file_obj)

    return extract_text_file(file_obj)


def extract_bytes_content(data, filename):
    return extract_file_content(io.BytesIO(data), filename)


# ------------------------
# IA
# ------------------------

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
        if not content:
            continue

        clean.append({
            "role": normalized_role,
            "content": content[:12000],
        })

    return clean


def sanitize_project_context(raw_context):
    if not isinstance(raw_context, str):
        return ""
    return normalize_text(raw_context, max_chars=45000)


def provider_configurations():
    providers = []

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        providers.append({
            "name": "Groq",
            "client": OpenAI(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=35.0,
                max_retries=0,
            ),
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        })

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        providers.append({
            "name": "Gemini",
            "client": OpenAI(
                api_key=gemini_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                timeout=35.0,
                max_retries=0,
            ),
            "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        })

    cloudflare_key = os.getenv("CLOUDFLARE_API_TOKEN")
    cloudflare_account = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    if cloudflare_key and cloudflare_account:
        providers.append({
            "name": "Cloudflare",
            "client": OpenAI(
                api_key=cloudflare_key,
                base_url=f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_account}/ai/v1",
                timeout=35.0,
                max_retries=0,
            ),
            "model": os.getenv(
                "CLOUDFLARE_MODEL",
                "@cf/google/gemma-4-26b-a4b-it",
            ),
        })

    return providers


def ask_with_fallback(messages):
    providers = provider_configurations()

    if not providers:
        raise RuntimeError(
            "Nenhum provedor de IA está configurado. "
            "Adicione GROQ_API_KEY, GEMINI_API_KEY ou as credenciais do Cloudflare no Render."
        )

    errors = []

    for provider in providers:
        try:
            logger.info(
                "Tentando provedor=%s modelo=%s",
                provider["name"],
                provider["model"],
            )

            response = provider["client"].chat.completions.create(
                model=provider["model"],
                messages=messages,
                temperature=0.4,
                max_tokens=1600,
            )

            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("O provedor retornou uma resposta vazia.")

            return {
                "reply": content.strip(),
                "provider": provider["name"],
                "model": provider["model"],
            }

        except Exception as exc:
            logger.warning(
                "Falha no provedor %s: %s",
                provider["name"],
                str(exc)[:500],
            )
            errors.append(provider["name"])

    raise RuntimeError(
        "Os provedores configurados não responderam. "
        f"Tentativas: {', '.join(errors)}."
    )


# ------------------------
# Segurança / login
# ------------------------

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
        microsoft_configured=microsoft_configured(),
    )


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    clear_preauth()
    return redirect(url_for("login"))


# ------------------------
# Microsoft routes
# ------------------------

@app.route("/microsoft/connect")
@login_required
def microsoft_connect():
    if not microsoft_configured():
        return redirect(url_for("dashboard", ms_error="not_configured"))

    cache = load_token_cache()
    msal_app = build_msal_app(cache)

    flow = msal_app.initiate_auth_code_flow(
        scopes=MICROSOFT_SCOPES,
        redirect_uri=microsoft_redirect_uri(),
    )
    session["ms_auth_flow"] = flow
    save_token_cache(cache)

    auth_uri = flow.get("auth_uri")
    if not auth_uri:
        return redirect(url_for("dashboard", ms_error="auth_failed"))

    return redirect(auth_uri)


@app.route("/microsoft/callback")
@login_required
def microsoft_callback():
    flow = session.get("ms_auth_flow")
    if not flow:
        return redirect(url_for("dashboard", ms_error="flow_missing"))

    cache = load_token_cache()
    msal_app = build_msal_app(cache)

    try:
        result = msal_app.acquire_token_by_auth_code_flow(flow, request.args)
    except ValueError:
        return redirect(url_for("dashboard", ms_error="invalid_callback"))

    save_token_cache(cache)
    session.pop("ms_auth_flow", None)

    if "access_token" not in result:
        logger.warning("Falha OAuth Microsoft: %s", result.get("error_description", result))
        return redirect(url_for("dashboard", ms_error="oauth_failed"))

    return redirect(url_for("dashboard", ms_connected="1"))


@app.route("/microsoft/disconnect", methods=["POST"])
@login_required
def microsoft_disconnect():
    session.pop("ms_token_cache", None)
    session.pop("ms_auth_flow", None)
    return jsonify({"ok": True})


@app.route("/api/microsoft/status")
@login_required
def microsoft_status():
    if not microsoft_configured():
        return jsonify({
            "configured": False,
            "connected": False,
            "profile": None,
        })

    token = get_graph_token()
    profile = microsoft_profile() if token else None

    return jsonify({
        "configured": True,
        "connected": bool(token),
        "profile": profile,
    })


@app.route("/api/microsoft/onenote/pages")
@login_required
def onenote_pages():
    try:
        response = graph_request(
            "GET",
            "/me/onenote/pages?$top=50&$orderby=lastModifiedTime desc"
            "&$select=id,title,createdDateTime,lastModifiedTime,links,parentSection",
        )
        data = response.json()
        pages = []
        for item in data.get("value", []):
            pages.append({
                "id": item.get("id"),
                "title": item.get("title") or "Sem título",
                "createdDateTime": item.get("createdDateTime"),
                "lastModifiedTime": item.get("lastModifiedTime"),
                "section": (item.get("parentSection") or {}).get("displayName"),
                "webUrl": ((item.get("links") or {}).get("oneNoteWebUrl") or {}).get("href"),
            })
        return jsonify({"pages": pages})
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except requests.HTTPError as exc:
        logger.warning("Erro OneNote: %s", exc)
        return jsonify({"error": "Não foi possível consultar o OneNote."}), 502


@app.route("/api/microsoft/onenote/page/<path:page_id>")
@login_required
def onenote_page_content(page_id):
    try:
        meta_response = graph_request(
            "GET",
            f"/me/onenote/pages/{page_id}?$select=id,title,lastModifiedTime,parentSection",
        )
        metadata = meta_response.json()

        content_response = graph_request(
            "GET",
            f"/me/onenote/pages/{page_id}/content",
        )
        html = content_response.text
        soup = BeautifulSoup(html, "html.parser")
        text = normalize_text(soup.get_text("\n", strip=True))

        return jsonify({
            "id": page_id,
            "title": metadata.get("title") or "Página OneNote",
            "section": (metadata.get("parentSection") or {}).get("displayName"),
            "lastModifiedTime": metadata.get("lastModifiedTime"),
            "content": text,
            "sourceType": "onenote",
        })
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except requests.HTTPError:
        return jsonify({"error": "Não foi possível importar essa página do OneNote."}), 502


@app.route("/api/microsoft/onedrive/items")
@login_required
def onedrive_items():
    item_id = request.args.get("item_id", "").strip()

    try:
        if item_id:
            endpoint = (
                f"/me/drive/items/{item_id}/children"
                "?$top=100&$select=id,name,size,lastModifiedDateTime,folder,file,webUrl,parentReference"
            )
        else:
            endpoint = (
                "/me/drive/root/children"
                "?$top=100&$select=id,name,size,lastModifiedDateTime,folder,file,webUrl,parentReference"
            )

        response = graph_request("GET", endpoint)
        data = response.json()
        items = []

        for item in data.get("value", []):
            items.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "size": item.get("size", 0),
                "lastModifiedDateTime": item.get("lastModifiedDateTime"),
                "isFolder": bool(item.get("folder")),
                "mimeType": (item.get("file") or {}).get("mimeType"),
                "webUrl": item.get("webUrl"),
            })

        return jsonify({"items": items, "currentFolderId": item_id or None})
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except requests.HTTPError:
        return jsonify({"error": "Não foi possível consultar o OneDrive."}), 502


@app.route("/api/microsoft/onedrive/file/<path:item_id>")
@login_required
def onedrive_file_content(item_id):
    try:
        meta = graph_request(
            "GET",
            f"/me/drive/items/{item_id}?$select=id,name,size,file,webUrl,lastModifiedDateTime",
        ).json()

        filename = meta.get("name") or "arquivo"
        suffix = Path(filename).suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            return jsonify({
                "error": "Esse tipo de arquivo ainda não pode ser convertido em texto para a IA."
            }), 400

        response = graph_request("GET", f"/me/drive/items/{item_id}/content", timeout=60)
        text = extract_bytes_content(response.content, filename)

        return jsonify({
            "id": item_id,
            "title": filename,
            "content": text,
            "sourceType": "onedrive",
            "webUrl": meta.get("webUrl"),
            "lastModifiedTime": meta.get("lastModifiedDateTime"),
        })
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except requests.HTTPError:
        return jsonify({"error": "Não foi possível baixar esse arquivo do OneDrive."}), 502
    except Exception as exc:
        logger.exception("Erro ao extrair arquivo OneDrive")
        return jsonify({"error": f"Não foi possível ler o arquivo: {str(exc)[:160]}"}), 400


# ------------------------
# Arquivo local
# ------------------------

@app.route("/api/files/extract", methods=["POST"])
@login_required
def extract_uploaded_file():
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Selecione um arquivo."}), 400

    try:
        text = extract_file_content(uploaded.stream, uploaded.filename)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Erro ao extrair upload")
        return jsonify({"error": f"Não foi possível ler o arquivo: {str(exc)[:160]}"}), 400

    if not text:
        return jsonify({"error": "O arquivo não possui texto legível para importar."}), 400

    return jsonify({
        "title": uploaded.filename,
        "content": text,
        "sourceType": "local_file",
        "size": request.content_length or 0,
    })


# ------------------------
# IA routes
# ------------------------

@app.route("/api/agent/status")
@login_required
def agent_status():
    configured = [
        {"provider": p["name"], "model": p["model"]}
        for p in provider_configurations()
    ]

    return jsonify({
        "configured": configured,
        "fallback_order": [p["provider"] for p in configured],
        "mfa": mfa_enabled(),
        "microsoftConfigured": microsoft_configured(),
    })


@app.route("/api/agent", methods=["POST"])
@login_required
def agent():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Digite uma mensagem."}), 400

    history = sanitize_history(data.get("history", []))
    project_context = sanitize_project_context(data.get("projectContext", ""))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if project_context:
        messages.append({
            "role": "system",
            "content": (
                "CONTEXTO DE PROJETO ATIVO:\n"
                "Use as informações abaixo como fonte privada fornecida pelo usuário. "
                "Não invente conteúdo além do que estiver presente.\n\n"
                f"{project_context}"
            ),
        })

    messages.extend(history)

    if (
        not history
        or history[-1].get("role") != "user"
        or history[-1].get("content") != message
    ):
        messages.append({"role": "user", "content": message})

    try:
        result = ask_with_fallback(messages)
        return jsonify(result)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception:
        logger.exception("Erro inesperado no Agente IA")
        return jsonify({"error": "Erro interno ao processar a solicitação."}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True)

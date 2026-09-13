import base64
import hashlib
import hmac
import io
import logging
import os
import time
from datetime import timedelta

import pyotp
import qrcode
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from openai import OpenAI

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
)

if os.getenv("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = True

csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"

SYSTEM_PROMPT = """Você é Alexandre AI, o assistente pessoal de Alexandre.
Responda sempre em português do Brasil, a menos que o usuário peça outro idioma.
Seja claro, objetivo e útil. Para assuntos técnicos, explique passo a passo quando isso ajudar.
Nunca invente que executou uma ação que o sistema ainda não possui.
Quando não tiver certeza de uma informação, deixe isso explícito.
"""

PREAUTH_TTL_SECONDS = 300
MAX_MFA_ATTEMPTS = 5


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
    """
    Deriva uma chave TOTP Base32 a partir do SECRET_KEY.
    Isso evita armazenar um segundo segredo TOTP em banco.
    Se SECRET_KEY for alterado, o Authenticator precisará ser pareado novamente.
    """
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
    for key in (
        "preauth",
        "preauth_at",
        "remember_after_mfa",
        "mfa_attempts",
    ):
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

    return render_template(
        "login.html",
        error=error,
        mfa_enabled=mfa_enabled(),
    )


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
            "content": content[:12000]
        })

    return clean


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
                "@cf/google/gemma-4-26b-a4b-it"
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
                max_tokens=1200,
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
    })


@app.route("/api/agent", methods=["POST"])
@login_required
def agent():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Digite uma mensagem."}), 400

    history = sanitize_history(data.get("history", []))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)

    if not history or history[-1].get("role") != "user" or history[-1].get("content") != message:
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

import hmac
import logging
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
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


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
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
            login_user(get_admin_user(), remember=remember)
            return redirect(url_for("dashboard"))

        error = "E-mail ou senha inválidos."

    return render_template("login.html", error=error)


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


def sanitize_history(raw_history):
    """Mantém apenas mensagens simples e limita o contexto enviado às APIs."""
    clean = []

    if not isinstance(raw_history, list):
        return clean

    # Últimas 16 mensagens para evitar contexto excessivo.
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

        # Limite defensivo por mensagem.
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
            # Não devolvemos o erro completo ao navegador para não expor detalhes.
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

    # Evita duplicar a mensagem caso o frontend já a tenha colocado no histórico.
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

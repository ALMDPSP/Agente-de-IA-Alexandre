import hmac
import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect

load_dotenv()

app = Flask(__name__)

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


@app.route("/api/agent", methods=["POST"])
@login_required
def agent():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Digite uma mensagem."}), 400

    # Próxima etapa:
    # conectar o roteador de IA:
    # Groq -> Gemini -> Cloudflare AI
    return jsonify({
        "reply": (
            "A interface do seu agente está funcionando sem banco de dados. "
            "Na próxima etapa vamos conectar Groq → Gemini → Cloudflare AI."
        )
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True)

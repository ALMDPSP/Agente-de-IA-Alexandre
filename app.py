import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)

database_url = os.getenv("DATABASE_URL", "sqlite:///alexandre_ai.db")
# Compatibilidade com URIs antigas do PostgreSQL.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-me"),
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    REMEMBER_COOKIE_HTTPONLY=True,
    REMEMBER_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)

# Em produção no Render, os cookies de sessão podem ser marcados como seguros.
if os.getenv("RENDER"):
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = True

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "warning"


class User(UserMixin, db.Model):
    __tablename__ = "alexandre_ai_users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, default="Alexandre")
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="admin")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def bootstrap_admin():
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    name = os.getenv("ADMIN_NAME", "Alexandre")

    if not email or not password:
        return

    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        return

    user = User(name=name.strip() or "Alexandre", email=email, role="admin")
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


with app.app_context():
    db.create_all()
    bootstrap_admin()


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

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
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
    # aqui conectaremos o roteador de IA:
    # Groq -> Gemini -> Cloudflare AI
    return jsonify(
        {
            "reply": (
                "A interface do seu agente já está pronta. "
                "Na próxima etapa vamos conectar Groq → Gemini → Cloudflare AI "
                "e adicionar as ferramentas do seu site."
            )
        }
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(debug=True)

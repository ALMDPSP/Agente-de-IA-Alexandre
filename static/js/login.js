const toggle = document.querySelector("[data-password-toggle]");
const password = document.querySelector("#password");

if (toggle && password) {
    toggle.addEventListener("click", () => {
        const isPassword = password.type === "password";
        password.type = isPassword ? "text" : "password";
        toggle.setAttribute("aria-label", isPassword ? "Ocultar senha" : "Mostrar senha");
        toggle.textContent = isPassword ? "◌" : "◉";
    });
}

const emailInput = document.querySelector('#email');
const submitBtn = document.querySelector('.auth-submit-btn');
if (emailInput && submitBtn) {
    emailInput.addEventListener('input', () => {
        submitBtn.dataset.armed = emailInput.value.includes('@') ? 'true' : 'false';
    });
}

function startMatrixRain() {
    const canvas = document.getElementById('matrixCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const chars = '01ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&@<>/[]{}*+-=アイウエオカキクケコサシスセソ0123456789';
    let fontSize = 16;
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
        fontSize = window.innerWidth < 768 ? 12 : 16;
        columns = Math.floor(window.innerWidth / fontSize);
        drops = Array.from({ length: columns }, () => Math.random() * -80);
    }

    function draw() {
        ctx.fillStyle = 'rgba(2, 7, 8, 0.11)';
        ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);

        ctx.font = `${fontSize}px monospace`;

        for (let i = 0; i < drops.length; i += 1) {
            const text = chars.charAt(Math.floor(Math.random() * chars.length));
            const x = i * fontSize;
            const y = drops[i] * fontSize;

            ctx.fillStyle = 'rgba(140, 255, 180, 0.95)';
            ctx.fillText(text, x, y);
            ctx.fillStyle = 'rgba(50, 170, 90, 0.72)';
            ctx.fillText(text, x, y - fontSize);

            if (y > window.innerHeight && Math.random() > 0.975) {
                drops[i] = Math.random() * -20;
            }

            drops[i] += 0.72;
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

startMatrixRain();

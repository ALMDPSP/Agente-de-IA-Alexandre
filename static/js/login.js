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

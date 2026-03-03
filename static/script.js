/* =========================================
   1. NAVIGATION & UI LOGIC
   ========================================= */

// Sticky Header Effect
window.addEventListener('scroll', () => {
    const nav = document.getElementById('mainNav');
    if (window.scrollY > 50) {
        nav.classList.add('scrolled');
    } else {
        nav.classList.remove('scrolled');
    }
});

// Modal Toggle (Login/Register)
function toggleModal() {
    const modal = document.getElementById('loginModal');
    modal.style.display = (modal.style.display === "flex") ? "none" : "flex";
}

// Switch between Login and Register Forms
function switchAuth(isRegister) {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    
    if (isRegister) {
        loginForm.style.display = "none";
        registerForm.style.display = "block";
    } else {
        loginForm.style.display = "block";
        registerForm.style.display = "none";
    }
}

/* =========================================
   2. AUTHENTICATION (Login & Role Direction)
   ========================================= */

// Front‑end authentication utilities.  The server will create
// `window.Auth` in a small inline script so the client code can
// inspect the current session without additional requests.
//
// `window.Auth` fields: userId, role, fullname (all may be null).

// if the login form is present we disable the button after submit
// to prevent double‑submits and optionally show a loader.
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.querySelector('#loginForm form');
    if (loginForm) {
        loginForm.addEventListener('submit', () => {
            const btn = loginForm.querySelector('button[type=submit]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Signing in...';
            }
        });
    }

    const regForm = document.querySelector('#registerForm form');
    if (regForm) {
        regForm.addEventListener('submit', () => {
            const btn = regForm.querySelector('button[type=submit]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Registering...';
            }
        });
    }

    // If the server flashed a message about needing to login, open
    // the modal automatically so the user can sign in quickly.
    const msgElem = document.getElementById('flash-message');
    if (msgElem && msgElem.textContent.toLowerCase().includes('please login')) {
        toggleModal();
    }
});



/* =========================================
   3. PASSWORD FUNCTIONALITY (Show/Hide & Strength)
   ========================================= */

// Toggle Password Visibility
function togglePasswordVisibility(inputId, iconElement) {
    const passwordInput = document.getElementById(inputId);
    
    if (passwordInput.type === "password") {
        passwordInput.type = "text";
        iconElement.classList.remove("fa-eye");
        iconElement.classList.add("fa-eye-slash");
    } else {
        passwordInput.type = "password";
        iconElement.classList.remove("fa-eye-slash");
        iconElement.classList.add("fa-eye");
    }
}

// Password Strength Meter
function checkStrength(password) {
    const bar = document.getElementById('strength-bar');
    let strength = 0;

    if (password.length > 5) strength += 25;
    if (password.match(/[a-z]/) && password.match(/[A-Z]/)) strength += 25;
    if (password.match(/[0-9]/)) strength += 25;
    if (password.match(/[^a-zA-Z0-9]/)) strength += 25;

    bar.style.width = strength + "%";

    // Change color based on strength
    if (strength <= 25) bar.style.backgroundColor = "#ff4d4d"; // Weak
    else if (strength <= 75) bar.style.backgroundColor = "#ffad33"; // Medium
    else bar.style.backgroundColor = "#2eb82e"; // Strong
}

/* =========================================
   4. FORM VALIDATION
   ========================================= */

// Validate Registration Form (Password Match)
document.addEventListener('DOMContentLoaded', () => {
    const regForm = document.querySelector('#registerForm form');
    if (regForm) {
        regForm.addEventListener('submit', function(e) {
            const pass = document.getElementById('regPass').value;
            const confirm = document.getElementById('confirmPass').value;

            if (pass !== confirm) {
                e.preventDefault();
                alert("Passwords do not match! Please verify your password confirmation.");
            }
        });
    }
});

/* =========================================
   5. STATUS HELPERS
   ========================================= */

function handleCancel() {
    if (confirm("Are you sure you want to cancel this ticket?")) {
        alert("Ticket cancelled successfully.");
        window.location.href = 'index.html';
    }
}

// placeholder for booking confirmation - currently client side only
function confirmFinalBooking() {
    if (confirm("Confirm booking with the provided details?")) {
        alert("Booking confirmed! Redirecting to status.");
        window.location.href = '/status';
    }
}

function confirmLogout(event) {
    event.preventDefault();

    if (confirm("Are you sure you want to logout?")) {
        window.location.href = "/logout";
    }
}

// Schedule filtering helper for the schedules page
function filterSchedules() {
    const input = document.getElementById('scheduleSearch');
    const filter = input.value.toLowerCase();
    const table = document.getElementById('busTable');
    const tr = table.getElementsByTagName('tr');

    for (let i = 1; i < tr.length; i++) { // skip header row
        const td = tr[i].getElementsByTagName('td')[1];
        if (td) {
            const txtValue = td.textContent || td.innerText;
            tr[i].style.display = txtValue.toLowerCase().indexOf(filter) > -1 ? '' : 'none';
        }
    }
}

// Back to top button behaviour
window.addEventListener('scroll', () => {
    const btn = document.getElementById('backToTop');
    if (!btn) return;
    if (window.scrollY > 200) {
        btn.style.display = 'block';
    } else {
        btn.style.display = 'none';
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('backToTop');
    if (btn) {
        btn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});

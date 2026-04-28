/* =========================================
   1. NAVIGATION & UI LOGIC
========================================= */

// Sticky Header Effect
window.addEventListener('scroll', () => {
    const nav = document.getElementById('mainNav');
    if (!nav) return;

    nav.classList.toggle('scrolled', window.scrollY > 50);
});

// Back to Top Button
window.addEventListener('scroll', () => {
    const btn = document.getElementById('backToTop');
    if (!btn) return;
    btn.style.display = window.scrollY > 200 ? 'block' : 'none';
});

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('backToTop');
    if (btn) {
        btn.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});

// Modal Toggle (Login/Register)
function toggleModal() {
    const modal = document.getElementById('loginModal');
    if (!modal) return;

    modal.style.display = modal.style.display === "flex" ? "none" : "flex";
}

// Switch Auth Forms
function switchAuth(isRegister) {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (!loginForm || !registerForm) return;

    loginForm.style.display = isRegister ? "none" : "block";
    registerForm.style.display = isRegister ? "block" : "none";
}


/* =========================================
   2. AUTHENTICATION
========================================= */

document.addEventListener('DOMContentLoaded', () => {

    const loginForm = document.querySelector('#loginForm form');
    const regForm = document.querySelector('#registerForm form');

    // Login submit
    if (loginForm) {
        loginForm.addEventListener('submit', () => {
            const btn = loginForm.querySelector('button[type=submit]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Signing in...';
            }
        });
    }

    // Register submit + validation
    if (regForm) {
        regForm.addEventListener('submit', (e) => {
            const pass = document.getElementById('regPass')?.value;
            const confirm = document.getElementById('confirmPass')?.value;

            if (pass !== confirm) {
                e.preventDefault();
                alert('⚠️ Passwords do not match.');
                return;
            }

            if (pass.length < 6) {
                e.preventDefault();
                alert('⚠️ Password must be at least 6 characters.');
                return;
            }

            const btn = regForm.querySelector('button[type=submit]');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Registering...';
            }
        });
    }

    // Auto-open modal if needed
    const msgElem = document.getElementById('flash-message');
    if (msgElem && msgElem.textContent.toLowerCase().includes('please login')) {
        toggleModal();
    }
});


/* =========================================
   3. PASSWORD FEATURES
========================================= */

// Toggle Password Visibility
function togglePasswordVisibility(inputId, icon) {
    const input = document.getElementById(inputId);
    if (!input) return;

    if (input.type === "password") {
        input.type = "text";
        icon.classList.replace("fa-eye", "fa-eye-slash");
    } else {
        input.type = "password";
        icon.classList.replace("fa-eye-slash", "fa-eye");
    }
}

// Password Strength
function checkStrength(password) {
    const bar = document.getElementById('strength-bar');
    if (!bar) return;

    let strength = 0;

    if (password.length > 5) strength += 25;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength += 25;
    if (/[0-9]/.test(password)) strength += 25;
    if (/[^a-zA-Z0-9]/.test(password)) strength += 25;

    bar.style.width = strength + "%";

    if (strength <= 25) bar.style.backgroundColor = "#ff4d4d";
    else if (strength <= 75) bar.style.backgroundColor = "#ffad33";
    else bar.style.backgroundColor = "#2eb82e";
}


/* =========================================
   4. STATUS / ACTION HELPERS
========================================= */

function handleCancel() {
    if (confirm("Are you sure you want to cancel this ticket?")) {
        alert("Ticket cancelled successfully.");
        window.location.href = "index.html";
    }
}

function confirmFinalBooking() {
    if (confirm("Confirm booking?")) {
        alert("Booking confirmed!");
        window.location.href = "/status";
    }
}

function confirmLogout(event) {
    event.preventDefault();
    if (confirm("Are you sure you want to logout?")) {
        window.location.href = "/logout";
    }
}


/* =========================================
   5. SCHEDULE FILTER
========================================= */

function filterSchedules() {
    const input = document.getElementById('scheduleSearch');
    const table = document.getElementById('busTable');
    if (!input || !table) return;

    const filter = input.value.toLowerCase();
    const rows = table.getElementsByTagName('tr');

    for (let i = 1; i < rows.length; i++) {
        const td = rows[i].getElementsByTagName('td')[1];
        if (!td) continue;

        const text = td.textContent.toLowerCase();
        rows[i].style.display = text.includes(filter) ? '' : 'none';
    }
}


/* =========================================
   6. SEAT MAP SYSTEM
========================================= */

const TOTAL_SEATS = 52;

function getBookedSeats(tripId) {
    fetch(`/api/booked-seats/${tripId}`)
        .then(res => res.json())
        .then(data => renderSeats(data))
        .catch(console.error);
}

function renderSeats(bookedSeats) {
    const container = document.getElementById('seatContainer');
    if (!container) return;

    container.innerHTML = "";

    for (let i = 1; i <= TOTAL_SEATS; i++) {
        const seat = document.createElement('div');
        seat.classList.add('seat');
        seat.textContent = i;

        if (bookedSeats.includes(String(i))) {
            seat.classList.add('booked');
        } else {
            seat.addEventListener('click', () => selectSeat(seat, i));
        }

        container.appendChild(seat);
    }
}

function selectSeat(element, seatNumber) {
    document.querySelectorAll('.seat.selected')
        .forEach(s => s.classList.remove('selected'));

    element.classList.add('selected');

    const input = document.getElementById('seat_number');
    if (input) input.value = seatNumber;
}


/* =========================================
   7. ADMIN FEATURES
========================================= */

document.addEventListener('DOMContentLoaded', () => {

    // Bus search
    const busSearch = document.getElementById('busSearch');
    const busTable = document.querySelector('.admin-table tbody');

    if (busSearch && busTable) {
        busSearch.addEventListener('input', function () {
            const term = this.value.toLowerCase();

            busTable.querySelectorAll('tr').forEach(row => {
                row.style.display =
                    row.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        });
    }

    // User search
    const userSearch = document.getElementById('userSearch');
    const usersTable = document.getElementById('usersTable');

    if (userSearch && usersTable) {
        userSearch.addEventListener('input', function () {
            const term = this.value.toLowerCase();

            usersTable.querySelectorAll('tbody tr').forEach(row => {
                row.style.display =
                    row.textContent.toLowerCase().includes(term) ? '' : 'none';
            });
        });
    }

    // Modal controls (Bus/User)
    const addBusBtn = document.getElementById('addBusBtn');
    const addBusModal = document.getElementById('addBusModal');
    const closeBusModal = document.querySelector('#addBusModal .close-modal');

    if (addBusBtn && addBusModal) {
        addBusBtn.addEventListener('click', () => addBusModal.style.display = 'flex');

        closeBusModal?.addEventListener('click', () => addBusModal.style.display = 'none');

        window.addEventListener('click', (e) => {
            if (e.target === addBusModal) addBusModal.style.display = 'none';
        });
    }

    const addUserBtn = document.getElementById('addUserBtn');
    const addUserModal = document.getElementById('addUserModal');
    const closeUserModal = document.querySelector('#addUserModal .close-modal');

    if (addUserBtn && addUserModal) {
        addUserBtn.addEventListener('click', () => addUserModal.style.display = 'flex');

        closeUserModal?.addEventListener('click', () => addUserModal.style.display = 'none');

        window.addEventListener('click', (e) => {
            if (e.target === addUserModal) addUserModal.style.display = 'none';
        });
    }

    // Booking tabs
    const activeTab = document.getElementById('activeBookingsTab');
    const historyTab = document.getElementById('historyBookingsTab');
    const activeSection = document.getElementById('activeBookingsSection');
    const historySection = document.getElementById('historyBookingsSection');

    if (activeTab && historyTab) {
        activeTab.addEventListener('click', () => {
            activeTab.classList.add('active');
            historyTab.classList.remove('active');
            activeSection?.classList.add('active');
            historySection?.classList.remove('active');
        });

        historyTab.addEventListener('click', () => {
            historyTab.classList.add('active');
            activeTab.classList.remove('active');
            historySection?.classList.add('active');
            activeSection?.classList.remove('active');
        });
    }
});
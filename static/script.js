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
    const seatStatuses = {};
    bookedSeats.forEach(item => {
        if (typeof item === 'object' && item !== null) {
            seatStatuses[String(item.seat)] = item.status || 'booked';
        } else {
            seatStatuses[String(item)] = 'booked';
        }
    });

    for (let i = 1; i <= TOTAL_SEATS; i++) {
        const seat = document.createElement('div');
        seat.classList.add('seat');
        seat.textContent = i;

        if (seatStatuses[String(i)]) {
            seat.classList.add('booked');
            if (seatStatuses[String(i)] === 'blocked') {
                seat.classList.add('blocked-admin');
            }
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

/* =========================================
   8. CONDUCTOR SCANNER SYSTEM
========================================= */

function initTicketScanner() {
    const readerElem = document.getElementById('reader');
    const dashboard = document.querySelector('.dashboard-page');
    if (!readerElem || !dashboard) return;

    // Conductor Tab Navigation
    const tabs = dashboard.querySelectorAll('.tab-btn');
    const panels = dashboard.querySelectorAll('.tab-panel');

    tabs.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.getAttribute('data-tab');
            
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            document.getElementById(target).classList.add('active');
        });
    });

    const feedbackDiv = document.getElementById('scan-feedback');
    const feedbackIcon = document.getElementById('feedback-icon');
    const feedbackTitle = document.getElementById('feedback-title');
    const feedbackMessage = document.getElementById('feedback-message');
    const resetBtn = document.getElementById('reset-scanner-btn');
    const historyBody = document.getElementById('scan-history-body');

    const html5QrCode = new Html5Qrcode("reader");
    const config = { fps: 10, qrbox: { width: 280, height: 280 } };

    const onScanSuccess = (decodedText) => {
        // Pause scanning to process the result
        html5QrCode.pause();
        
        // Show processing state
        feedbackDiv.style.display = 'block';
        feedbackDiv.style.background = 'rgba(255, 255, 255, 0.8)';
        feedbackTitle.textContent = "Processing...";
        feedbackMessage.textContent = "Validating ticket...";
        feedbackIcon.className = "fa-solid fa-spinner fa-spin";
        feedbackIcon.style.color = "var(--accent)";
        resetBtn.style.display = 'none';

        // Send scanned data to API
        fetch('/api/scan_ticket', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qr_content: decodedText })
        })
        .then(res => res.json())
        .then(data => {
            resetBtn.style.display = 'inline-block';
            const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            const ticketId = decodedText.match(/Ticket #(\d+)/)?.[1] || "Unknown";
            
            if (data.success) {
                // Boarding or Completion Success
                feedbackDiv.style.background = 'rgba(76, 175, 80, 0.25)';
                feedbackDiv.style.border = '2px solid #2e7d32';
                feedbackIcon.className = "fa-solid fa-circle-check";
                feedbackIcon.style.color = "#2e7d32";
                feedbackTitle.textContent = "SUCCESS";
                feedbackTitle.style.color = "#2e7d32";
                feedbackMessage.textContent = data.message;
            } else {
                // Already used or cancelled ticket (Real-time "Flash" Error)
                feedbackDiv.style.background = 'rgba(244, 67, 54, 0.4)'; // Darker red for emphasis
                feedbackDiv.style.border = '2px solid #c62828';
                feedbackDiv.style.animation = 'shake 0.4s ease-in-out'; // Adding a shake animation
                feedbackIcon.className = "fa-solid fa-circle-xmark";
                feedbackIcon.style.color = "#c62828";
                feedbackTitle.textContent = "SCAN ERROR";
                feedbackTitle.style.color = "#c62828";
                feedbackMessage.textContent = data.message;
                
                // Remove shake class after animation finishes
                setTimeout(() => feedbackDiv.style.animation = '', 400);
            }

            // Add to History Table
            if (historyBody) {
                if (historyBody.children.length === 1 && historyBody.innerText.includes('No tickets')) {
                    historyBody.innerHTML = '';
                }
                const row = document.createElement('tr');
                const statusClass = data.success ? 'status-paid' : 'status-cancelled';
                row.innerHTML = `
                    <td>${now}</td>
                    <td><strong>#${ticketId}</strong></td>
                    <td><span class="${statusClass}">${data.new_status || 'Error'}</span></td>
                    <td style="font-size: 0.85rem;">${data.message}</td>
                `;
                historyBody.prepend(row);
            }
        })
        .catch(err => {
            console.error(err);
            feedbackDiv.style.display = 'block';
            feedbackTitle.textContent = "CONNECTION ERROR";
            feedbackMessage.textContent = "Could not communicate with the server.";
            resetBtn.style.display = 'inline-block';
        });
    };

    // Start camera (Environment/Back camera preferred)
    html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess)
        .catch(err => console.error("Scanner start error:", err));

    resetBtn.addEventListener('click', () => {
        feedbackDiv.style.display = 'none';
        html5QrCode.resume();
    });
}

document.addEventListener('DOMContentLoaded', initTicketScanner);

/* =========================================
   9. DISCOUNT ID SCANNER LOGIC
========================================= */

function setupIdScanner(btnId, readerId, inputId, statusId) {
    const btn = document.getElementById(btnId);
    const reader = document.getElementById(readerId);
    const input = document.getElementById(inputId);
    const status = document.getElementById(statusId);
    
    if (!btn || !reader) return;

    let html5QrCode = null;

    window.stopIdScanner = () => {
        if (html5QrCode && html5QrCode.isScanning) {
            html5QrCode.stop().then(() => {
                reader.style.display = 'none';
                btn.innerHTML = btnId.includes('staff') ? '<i class="fa-solid fa-camera"></i> Scan Customer ID' : '<i class="fa-solid fa-camera"></i> Use Camera to Scan ID';
            });
        }
    };

    btn.addEventListener('click', () => {
        if (html5QrCode && html5QrCode.isScanning) {
            window.stopIdScanner();
            return;
        }

        reader.style.display = 'block';
        btn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop Camera';
        
        html5QrCode = new Html5Qrcode(readerId);
        const config = { fps: 10, qrbox: { width: 250, height: 250 } };

        html5QrCode.start({ facingMode: "environment" }, config, (decodedText) => {
            // Real-time verification logic
            const isIdValid = decodedText.toUpperCase().includes("ID");
            
            if (isIdValid) {
                status.style.display = 'block';
                status.style.color = '#166534';
                status.style.backgroundColor = '#dcfce7';
                status.innerHTML = `<i class="fa-solid fa-circle-check"></i> ID Verified: ${decodedText}`;
                if (input) input.value = "1";
                window.stopIdScanner();
            } else {
                // Real-time error feedback
                status.style.display = 'block';
                status.style.color = '#991b1b';
                status.style.backgroundColor = '#fee2e2';
                status.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Scan Error: Invalid ID format detected.`;
                
                // Shake effect for error
                reader.style.animation = 'shake 0.4s ease-in-out';
                setTimeout(() => reader.style.animation = '', 400);
            }
        }).catch(err => {
            console.error(err);
            status.style.display = 'block';
            status.style.color = '#991b1b';
            status.textContent = "Could not start camera.";
        });
    });
}

// Initialize for both dashboards
document.addEventListener('DOMContentLoaded', () => {
    setupIdScanner('start-id-scan', 'id-reader', 'id_scanned', 'id-verification-status');
    setupIdScanner('staff-start-id-scan', 'staff-id-reader', 'staff_id_scanned', 'staff-id-verification-status');
    
    // Staff Dashboard specific toggle
    const staffDiscount = document.getElementById('discount_type');
    const staffIdSection = document.getElementById('staff-id-verify-section');
    
    if (staffDiscount && staffIdSection) {
        staffDiscount.addEventListener('change', function() {
            if (this.value !== 'regular') {
                staffIdSection.classList.remove('hidden');
            } else {
                staffIdSection.classList.add('hidden');
                const hiddenInp = document.getElementById('staff_id_scanned');
                if (hiddenInp) hiddenInp.value = '0';
                const statusDiv = document.getElementById('staff-id-verification-status');
                if (statusDiv) statusDiv.style.display = 'none';
                if (window.stopIdScanner) window.stopIdScanner();
            }
        });
    }
});

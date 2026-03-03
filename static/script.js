// 1. Navigation and Back to Top Effect
window.addEventListener('scroll', () => {
    const nav = document.getElementById('mainNav');
    const topBtn = document.getElementById('backToTop');
    
    // Scrolled Nav effect
    if (window.scrollY > 50) {
        nav.classList.add('scrolled');
        topBtn.style.display = "block";
    } else {
        nav.classList.remove('scrolled');
        topBtn.style.display = "none";
    }
});

// 2. Modal Controls
function toggleModal() {
    const modal = document.getElementById('loginModal');
    modal.style.display = (modal.style.display === "flex") ? "none" : "flex";
}

// 3. Switch between Login and Register inside Modal
function switchAuth(isRegister) {
    const login = document.getElementById('loginForm');
    const register = document.getElementById('registerForm');
    
    if (isRegister) {
        login.style.display = "none";
        register.style.display = "block";
    } else {
        login.style.display = "block";
        register.style.display = "none";
    }
}

// 4. Password Strength Meter
function checkStrength(password) {
    const bar = document.getElementById('strength-bar');
    let strength = 0;
    if (password.length > 5) strength += 40;
    if (/[A-Z]/.test(password)) strength += 30;
    if (/[0-9]/.test(password)) strength += 30;

    bar.style.width = strength + "%";
    
    if (strength < 50) bar.style.backgroundColor = "#ff4d4d"; // Error color
    else if (strength < 90) bar.style.backgroundColor = "#ffad33"; // Warning color
    else bar.style.backgroundColor = "#2eb82e"; // Success color
}

// 5. Hero Action Handler
function handleAction(action) {
    if (action === 'Booking' || action === 'Status') {
        alert(action + " feature is coming soon! Check View Schedules for now.");
    }
}

// Update the action handler to redirect to booking.html
function handleAction(action) {
    if (action === 'Booking') {
        window.location.href = 'booking.html';
    } else if (action === 'Status') {
        alert("Status feature is coming soon!");
    }
}

function confirmFinalBooking() {
    const name = document.getElementById('passName').value;
    const selectedCount = document.querySelectorAll('.seat-box.selected').length;

    if (!name) {
        alert("Please enter the passenger name.");
        return;
    }
    if (selectedCount === 0) {
        alert("Please select at least one seat.");
        return;
    }

    alert(`Successfully Booked!\n\nPassenger: ${name}\nSeats: ${selectedCount}\n\nHave a safe trip with BusGo!`);
    window.location.href = 'index.html';
}

function handleAction(action) {
    if (action === 'Booking') {
        window.location.href = 'booking.html';
    } else if (action === 'Status') {
        window.location.href = 'status.html'; // Now links to the new page
    } else if (action === 'Schedules') {
        window.location.href = 'schedules.html';
    }
}

// Function for the Cancel Ticket button
function handleCancel() {
    if (confirm("Are you sure you want to cancel this ticket?")) {
        alert("Ticket BG8745123 has been successfully cancelled.");
        window.location.href = 'index.html';
    }
}
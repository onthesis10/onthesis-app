// File: app/static/js/script.js
// Menggunakan modul Firebase yang sudah diinisialisasi

import { auth } from './firebase.js';
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

onAuthStateChanged(auth, (user) => {
    const mainContainer = document.getElementById('main-app-container');
    if (user) {
        if (mainContainer) mainContainer.style.visibility = 'visible';
        
        const userDisplayNameEl = document.getElementById('user-display-name');
        const userPhotoEl = document.getElementById('user-photo-header');

        if (userDisplayNameEl) userDisplayNameEl.textContent = user.displayName || 'Pengguna';
        if (userPhotoEl) userPhotoEl.src = user.photoURL || `https://ui-avatars.com/api/?name=${user.displayName || 'U'}&background=161B22&color=E6EDF3`;
        
    } else {
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    }
});

const handleActiveNavLinks = () => {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const linkPath = new URL(link.href).pathname.replace(/\/$/, '');
        const currentBasePath = currentPath.replace(/\/$/, '');
        if (linkPath === currentBasePath || (currentBasePath === '' && linkPath.endsWith('/dashboard'))) {
            link.classList.add('active');
        }
    });
};

const handleLogout = () => {
    const logoutBtn = document.querySelector('a[href="/logout"]'); // Jika ada tombol logout khusus
    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            signOut(auth).then(() => {
                window.location.href = '/login';
            }).catch((error) => console.error("Error saat logout:", error));
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    handleActiveNavLinks();
    handleLogout();
});

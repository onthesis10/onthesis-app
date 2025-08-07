// File: app/static/js/script.js
// Mengelola otentikasi, link aktif, dan TEMA

import { auth } from './firebase.js';
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

// --- FUNGSI PENGELOLA TEMA ---
const handleThemeToggle = () => {
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');

    if (!themeToggleBtn || !sunIcon || !moonIcon) return;

    // Fungsi untuk menerapkan tema dan ikon yang sesuai
    const applyTheme = (theme) => {
        if (theme === 'light') {
            document.documentElement.classList.add('light');
            sunIcon.classList.remove('hidden');
            moonIcon.classList.add('hidden');
        } else {
            document.documentElement.classList.remove('light');
            sunIcon.classList.add('hidden');
            moonIcon.classList.remove('hidden');
        }
    };

    // Mendapatkan tema saat ini (prioritas: localStorage > preferensi sistem)
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    let currentTheme = savedTheme ? savedTheme : (systemPrefersDark ? 'dark' : 'light');
    
    // Terapkan tema saat halaman dimuat
    applyTheme(currentTheme);

    // Tambahkan event listener ke tombol
    themeToggleBtn.addEventListener('click', () => {
        const newTheme = document.documentElement.classList.contains('light') ? 'dark' : 'light';
        localStorage.setItem('theme', newTheme);
        applyTheme(newTheme);
    });
};


// --- FUNGSI LAINNYA ---
onAuthStateChanged(auth, (user) => {
    const mainContainer = document.querySelector('.main-canvas');
    if (user) {
        if (mainContainer) mainContainer.style.visibility = 'visible';
        
        const userPhotoEl = document.getElementById('user-photo-header');
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

// --- INISIALISASI SAAT DOM SIAP ---
document.addEventListener('DOMContentLoaded', () => {
    handleActiveNavLinks();
    handleThemeToggle(); // Jalankan fungsi tema
});

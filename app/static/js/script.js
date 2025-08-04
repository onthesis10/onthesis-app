// Ganti seluruh isi file script.js Anda dengan kode ini

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { 
    getAuth, 
    onAuthStateChanged, 
    signOut,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const firebaseConfig = {
    apiKey: "AIzaSyAEkuE7wK6knIXwejAfjSb8oxArj4gsH5w",
    authDomain: "onthesis.firebaseapp.com",
    projectId: "onthesis",
    storageBucket: "onthesis.appspot.com",
    messagingSenderId: "258634496518",
    appId: "1:258634496518:web:5053a01aeb4d8367366187",
    measurementId: "G-FMM4FZ6GN2"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app); 

onAuthStateChanged(auth, async (user) => {
    if (user) {
        App.userDisplayName = user.displayName || 'Pengguna';
        document.getElementById('main-app-container').style.visibility = 'visible';
        
        const userDisplayNameEl = document.getElementById('user-display-name');
        const userPhotoEl = document.getElementById('user-photo');

        if (userDisplayNameEl) {
            userDisplayNameEl.textContent = App.userDisplayName;
        }
        if (userPhotoEl) {
            userPhotoEl.src = user.photoURL || `https://ui-avatars.com/api/?name=${App.userDisplayName}&background=random`;
        }
        
        App.init();
    } else {
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    }
});

const App = {
    userDisplayName: 'Pengguna',

    init() {
        this.handleThemeToggle();
        this.handleLogout();
        this.handleActiveNavLinks();
        // Panggilan fungsi kuota dihapus dari sini
    },

    handleThemeToggle() {
        const themeToggleBtn = document.getElementById('theme-toggle');
        if (!themeToggleBtn) return;

        const sunIcon = document.getElementById('theme-toggle-sun-icon');
        const moonIcon = document.getElementById('theme-toggle-moon-icon');

        const applyTheme = (isDark) => {
            if (isDark) {
                document.documentElement.classList.add('dark');
                moonIcon?.classList.add('hidden');
                sunIcon?.classList.remove('hidden');
            } else {
                document.documentElement.classList.remove('dark');
                moonIcon?.classList.remove('hidden');
                sunIcon?.classList.add('hidden');
            }
        };

        const savedTheme = localStorage.getItem('color-theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const isDark = savedTheme === 'dark' || (savedTheme === null && prefersDark);
        applyTheme(isDark);

        themeToggleBtn.addEventListener('click', () => {
            const isCurrentlyDark = document.documentElement.classList.contains('dark');
            localStorage.setItem('color-theme', isCurrentlyDark ? 'light' : 'dark');
            applyTheme(!isCurrentlyDark);
        });
    },

    handleLogout() {
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                signOut(auth).catch((error) => console.error("Error saat logout:", error));
            });
        }
    },

    handleActiveNavLinks() {
        const currentPath = window.location.pathname;
        const navLinks = document.querySelectorAll('.nav-link');
        
        navLinks.forEach(link => {
            const linkPath = new URL(link.href).pathname.replace(/\/$/, '');
            const currentBasePath = currentPath.replace(/\/$/, '');
            if (linkPath === currentBasePath || (currentBasePath === '/' && linkPath.endsWith('/dashboard'))) {
                link.classList.add('active');
            }
        });
    },

    // Fungsi untuk mengambil kuota telah dihapus dari file utama ini
};

window.App = App;
window.auth = auth;

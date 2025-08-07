// File: app/static/js/firebase.js
// Deskripsi: Inisialisasi Firebase untuk digunakan di seluruh aplikasi.

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

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
const db = getFirestore(app);

export { db, auth, app };

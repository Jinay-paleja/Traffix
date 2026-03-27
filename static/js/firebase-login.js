// Firebase v10 SDK initialization and Google Sign-In for Traffix
// https://firebase.google.com/docs/web/setup

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import { getAuth, GoogleAuthProvider, signInWithPopup, getIdToken } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';

const firebaseConfig = {
  apiKey: "AIzaSyC-tnjkrhHygkG60Nq0yOk0Y4W3oFqpHsI",
  authDomain: "traffix-40acf.firebaseapp.com",
  projectId: "traffix-40acf",
  storageBucket: "traffix-40acf.firebasestorage.app",
  messagingSenderId: "622309834466",
  appId: "1:622309834466:web:04e38961b2ff6be12828bb",
  measurementId: "G-27655CG8PK"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Google Sign-In handler
const googleBtn = document.getElementById('google-signin-btn');
if (googleBtn) {
  googleBtn.addEventListener('click', async function () {
    try {
      console.log('Starting Google Sign-In...');
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      console.log('Sign-In successful:', result.user);
      
      const idToken = await getIdToken(result.user);
      console.log('ID Token obtained, sending to backend...');
      
      const response = await fetch('/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ idToken }),
      });
      
      const data = await response.json();
      console.log('Backend response:', data);
      
      if (data.success) {
        window.location.href = '/dashboard';
      } else {
        alert(data.message || 'Login failed');
      }
    } catch (error) {
      console.error('Google Sign-In error:', error);
      alert('Sign-in failed: ' + error.message);
    }
  });
}

// Email/Password login (if form used)
const loginForm = document.getElementById('login-form');
if (loginForm) {
  loginForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    try {
      const email = document.getElementById('email').value;
      const password = document.getElementById('password').value;
      
      console.log('Starting email/password login...');
      const result = await signInWithEmailAndPassword(auth, email, password);
      const idToken = await getIdToken(result.user);
      
      const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idToken }),
      });
      
      const data = await response.json();
      if (data.success) {
        window.location.href = '/dashboard';
      } else {
        alert(data.message || 'Login failed');
      }
    } catch (error) {
      console.error('Login error:', error);
      alert(error.message);
    }
  });
}


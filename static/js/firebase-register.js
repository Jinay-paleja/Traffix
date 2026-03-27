// Firebase v10 SDK for registration
// Load after firebase-app.js (if separate), but standalone import here

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import { getAuth, createUserWithEmailAndPassword, updateProfile } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';

const firebaseConfig = {
  apiKey: "AIzaSyC-tnjkrhHygkG60Nq0yOk0Y4W3oFqpHsI",
  authDomain: "traffix-40acf.firebaseapp.com",
  projectId: "traffix-40acf",
  storageBucket: "traffix-40acf.firebasestorage.app",
  messagingSenderId: "622309834466",
  appId: "1:622309834466:web:04e38961b2ff6be12828bb",
  measurementId: "G-27655CG8PK"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

const registerForm = document.getElementById('register-form');
if (registerForm) {
  registerForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    try {
      const name = document.getElementById('name').value.trim();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const confirm = document.getElementById('confirm-password').value;
      
      if (password !== confirm) {
        alert('Passwords do not match');
        return;
      }
      if (password.length < 8) {
        alert('Password must be at least 8 characters');
        return;
      }
      
      console.log('Creating user...');
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      await updateProfile(userCredential.user, { displayName: name });
      
      console.log('User created successfully');
      alert('Account created! Redirecting to login...');
      window.location.href = '/login';
    } catch (error) {
      console.error('Registration error:', error);
      alert('Registration failed: ' + error.message);
    }
  });
}


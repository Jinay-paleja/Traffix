// Firebase v9 compat - Email/Password Authentication
const firebaseConfig = {
  apiKey: "AIzaSyC9PQmiPza6U5wkffC1qPAQHgMOfAgZgQM",
  authDomain: "traffix-c507d.firebaseapp.com",
  projectId: "traffix-c507d",
  storageBucket: "traffix-c507d.firebasestorage.app",
  messagingSenderId: "34975360182",
  appId: "1:34975360182:web:662683d39c1a3750ba7217",
  measurementId: "G-KWD0WPNJNK"
};

// Initialize Firebase
if (!window.firebaseAppsInitialized) {
  firebase.initializeApp(firebaseConfig);
  window.firebaseAppsInitialized = true;
  console.log('✓ Firebase initialized');
}

const auth = firebase.auth();

// Handle email/password login form submission
document.addEventListener('DOMContentLoaded', function() {
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      
      console.log('📧 Email/Password login attempt:', email);
      
      try {
        // Sign in with Firebase
        console.log('Signing in with Firebase...');
        const userCredential = await auth.signInWithEmailAndPassword(email, password);
        console.log('✓ Firebase authentication successful');
        console.log('User:', userCredential.user.email);
        
        // Get ID token
        const idToken = await userCredential.user.getIdToken();
        console.log('✓ ID Token obtained');
        
        // Send token to backend
        console.log('Sending token to backend...');
        const response = await fetch('/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ idToken }),
        });
        
        const data = await response.json();
        console.log('Response:', data);
        
        if (data.success) {
          console.log('✓✓✓ LOGIN SUCCESSFUL ✓✓✓');
          setTimeout(() => {
            window.location.href = '/dashboard';
          }, 500);
        } else {
          console.error('❌ Backend error:', data.message);
          alert('Login failed: ' + (data.message || 'Unknown error'));
        }
      } catch (error) {
        console.error('❌ Login failed:', error.code, error.message);
        
        // User-friendly error messages
        let errMsg = 'Login failed';
        if (error.code === 'auth/user-not-found') {
          errMsg = 'User not found. Please create an account.';
        } else if (error.code === 'auth/wrong-password') {
          errMsg = 'Incorrect password.';
        } else if (error.code === 'auth/invalid-email') {
          errMsg = 'Invalid email address.';
        } else if (error.code === 'auth/user-disabled') {
          errMsg = 'User account has been disabled.';
        }
        
        alert(errMsg);
      }
    });
  }
});

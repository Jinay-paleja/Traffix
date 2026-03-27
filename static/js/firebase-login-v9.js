// Firebase v9 compat (legacy namespace) for stable Google Sign-In - Traffix
// Use v9.0 compat layer for firebase.auth() global API (avoid v10 module issues on localhost)

const firebaseConfig = {
  apiKey: "AIzaSyC-tnjkrhHygkG60Nq0yOk0Y4W3oFqpHsI",
  authDomain: "traffix-40acf.firebaseapp.com",
  projectId: "traffix-40acf",
  storageBucket: "traffix-40acf.firebasestorage.app",
  messagingSenderId: "622309834466",
  appId: "1:622309834466:web:04e38961b2ff6be12828bb",
  measurementId: "G-27655CG8PK"
};

// Initialize only if not already
if (!window.firebaseAppsInitialized) {
  window.firebaseConfig = firebaseConfig;  // Global config
  firebase.initializeApp(firebaseConfig);
  window.firebaseAppsInitialized = true;
  console.log('Firebase initialized successfully');
} else {
  console.log('Firebase already initialized');
}

const auth = firebase.auth();

// Google Sign-In with detailed logging
const googleBtn = document.getElementById('google-signin-btn');
if (googleBtn) {
  googleBtn.addEventListener('click', function () {
    console.log('Google Sign-In clicked');
    const provider = new firebase.auth.GoogleAuthProvider();
    provider.addScope('email');
    provider.setCustomParameters({ prompt: 'select_account' });
    
    firebase.auth().signInWithPopup(provider)
      .then((result) => {
        console.log('Google Sign-In result:', result);
        console.log('User:', result.user);
        return result.user.getIdToken();
      })
      .then((idToken) => {
        console.log('ID Token:', idToken ? 'obtained' : 'null');
        return fetch('/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ idToken }),
        });
      })
      .then(response => {
        console.log('Backend response status:', response.status);
        return response.json();
      })
      .then(data => {
        console.log('Backend data:', data);
        if (data.success) {
          console.log('Redirecting to dashboard');
          window.location.href = '/dashboard';
        } else {
          console.error('Backend error:', data.message);
          alert(data.message || 'Login failed');
        }
      })
      .catch((error) => {
        console.error('Full Sign-In error:', error);
        console.error('Error code:', error.code);
        console.error('Error message:', error.message);
        alert(`Sign-in failed: ${error.message}`);
      });
  });
}

// Email login fallback
const loginForm = document.getElementById('login-form');
if (loginForm) {
  loginForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const email = document.getElementById('email')?.value;
    const password = document.getElementById('password')?.value;
    if (!email || !password) {
      alert('Please enter email and password');
      return;
    }
    
    firebase.auth().signInWithEmailAndPassword(email, password)
      .then((result) => {
        console.log('Email login success');
        return result.user.getIdToken();
      })
      .then(idToken => {
        return fetch('/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ idToken }),
        });
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          window.location.href = '/dashboard';
        } else {
          alert(data.message || 'Login failed');
        }
      })
      .catch(error => {
        console.error('Email login error:', error);
        alert(error.message);
      });
  });
}


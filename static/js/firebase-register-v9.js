// Firebase v9 compat for user registration - Traffix
// Uses compat SDK for consistency with login page

const firebaseConfig = {
  apiKey: "AIzaSyC9PQmiPza6U5wkffC1qPAQHgMOfAgZgQM",
  authDomain: "traffix-c507d.firebaseapp.com",
  projectId: "traffix-c507d",
  storageBucket: "traffix-c507d.firebasestorage.app",
  messagingSenderId: "34975360182",
  appId: "1:34975360182:web:662683d39c1a3750ba7217",
  measurementId: "G-KWD0WPNJNK"
};

// Initialize only if not already
if (!window.firebaseAppsInitialized) {
  window.firebaseConfig = firebaseConfig;
  firebase.initializeApp(firebaseConfig);
  window.firebaseAppsInitialized = true;
  console.log('Firebase initialized successfully');
} else {
  console.log('Firebase already initialized');
}

const auth = firebase.auth();

// Handle registration form
const registerForm = document.getElementById('register-form');
if (registerForm) {
  registerForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    
    const name = document.getElementById('name')?.value.trim();
    const email = document.getElementById('email')?.value.trim();
    const password = document.getElementById('password')?.value;
    const confirm = document.getElementById('confirm-password')?.value;
    const btnSubmit = registerForm.querySelector('button[type="submit"]');
    const originalText = btnSubmit.textContent;
    
    try {
      // Validation
      if (!name || !email || !password || !confirm) {
        alert('Please fill in all fields');
        return;
      }
      
      if (password !== confirm) {
        alert('Passwords do not match');
        return;
      }
      
      if (password.length < 8) {
        alert('Password must be at least 8 characters');
        return;
      }
      
      // Disable button and show loading state
      btnSubmit.disabled = true;
      btnSubmit.textContent = 'Creating account...';
      
      console.log('Creating user with email:', email);
      
      // Create user in Firebase
      const userCredential = await firebase.auth().createUserWithEmailAndPassword(email, password);
      console.log('User created, updating profile...');
      
      // Update profile with display name
      await userCredential.user.updateProfile({
        displayName: name
      });
      
      console.log('User profile updated successfully');
      alert('Account created successfully! Redirecting to login...');
      
      // Redirect to login
      window.location.href = '/login';
    } catch (error) {
      console.error('Registration error:', error);
      
      let message = 'Registration failed: ' + error.message;
      
      if (error.code === 'auth/email-already-in-use') {
        message = 'This email is already registered. Please log in instead.';
      } else if (error.code === 'auth/invalid-email') {
        message = 'Please enter a valid email address.';
      } else if (error.code === 'auth/weak-password') {
        message = 'Password is too weak. Please use at least 8 characters with a mix of uppercase, lowercase, numbers, and symbols.';
      }
      
      alert(message);
      btnSubmit.disabled = false;
      btnSubmit.textContent = originalText;
    }
  });
}

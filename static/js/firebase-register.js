// Firebase compat SDK registration flow for Flask templates.
const firebaseConfig = window.FIREBASE_WEB_CONFIG || {};
const requiredConfigFields = ["apiKey", "authDomain", "projectId", "appId"];
const missingConfigFields = requiredConfigFields.filter((key) => !firebaseConfig[key]);

if (missingConfigFields.length) {
  console.error("Missing Firebase web config fields:", missingConfigFields.join(", "));
  alert("Firebase is not configured for this app yet. Please set FIREBASE_WEB_* environment variables.");
  throw new Error("Firebase client configuration missing");
}

if (!window.firebaseAppsInitialized) {
  firebase.initializeApp(firebaseConfig);
  window.firebaseAppsInitialized = true;
}

const auth = firebase.auth();

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
      const userCredential = await auth.createUserWithEmailAndPassword(email, password);
      await userCredential.user.updateProfile({ displayName: name });
      
      console.log('User created successfully');
      alert('Account created! Redirecting to login...');
      window.location.href = '/login';
    } catch (error) {
      console.error('Registration error:', error);
      alert('Registration failed: ' + error.message);
    }
  });
}


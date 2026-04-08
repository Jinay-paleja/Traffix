# Traffix - Smart Traffic Signal Optimizer

A Python-based web application for the Smart Traffic Signal Optimizer (Intelligent Transportation System). It includes a homepage, user registration, login, and a simple dashboard.

## Setup

1. Create a virtual environment (recommended):

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure Firebase:

   Place your Firebase Admin SDK service account JSON in the project root and update the filename in [app.py](/c:/Users/manas/College%20Project/Traffix/app.py) if needed.

4. Run the app:

   ```bash
   python app.py
   ```

5. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Project structure

- `app.py` - Flask application, routes, Firebase Auth, and Firestore persistence
- `templates/` - Jinja2 HTML templates
- `static/css/` - Styles
- `static/js/` - Client-side scripts
- `data/` - Legacy local JSON files retained only for one-time migration into Firestore

## Features

- **Homepage** - Problem intro, value proposition, and CTAs
- **Registration** - Full name, email, password handled through Firebase Authentication
- **Login / Logout** - Session-based auth backed by Firebase Auth
- **Dashboard** - Placeholder after login (ready for traffic controls later)

## Data storage

Traffix now stores application data in Firebase Firestore for:

- users/profile metadata
- intersections
- traffic history
- intersection media metadata

If legacy JSON files already exist in `data/`, the app imports them into Firestore automatically the first time each dataset is loaded.

For production, set the `SECRET_KEY` environment variable and use a proper WSGI server.

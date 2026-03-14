# Traffix – Smart Traffic Signal Optimizer

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

3. Run the app:

   ```bash
   python app.py
   ```

4. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## Project structure

- `app.py` – Flask application and routes (home, login, register, dashboard, logout)
- `templates/` – Jinja2 HTML templates
- `static/css/` – Styles
- `static/js/` – Client-side scripts
- `data/users.json` – User store (created on first registration; set `SECRET_KEY` in production)

## Features

- **Homepage** – Problem intro, value proposition, and CTAs
- **Registration** – Full name, email, password (stored hashed in `data/users.json`)
- **Login / Logout** – Session-based auth
- **Dashboard** – Placeholder after login (ready for traffic controls later)

For production, set the `SECRET_KEY` environment variable and use a proper database and WSGI server (e.g. Gunicorn).

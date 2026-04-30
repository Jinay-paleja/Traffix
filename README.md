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

### Firebase configuration

This project now reads Firebase settings from environment variables so you can switch projects safely.

1. Copy `.env.example` to `.env`
2. Fill in your new Firebase project's values:
   - Backend Admin SDK: `FIREBASE_SERVICE_ACCOUNT_PATH` (or `FIREBASE_SERVICE_ACCOUNT_JSON`)
   - Frontend Web SDK: all `FIREBASE_WEB_*` variables
3. Ensure `.firebaserc` has your real Firebase project ID in `projects.default`

Optional Firebase CLI deploy commands:

```bash
firebase login
firebase use --add
firebase deploy --only firestore:rules,firestore:indexes
```

## Project structure

- `app.py` – Flask application and routes (home, login, register, dashboard, logout)
- `templates/` – Jinja2 HTML templates
- `static/css/` – Styles
- `static/js/` – Client-side scripts
- Firestore collections: `users`, `intersections`, `lanes`, `cameras`, `traffic_analyses`, `lane_analyses`, `lane_media`

## Features

- **Homepage** – Problem intro, value proposition, and CTAs
- **Registration** – Full name, email, password (stored hashed in `data/users.json`)
- **Login / Logout** – Session-based auth
- **Dashboard** – Placeholder after login (ready for traffic controls later)

## Firestore data model (ER-aligned)

- `users` -> `user_id`, `name`, `email`, `role`
- `intersections` -> `intersection_id`, `name`, `location`, `num_roads`
- `lanes` -> `lane_id`, `intersection_id`, `name`, `direction`, `camera_id`
- `cameras` -> `camera_id`, `lane_id`, `status`, `stream_url`
- `traffic_analyses` -> `analysis_id`, `intersection_id`, `analysis_mode`, `timestamp`, `event_duration_minutes`, `lanes_analyzed`, `total_vehicles`, `green_time`
- `lane_analyses` -> `lane_analysis_id`, `analysis_id`, `lane_id`, `vehicle_count`, `density_level`, `suggested_green_time`
- `lane_media` -> `media_id`, `lane_analysis_id`, `camera_id`, `video_url`, `uploaded_at`

For production, set the `SECRET_KEY` environment variable and run behind a proper WSGI server (e.g. Gunicorn).

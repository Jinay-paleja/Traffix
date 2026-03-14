"""
Traffix – Smart Traffic Signal Optimizer
Python web application (Flask).
"""
import os
import json
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.secret_key = os.environ.get("SECRET_KEY", "traffix-dev-secret-change-in-production")

USERS_FILE = BASE_DIR / "data" / "users.json"
INTERSECTIONS_FILE = BASE_DIR / "data" / "intersections.json"


def load_intersections():
    if not INTERSECTIONS_FILE.exists():
        return []
    try:
        with open(INTERSECTIONS_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return []
            return json.loads(data).get("intersections", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_intersections(intersections):
    INTERSECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INTERSECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"intersections": intersections}, f, indent=2)


def get_intersection(intersection_id):
    intersections = load_intersections()
    for intersection in intersections:
        if intersection["id"] == intersection_id:
            return intersection
    return None


def toggle_camera(intersection_id, lane_id):
    from datetime import datetime
    intersections = load_intersections()
    for intersection in intersections:
        if intersection["id"] == intersection_id:
            for lane in intersection.get("lanes", []):
                if lane["id"] == lane_id:
                    lane["camera"]["status"] = not lane["camera"]["status"]
                    save_intersections(intersections)
                    return True
    return False


def add_intersection(name, location):
    intersections = load_intersections()
    new_id = f"int-{len(intersections) + 1:03d}"
    new_intersection = {
        "id": new_id,
        "name": name,
        "location": location,
        "status": "active",
        "lanes": [
            {"id": "lane-n", "name": "Northbound", "direction": "north", "camera": {"id": f"cam-{new_id}-n", "name": "North Lane Camera", "status": True}},
            {"id": "lane-s", "name": "Southbound", "direction": "south", "camera": {"id": f"cam-{new_id}-s", "name": "South Lane Camera", "status": True}},
            {"id": "lane-e", "name": "Eastbound", "direction": "east", "camera": {"id": f"cam-{new_id}-e", "name": "East Lane Camera", "status": True}},
            {"id": "lane-w", "name": "Westbound", "direction": "west", "camera": {"id": f"cam-{new_id}-w", "name": "West Lane Camera", "status": True}}
        ]
    }
    intersections.append(new_intersection)
    save_intersections(intersections)
    return new_intersection


def remove_intersection(intersection_id):
    intersections = load_intersections()
    intersections = [i for i in intersections if i["id"] != intersection_id]
    save_intersections(intersections)
    return True


def load_users():
    if not USERS_FILE.exists():
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return {}
            return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(users):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def get_user_by_email(email):
    users = load_users()
    return users.get(email.strip().lower())


def register_user(name, email, password):
    users = load_users()
    email_key = email.strip().lower()
    if email_key in users:
        return False, "An account with this email already exists."
    users[email_key] = {
        "name": name.strip(),
        "email": email_key,
        "password_hash": generate_password_hash(password, method="pbkdf2:sha256"),
    }
    save_users(users)
    return True, None


def check_password(email, password):
    user = get_user_by_email(email)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return user


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        print(f"[DEBUG] Login attempt - Email: {email}")
        
        if not email or not password:
            flash("Please enter email and password.", "error")
            return redirect(url_for("login"))
        
        user = check_password(email, password)
        
        print(f"[DEBUG] User found: {user is not None}")
        
        if not user:
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))
        
        session["user_id"] = user["email"]
        session["user_name"] = user["name"]
        flash(f"Welcome back, {user['name']}!", "success")
        
        print(f"[DEBUG] Login successful for: {email}")
        
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm-password", "")
        if not name or not email or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("register"))
        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))
        ok, err = register_user(name, email, password)
        if not ok:
            flash(err, "error")
            return redirect(url_for("register"))
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to view the dashboard.", "error")
        return redirect(url_for("login"))
    
    # Calculate real-time stats from data
    intersections = load_intersections()
    total_intersections = len(intersections)
    
    # Count active signals (lanes with cameras enabled)
    active_signals = 0
    sensors_connected = 0
    
    for intersection in intersections:
        if intersection.get("status") == "active":
            for lane in intersection.get("lanes", []):
                if lane.get("camera", {}).get("status"):
                    active_signals += 1
                    sensors_connected += 1
    
    stats = {
        "intersections": total_intersections,
        "active_signals": active_signals,
        "sensors": sensors_connected
    }
    
    return render_template("dashboard.html", user_name=session.get("user_name", "User"), stats=stats)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please log in to view your profile.", "error")
        return redirect(url_for("login"))
    
    user_email = session["user_id"]
    users = load_users()
    user = users.get(user_email)
    
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("logout"))
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_profile":
            new_name = request.form.get("name", "").strip()
            if not new_name:
                flash("Name cannot be empty.", "error")
            else:
                users[user_email]["name"] = new_name
                save_users(users)
                session["user_name"] = new_name
                flash("Profile updated successfully!", "success")
        
        elif action == "change_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            
            if not current_password or not new_password or not confirm_password:
                flash("Please fill in all password fields.", "error")
            elif not check_password_hash(user["password_hash"], current_password):
                flash("Current password is incorrect.", "error")
            elif len(new_password) < 8:
                flash("New password must be at least 8 characters.", "error")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "error")
            else:
                users[user_email]["password_hash"] = generate_password_hash(new_password, method="pbkdf2:sha256")
                save_users(users)
                flash("Password changed successfully!", "success")
        
        return redirect(url_for("profile"))
    
    return render_template("profile.html", user=user)


@app.route("/intersections")
def intersections():
    if "user_id" not in session:
        flash("Please log in to view intersections.", "error")
        return redirect(url_for("login"))
    intersections = load_intersections()
    return render_template("intersections.html", intersections=intersections)


@app.route("/intersection/<intersection_id>")
def intersection_detail(intersection_id):
    if "user_id" not in session:
        flash("Please log in to view intersection details.", "error")
        return redirect(url_for("login"))
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    return render_template("intersection_detail.html", intersection=intersection)


@app.route("/camera/toggle/<intersection_id>/<lane_id>", methods=["POST"])
def camera_toggle(intersection_id, lane_id):
    if "user_id" not in session:
        flash("Please log in to manage cameras.", "error")
        return redirect(url_for("login"))
    
    success = toggle_camera(intersection_id, lane_id)
    if success:
        flash("Camera status updated successfully!", "success")
    else:
        flash("Camera not found.", "error")
    
    return redirect(url_for("intersection_detail", intersection_id=intersection_id))


@app.route("/intersection/add", methods=["POST"])
def intersection_add():
    if "user_id" not in session:
        flash("Please log in to add intersections.", "error")
        return redirect(url_for("login"))
    
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    
    if not name or not location:
        flash("Please provide both name and location.", "error")
        return redirect(url_for("intersections"))
    
    new_intersection = add_intersection(name, location)
    flash(f"Intersection '{name}' added successfully!", "success")
    return redirect(url_for("intersection_detail", intersection_id=new_intersection["id"]))


@app.route("/intersection/delete/<intersection_id>", methods=["POST"])
def intersection_delete(intersection_id):
    if "user_id" not in session:
        flash("Please log in to delete intersections.", "error")
        return redirect(url_for("login"))
    
    remove_intersection(intersection_id)
    flash("Intersection deleted successfully!", "success")
    return redirect(url_for("intersections"))


@app.errorhandler(404)
def not_found(e):
    return render_template("index.html"), 404


@app.errorhandler(500)
def server_error(e):
    return (
        "<h1>Something went wrong</h1><p>Check the terminal where you ran <code>python app.py</code> for the error details.</p>"
        "<p><a href='/'>Go to homepage</a></p>",
        500,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)

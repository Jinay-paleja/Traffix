from functools import wraps

# Decorator to protect routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_uid" not in session and "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
"""
Traffix – Smart Traffic Signal Optimizer
Python web application (Flask).
"""
import os
import json
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials

# Initialize Firebase Admin with service account
cred = credentials.Certificate("traffix-40acf-firebase-adminsdk-fbsvc-b4a43d8111.json")
firebase_admin.initialize_app(cred)

from firebase_admin import auth

# Firebase Authentication helper functions
def create_firebase_user(email, password, display_name=None):
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name
        )
        return user
    except Exception as e:
        return None

def verify_firebase_token(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        return None

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.secret_key = os.environ.get("SECRET_KEY", "traffix-dev-secret-change-in-production")

USERS_FILE = BASE_DIR / "data" / "users.json"
INTERSECTIONS_FILE = BASE_DIR / "data" / "intersections.json"


def _normalize_intersections(intersections):
    """
    Best-effort data migration for intersections.json.
    Ensures lanes have unique IDs per intersection and that camera objects are present.
    """
    changed = False

    for intersection in intersections or []:
        lanes = intersection.get("lanes") or []
        if not isinstance(lanes, list):
            intersection["lanes"] = []
            changed = True
            continue

        seen_lane_ids = set()
        seen_cam_ids = set()

        for idx, lane in enumerate(lanes):
            if not isinstance(lane, dict):
                continue

            direction = (lane.get("direction") or "").strip().lower()
            if not direction:
                direction = f"lane{idx+1}"
                lane["direction"] = direction
                changed = True

            # Ensure camera exists
            camera = lane.get("camera")
            if not isinstance(camera, dict):
                camera = {}
                lane["camera"] = camera
                changed = True

            # Normalize lane id (must be unique within intersection)
            lane_id = lane.get("id")
            if not lane_id or lane_id in seen_lane_ids:
                base = f"lane-{direction.replace(' ', '-')}"
                candidate = base
                n = 2
                while candidate in seen_lane_ids:
                    candidate = f"{base}-{n}"
                    n += 1
                lane["id"] = candidate
                lane_id = candidate
                changed = True
            seen_lane_ids.add(lane_id)

            # Normalize camera id (must be unique within intersection)
            cam_id = camera.get("id")
            if not cam_id or cam_id in seen_cam_ids:
                int_id = intersection.get("id", "int-unknown")
                base = f"cam-{int_id}-{direction.replace(' ', '-')}"
                candidate = base
                n = 2
                while candidate in seen_cam_ids:
                    candidate = f"{base}-{n}"
                    n += 1
                camera["id"] = candidate
                cam_id = candidate
                changed = True
            seen_cam_ids.add(cam_id)

            # Fill camera defaults
            if "name" not in camera:
                camera["name"] = f"{direction.title()} Lane Camera"
                changed = True
            if "status" not in camera:
                camera["status"] = True
                changed = True
            stream_url = camera.get("stream_url")
            if not stream_url:
                camera["stream_url"] = f"https://example.com/stream/{cam_id}"
                changed = True
            else:
                # If the stream URL is still the default placeholder, keep it in sync with camera.id.
                placeholder_prefix = "https://example.com/stream/"
                if isinstance(stream_url, str) and stream_url.startswith(placeholder_prefix) and not stream_url.endswith(cam_id):
                    camera["stream_url"] = f"{placeholder_prefix}{cam_id}"
                    changed = True

    return intersections, changed


def load_intersections():
    if not INTERSECTIONS_FILE.exists():
        return []
    try:
        with open(INTERSECTIONS_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return []
            intersections = json.loads(data).get("intersections", [])
            intersections, changed = _normalize_intersections(intersections)
            if changed:
                save_intersections(intersections)
            return intersections
    except (json.JSONDecodeError, OSError):
        return []


def save_intersections(intersections):
    INTERSECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INTERSECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"intersections": intersections}, f, indent=2)


# Migrate/normalize stored intersection data on startup (safe no-op if already clean).
# This prevents duplicate lane IDs/camera IDs from breaking detail pages and toggles.
try:
    _ = load_intersections()
except Exception:
    # Avoid crashing the app if the data file is unreadable; routes will handle empty data.
    pass


def get_intersection(intersection_id):
    intersections = load_intersections()
    for intersection in intersections:
        if intersection["id"] == intersection_id:
            return intersection
    return None


def toggle_camera(intersection_id, lane_id):
    intersections = load_intersections()
    for intersection in intersections:
        if intersection["id"] == intersection_id:
            for lane in intersection.get("lanes", []):
                if lane["id"] == lane_id:
                    if "stream_url" not in lane["camera"]:
                        lane["camera"]["stream_url"] = f"https://example.com/stream/{lane['camera']['id']}"
                    lane["camera"]["status"] = not lane["camera"]["status"]
                    save_intersections(intersections)
                    return True
    return False


def set_all_cameras(intersection_id, enabled):
    intersections = load_intersections()
    for intersection in intersections:
        if intersection["id"] == intersection_id:
            changed = False
            for lane in intersection.get("lanes", []):
                camera = lane.get("camera") or {}
                if "stream_url" not in camera:
                    camera["stream_url"] = f"https://example.com/stream/{camera.get('id', lane['id'])}"
                if camera.get("status") != enabled:
                    camera["status"] = enabled
                    changed = True
            if changed:
                save_intersections(intersections)
            return True
    return False


def add_intersection(name, location, num_roads=4):
    intersections = load_intersections()
    new_id = f"int-{len(intersections) + 1:03d}"
    
    # Directions for different road counts
    directions = {
        3: ['north', 'southeast', 'southwest'],
        4: ['north', 'south', 'east', 'west'],
        5: ['north', 'northeast', 'southeast', 'southwest', 'west'],
        6: ['north', 'northeast', 'southeast', 'south', 'southwest', 'northwest']
    }
    
    dir_list = directions.get(num_roads, directions[4])
    
    lanes = []
    for i, direction in enumerate(dir_list):
        safe_dir = direction.replace(" ", "-").lower()
        lane_id = f"lane-{safe_dir}"
        cam_id = f"cam-{new_id}-{safe_dir}"
        lanes.append({
            "id": lane_id,
            "name": f"{direction.title()}bound",
            "direction": direction,
            "camera": {
                "id": cam_id,
                "name": f"{direction.title()} Lane Camera",
                "status": True,
                "stream_url": f"https://example.com/stream/{cam_id}"
            }
        })
    
    new_intersection = {
        "id": new_id,
        "name": name,
        "location": location,
        "num_roads": num_roads,
        "status": "active",
        "lanes": lanes
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
    # Try to create user in Firebase Authentication
    try:
        user = create_firebase_user(email=email, password=password, display_name=name)
        if user:
            return True, None
        else:
            return False, "Failed to create user in Firebase."
    except Exception as e:
        return False, str(e)


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
        if request.is_json:
            data = request.get_json()
            id_token = data.get("idToken")
            if not id_token:
                return {"success": False, "message": "Missing ID token."}, 400
            decoded = verify_firebase_token(id_token)
            if not decoded:
                return {"success": False, "message": "Invalid ID token."}, 401
            session["user_id"] = decoded["uid"]  # Backward compat
            session["user_uid"] = decoded["uid"]
            session["user_email"] = decoded["email"]
            session["user_name"] = decoded.get("name", decoded["email"])
            return {"success": True, "message": "Login successful."}
        else:
            # Fallback for form-based login
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            print(f"[DEBUG] Login attempt - Email: {email}")
            if not email or not password:
                flash("Please enter email and password.", "error")
                return redirect(url_for("login"))
            try:
                user = auth.get_user_by_email(email)
                session["user_id"] = user.uid  # Backward compat
                session["user_uid"] = user.uid
                session["user_email"] = user.email
                session["user_name"] = user.display_name or user.email
                flash(f"Welcome back, {user.display_name or user.email}!", "success")
                print(f"[DEBUG] Login successful for: {email}")
                return redirect(url_for("dashboard"))
            except auth.UserNotFoundError:
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))
            except Exception as e:
                flash(f"Login error: {str(e)}", "error")
                return redirect(url_for("login"))
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
@login_required
def dashboard():
    intersections = load_intersections()
    total_intersections = len(intersections)
    total_cameras = 0
    active_cameras = 0
    maintenance_intersections = 0
    healthy_intersections = 0
    alerts = []
    priority_intersections = []

    for intersection in intersections:
        lanes = intersection.get("lanes", [])
        camera_total = len(lanes)
        camera_active = sum(1 for lane in lanes if lane.get("camera", {}).get("status"))
        camera_offline = camera_total - camera_active
        status = intersection.get("status", "active")

        total_cameras += camera_total
        active_cameras += camera_active

        if status == "maintenance":
            maintenance_intersections += 1

        if status == "active" and camera_total > 0 and camera_active == camera_total:
            healthy_intersections += 1

        if status == "maintenance":
            alerts.append({
                "tone": "error",
                "title": f"{intersection['name']} is under maintenance",
                "copy": f"{intersection['location']} needs review before normal monitoring resumes.",
                "intersection_id": intersection["id"],
            })
        elif camera_total == 0:
            alerts.append({
                "tone": "warning",
                "title": f"{intersection['name']} has no cameras configured",
                "copy": "Add lane cameras before using live monitoring.",
                "intersection_id": intersection["id"],
            })
        elif camera_active == 0:
            alerts.append({
                "tone": "error",
                "title": f"All cameras are off at {intersection['name']}",
                "copy": f"{camera_total} lane camera(s) are currently disabled.",
                "intersection_id": intersection["id"],
            })
        elif camera_offline > 0:
            alerts.append({
                "tone": "warning",
                "title": f"{intersection['name']} has reduced coverage",
                "copy": f"{camera_offline} of {camera_total} camera(s) are disabled.",
                "intersection_id": intersection["id"],
            })

        priority_intersections.append({
            "id": intersection["id"],
            "name": intersection["name"],
            "location": intersection.get("location", "Unknown location"),
            "status": status,
            "camera_total": camera_total,
            "camera_active": camera_active,
            "camera_offline": camera_offline,
            "priority_score": (
                300 if status == "maintenance" else 0
            ) + (
                200 if camera_total > 0 and camera_active == 0 else 0
            ) + (camera_offline * 10),
        })

    priority_intersections.sort(key=lambda item: (-item["priority_score"], item["name"]))
    alerts = alerts[:4]
    priority_intersections = priority_intersections[:4]

    stats = {
        "intersections": total_intersections,
        "active_signals": active_cameras,
        "sensors": total_cameras,
        "offline_cameras": total_cameras - active_cameras,
        "maintenance": maintenance_intersections,
        "healthy_intersections": healthy_intersections,
    }

    quick_actions = [
        {
            "title": "Manage intersections",
            "copy": "Open the full directory to edit lanes, cameras, and status.",
            "href": url_for("intersections"),
            "label": "Open intersections",
            "tone": "primary",
        },
        {
            "title": "Review profile",
            "copy": "Update account details and keep security settings in one place.",
            "href": url_for("profile"),
            "label": "Open profile",
            "tone": "secondary",
        },
        {
            "title": "Return home",
            "copy": "Jump back to the landing page and top-level navigation.",
            "href": url_for("index"),
            "label": "View homepage",
            "tone": "ghost",
        },
    ]

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name", "User"),
        stats=stats,
        alerts=alerts,
        priority_intersections=priority_intersections,
        quick_actions=quick_actions,
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    # Use Firebase session data or local
    user_email = session.get("user_email") or session.get("user_id")
    user_uid = session.get("user_uid") or session.get("user_id")
    user_name = session.get("user_name", "User")
    
    users = load_users()
    user = users.get(user_email)
    
    # Create local user record if Firebase-only
    if not user and user_email:
        user = {
            "email": user_email,
            "uid": user_uid,
            "name": user_name
        }
        users[user_email] = user
        save_users(users)
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_profile":
            new_name = request.form.get("name", "").strip()
            if not new_name:
                flash("Name cannot be empty.", "error")
            else:
                user["name"] = new_name
                users[user_email] = user
                save_users(users)
                session["user_name"] = new_name
                flash("Profile updated successfully!", "success")
        
        elif action == "change_password":
            flash("Password management handled by Firebase Auth. Use Firebase Console or email reset.", "info")
        
        return redirect(url_for("profile"))
    
    return render_template("profile.html", user=user)


@app.route("/intersections")
@login_required
def intersections():
    intersections = load_intersections()
    return render_template("intersections.html", intersections=intersections)


@app.route("/intersection/<intersection_id>")
@login_required
def intersection_detail(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    return render_template("intersection_detail.html", intersection=intersection)


@app.route("/intersection/<intersection_id>/monitor")
@login_required
def intersection_monitor(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    return render_template("intersection_monitor.html", intersection=intersection)


@app.route("/camera/toggle/<intersection_id>/<lane_id>", methods=["POST"])
@login_required
def camera_toggle(intersection_id, lane_id):
    success = toggle_camera(intersection_id, lane_id)

    lane = None
    intersection = get_intersection(intersection_id)
    if intersection:
        for item in intersection.get("lanes", []):
            if item.get("id") == lane_id:
                lane = item
                break

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]
    )

    if wants_json:
        if success and lane:
            return {
                "ok": True,
                "lane_id": lane_id,
                "camera_status": bool(lane.get("camera", {}).get("status")),
                "message": "Camera status updated successfully!",
            }
        return {"ok": False, "lane_id": lane_id, "message": "Camera not found."}, 404

    if success:
        flash("Camera status updated successfully!", "success")
    else:
        flash("Camera not found.", "error")

    return redirect(url_for("intersection_detail", intersection_id=intersection_id))


@app.route("/camera/set_all/<intersection_id>", methods=["POST"])
@login_required
def camera_set_all(intersection_id):
    enabled = request.get_json(silent=True, force=False) or {}
    target_state = bool(enabled.get("enabled"))

    success = set_all_cameras(intersection_id, target_state)
    intersection = get_intersection(intersection_id) if success else None
    active_count = 0
    total_count = 0
    if intersection:
        lanes = intersection.get("lanes", [])
        total_count = len(lanes)
        active_count = sum(1 for lane in lanes if lane.get("camera", {}).get("status"))

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]
    )

    if wants_json:
        if success:
            return {
                "ok": True,
                "enabled": target_state,
                "active_count": active_count,
                "total_count": total_count,
                "message": "All cameras updated successfully!",
            }
        return {"ok": False, "message": "Intersection not found."}, 404

    if success:
        flash("All cameras updated successfully!", "success")
    else:
        flash("Intersection not found.", "error")

    return redirect(url_for("intersection_monitor", intersection_id=intersection_id))


@app.route("/intersection/add", methods=["POST"])
@login_required
def intersection_add():
    
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    num_roads_str = request.form.get("num_roads", "4")
    
    try:
        num_roads = int(num_roads_str)
        if num_roads not in [3, 4, 5, 6]:
            flash("Number of roads must be 3, 4, 5, or 6.", "error")
            return redirect(url_for("intersections"))
    except ValueError:
        flash("Invalid number of roads.", "error")
        return redirect(url_for("intersections"))
    
    if not name or not location:
        flash("Please provide name, location, and number of roads.", "error")
        return redirect(url_for("intersections"))
    
    new_intersection = add_intersection(name, location, num_roads)
    flash(f"'{name}' ({num_roads}-road) intersection added!", "success")
    return redirect(url_for("intersection_detail", intersection_id=new_intersection["id"]))


@app.route("/intersection/update/<intersection_id>", methods=["POST"])
@login_required
def intersection_update(intersection_id):
    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    
    if not name or not location:
        flash("Name and location cannot be empty.", "error")
        return redirect(url_for("intersection_detail", intersection_id=intersection_id))
    
    intersections = load_intersections()
    for intersection in intersections:
        if intersection["id"] == intersection_id:
            intersection["name"] = name
            intersection["location"] = location
            save_intersections(intersections)
            flash("Intersection updated successfully!", "success")
            return redirect(url_for("intersection_detail", intersection_id=intersection_id))
    
    flash("Intersection not found.", "error")
    return redirect(url_for("intersections"))


@app.route("/intersection/delete/<intersection_id>", methods=["POST"])
@login_required
def intersection_delete(intersection_id):
    
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

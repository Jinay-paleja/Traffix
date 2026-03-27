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
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials

# Initialize Firebase Admin with service account
cred = credentials.Certificate("traffix-c507d-firebase-adminsdk.json.json")
firebase_admin.initialize_app(cred)

from firebase_admin import auth

# AI/ML Module imports
try:
    from traffic_detector import TrafficDetector, get_traffic_detector
    from signal_optimizer import get_signal_optimizer
    AI_ML_AVAILABLE = True
except ImportError as e:
    print(f"Warning: AI/ML modules not available: {e}")
    AI_ML_AVAILABLE = False

# Global variables for lazy loading
detector = None
optimizer = None

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
        print(f"[TOKEN_VERIFY] Verifying token: {id_token[:50]}...")
        decoded_token = auth.verify_id_token(id_token)
        print(f"[TOKEN_VERIFY] ✓ Token verified successfully")
        print(f"[TOKEN_VERIFY] Decoded token keys: {list(decoded_token.keys())}")
        print(f"[TOKEN_VERIFY] UID: {decoded_token.get('uid')}")
        print(f"[TOKEN_VERIFY] Email: {decoded_token.get('email')}")
        return decoded_token
    except Exception as e:
        print(f"[TOKEN_VERIFY] ❌ Token verification failed")
        print(f"[TOKEN_VERIFY] Error type: {type(e).__name__}")
        print(f"[TOKEN_VERIFY] Error message: {str(e)}")
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
            print(f"\n[LOGIN] Firebase sign-in attempt")
            print(f"[LOGIN] ID Token received: {id_token[:50] if id_token else 'NONE'}...")
            
            if not id_token:
                print(f"[LOGIN] ❌ No ID token provided")
                return {"success": False, "message": "Missing ID token."}, 400
            
            decoded = verify_firebase_token(id_token)
            print(f"[LOGIN] Token verification result: {decoded}")
            
            if not decoded:
                print(f"[LOGIN] ❌ Token verification failed")
                return {"success": False, "message": "Invalid ID token."}, 401
            
            print(f"[LOGIN] ✓ Token verified for user: {decoded.get('email')}")
            session["user_id"] = decoded["uid"]  # Backward compat
            session["user_uid"] = decoded["uid"]
            session["user_email"] = decoded["email"]
            session["user_name"] = decoded.get("name", decoded["email"])
            session.modified = True  # Force session to be saved
            print(f"[LOGIN] ✓ Session created for: {decoded['email']}")
            print(f"[LOGIN] Session data: uid={session.get('user_uid')}, email={session.get('user_email')}")
            return {"success": True, "message": "Login successful."}
        else:
            # Fallback for form-based login
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            print(f"[LOGIN] Form login attempt - Email: {email}")
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


@app.route("/camera/toggle/<intersection_id>/<lane_id>", methods=["POST"])
@login_required
def camera_toggle(intersection_id, lane_id):
    
    success = toggle_camera(intersection_id, lane_id)
    if success:
        flash("Camera status updated successfully!", "success")
    else:
        flash("Camera not found.", "error")
    
    return redirect(url_for("intersection_detail", intersection_id=intersection_id))


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


# ============= AI/ML TRAFFIC OPTIMIZATION ROUTES =============

@app.route("/traffic-detection")
@login_required
def traffic_detection():
    """Display traffic detection interface"""
    intersections = load_intersections()
    return render_template("traffic_detection.html", intersections=intersections)


@app.route("/api/analyze-traffic", methods=["POST"])
@login_required
def api_analyze_traffic():
    """
    API endpoint to analyze traffic from uploaded images (one per lane).
    Expects multipart/form-data with:
    - 'intersection_id': ID of the intersection
    - 'images[lane_id]': Multiple image files (one per lane)
    """
    if not AI_ML_AVAILABLE:
        return {"error": "AI/ML modules not available"}, 503
    
    try:
        global detector
        
        # Initialize detector on first use
        if detector is None:
            detector = get_traffic_detector()
            if detector is None:
                return {"error": "Could not initialize traffic detector"}, 500
        
        # Get intersection ID
        intersection_id = request.form.get('intersection_id')
        if not intersection_id:
            return {"error": "No intersection_id provided"}, 400
        
        # Get the intersection to access lane information
        intersection = get_intersection(intersection_id)
        if not intersection:
            return {"error": "Intersection not found"}, 404
        
        # Check if images were uploaded
        image_count = 0
        for key in request.files:
            if key.startswith('images['):
                image_count += 1
        
        if image_count == 0:
            return {"error": "No image files provided"}, 400
        
        # Process each image
        results = {}
        total_vehicles = 0
        highest_density = None
        highest_density_lane = None
        
        import tempfile
        import os
        
        # Create mapping of lane IDs to lane data
        lane_map = {lane['id']: lane for lane in intersection.get('lanes', [])}
        
        for key in request.files:
            if not key.startswith('images['):
                continue
            
            # Extract lane ID from form field name (images[lane-id])
            lane_id = key[7:-1]  # Remove 'images[' and ']'
            file = request.files[key]
            
            if file.filename == '':
                continue
            
            try:
                # Save file temporarily
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    file.save(tmp.name)
                    temp_path = tmp.name
                
                # Run detection
                detection_result = detector.detect_vehicles(temp_path)
                
                # Get lane info
                lane_info = lane_map.get(lane_id, {})
                lane_direction = lane_info.get('direction', lane_id)
                
                # Store result with lane info
                results[lane_id] = {
                    'direction': lane_direction,
                    'vehicle_count': detection_result.get('vehicle_count', 0),
                    'density_level': detection_result.get('density_level', 'Low'),
                    'timestamp': detection_result.get('timestamp'),
                    'detections': detection_result.get('detections', [])
                }
                
                # Track stats
                total_vehicles += detection_result.get('vehicle_count', 0)
                
                density_priority = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}
                current_density_score = density_priority.get(results[lane_id]['density_level'], 0)
                
                if highest_density is None or current_density_score > density_priority.get(highest_density, 0):
                    highest_density = results[lane_id]['density_level']
                    highest_density_lane = lane_direction
                
                # Clean up temp file
                os.remove(temp_path)
                
            except Exception as e:
                results[lane_id] = {
                    'direction': lane_map.get(lane_id, {}).get('direction', lane_id),
                    'error': str(e)
                }
        
        if not results:
            return {"error": "No images could be processed"}, 400
        
        return {
            'results': results,
            'summary': {
                'intersection_id': intersection_id,
                'intersection_name': intersection.get('name'),
                'total_vehicles': total_vehicles,
                'highest_congestion_lane': highest_density_lane or 'N/A',
                'highest_congestion_density': highest_density or 'N/A',
                'timestamp': datetime.now().isoformat()
            }
        }, 200
    
    except Exception as e:
        return {"error": f"Server error: {str(e)}"}, 500


@app.route("/api/optimize-signals", methods=["POST"])
@login_required
def api_optimize_signals():
    """
    API endpoint to optimize signal timing based on traffic data.
    Expects JSON with intersection_data:
    {
        "intersection_id": "int-001",
        "traffic_data": {
            "North": {"vehicles": 10, "priority": 2},
            "South": {"vehicles": 5, "priority": 1},
            ...
        }
    }
    """
    if not AI_ML_AVAILABLE:
        return {"error": "AI/ML modules not available"}, 503
    
    try:
        global optimizer
        
        data = request.get_json()
        if not data:
            return {"error": "No JSON data provided"}, 400
        
        traffic_data = data.get('traffic_data', {})
        if not traffic_data:
            return {"error": "No traffic_data provided"}, 400
        
        # Initialize optimizer on first use
        if optimizer is None:
            optimizer = get_signal_optimizer()
        
        # Optimize signal timing
        optimization = optimizer.optimize_signal(traffic_data)
        
        # Get detailed schedule and recommendations
        schedule = optimizer.get_signal_schedule(traffic_data)
        recommendations = optimizer.get_recommendations(traffic_data)
        
        return {
            "optimization": optimization,
            "schedule": schedule,
            "recommendations": recommendations
        }, 200
    
    except Exception as e:
        return {"error": f"Server error: {str(e)}"}, 500


@app.route("/signal-optimization/<intersection_id>")
@login_required
def signal_optimization(intersection_id):
    """Display signal optimization dashboard for intersection"""
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    
    return render_template("signal_optimization.html", intersection=intersection)


# ============= END AI/ML TRAFFIC OPTIMIZATION ROUTES =============



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

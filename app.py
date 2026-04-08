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
import base64
import json
import math
import random
import uuid
from pathlib import Path
from datetime import datetime, timedelta

import cv2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials
from signal_optimizer import get_signal_optimizer
from traffic_detector import get_traffic_detector

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
TRAFFIC_HISTORY_FILE = BASE_DIR / "data" / "traffic_history.json"
INTERSECTION_MEDIA_FILE = BASE_DIR / "data" / "intersection_media.json"
LANE_VIDEO_UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "lane_videos"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
LIVE_ANALYSIS_STATE = {}
LIVE_HISTORY_INTERVAL_SECONDS = 60


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


def load_traffic_history():
    if not TRAFFIC_HISTORY_FILE.exists():
        return []
    try:
        with open(TRAFFIC_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return []
            payload = json.loads(data)
            history = payload.get("history", [])
            if not isinstance(history, list):
                return []
            changed = False
            for item in history:
                if isinstance(item, dict) and not item.get("id"):
                    item["id"] = uuid.uuid4().hex
                    changed = True
            if changed:
                save_traffic_history(history)
            return history
    except (json.JSONDecodeError, OSError):
        return []


def save_traffic_history(history):
    TRAFFIC_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAFFIC_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"history": history[-500:]}, f, indent=2)


def load_intersection_media():
    if not INTERSECTION_MEDIA_FILE.exists():
        return {}
    try:
        with open(INTERSECTION_MEDIA_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                return {}
            payload = json.loads(data)
            media = payload.get("media", {})
            return media if isinstance(media, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_intersection_media(media):
    INTERSECTION_MEDIA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INTERSECTION_MEDIA_FILE, "w", encoding="utf-8") as f:
        json.dump({"media": media}, f, indent=2)


def _peak_multiplier(hour):
    if 7 <= hour <= 10:
        return 1.8
    if 17 <= hour <= 20:
        return 2.1
    if 12 <= hour <= 14:
        return 1.35
    if 22 <= hour or hour <= 5:
        return 0.55
    return 1.0


def _direction_weight(direction):
    direction = (direction or "").lower()
    mapping = {
        "north": 1.18,
        "south": 1.0,
        "east": 1.28,
        "west": 0.92,
        "northeast": 1.12,
        "northwest": 0.95,
        "southeast": 1.22,
        "southwest": 0.88,
    }
    return mapping.get(direction, 1.0)


def _density_level_from_count(vehicle_count):
    if vehicle_count < 5:
        return "Low"
    if vehicle_count < 15:
        return "Medium"
    if vehicle_count < 30:
        return "High"
    return "Critical"


def _generate_modeled_history(intersection, days=7):
    lanes = intersection.get("lanes", [])
    now = datetime.now()
    history = []

    for day_offset in range(days - 1, -1, -1):
        day = (now - timedelta(days=day_offset)).replace(minute=0, second=0, microsecond=0)
        for hour in [6, 9, 12, 15, 18, 21]:
            sample_time = day.replace(hour=hour)
            lane_results = {}
            total = 0
            for idx, lane in enumerate(lanes):
                direction = lane.get("direction", f"lane-{idx+1}")
                base = 6 + (idx * 2)
                weekday_boost = 1.18 if sample_time.weekday() < 5 else 0.88
                wave = 1 + (math.sin(((sample_time.timetuple().tm_yday + idx) / 8.0)) * 0.14)
                seeded_noise = random.Random(f"{intersection.get('id')}:{direction}:{sample_time.isoformat()}").uniform(0.86, 1.16)
                vehicles = int(round(base * _direction_weight(direction) * _peak_multiplier(hour) * weekday_boost * wave * seeded_noise))
                vehicles = max(0, vehicles)
                lane_results[lane.get("id", direction)] = {
                    "lane_id": lane.get("id", direction),
                    "lane_name": lane.get("name", direction.title()),
                    "direction": direction.title(),
                    "vehicle_count": vehicles,
                    "density_level": _density_level_from_count(vehicles),
                    "timestamp": sample_time.isoformat(),
                    "detections": [],
                }
                total += vehicles

            history.append({
                "intersection_id": intersection.get("id"),
                "timestamp": sample_time.isoformat(),
                "source": "modeled",
                "results": lane_results,
                "summary": {
                    "total_vehicles": total,
                    "lanes_analyzed": len(lane_results),
                },
            })

    return history


def _normalize_analysis_timestamp(raw_value):
    if not raw_value:
        return datetime.now().replace(microsecond=0).isoformat()
    try:
        return datetime.fromisoformat(raw_value).replace(microsecond=0).isoformat()
    except ValueError:
        return datetime.now().replace(microsecond=0).isoformat()


def _normalize_event_duration(raw_value):
    try:
        duration = int(raw_value)
    except (TypeError, ValueError):
        duration = 15
    return max(1, min(duration, 240))


def _decode_base64_image(data_url):
    if not isinstance(data_url, str) or "," not in data_url:
        return None, "Live frame was missing or malformed."

    _, encoded = data_url.split(",", 1)
    try:
        raw_bytes = base64.b64decode(encoded)
    except (ValueError, TypeError):
        return None, "Live frame could not be decoded."

    np_buffer = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if image is None:
        return None, "Live frame could not be parsed as an image."
    return image, None


def _get_live_state(intersection_id):
    state = LIVE_ANALYSIS_STATE.get(intersection_id)
    if isinstance(state, dict):
        return state

    state = {
        "lanes": {},
        "last_persisted_at": None,
    }
    LIVE_ANALYSIS_STATE[intersection_id] = state
    return state


def _smooth_live_vehicle_count(intersection_id, lane_id, detected_count, alpha=0.45):
    state = _get_live_state(intersection_id)
    lanes = state["lanes"]
    lane_state = lanes.get(lane_id, {})
    previous = float(lane_state.get("smoothed_count", detected_count))
    smoothed = detected_count if not lane_state else ((alpha * detected_count) + ((1 - alpha) * previous))
    lane_state["smoothed_count"] = smoothed
    lane_state["last_seen_at"] = datetime.now().isoformat()
    lanes[lane_id] = lane_state
    return max(0, int(round(smoothed)))


def _should_persist_live_history(intersection_id):
    state = _get_live_state(intersection_id)
    now = datetime.now()
    last_persisted_at = _parse_iso_datetime(state.get("last_persisted_at"))
    if last_persisted_at and (now - last_persisted_at).total_seconds() < LIVE_HISTORY_INTERVAL_SECONDS:
        return False

    state["last_persisted_at"] = now.replace(microsecond=0).isoformat()
    return True


def _parse_iso_datetime(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except (TypeError, ValueError):
        return None


def _format_relative_timestamp(timestamp):
    if not timestamp:
        return "No analysis yet"

    delta = datetime.now() - timestamp
    seconds = max(0, int(delta.total_seconds()))
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24

    if minutes < 1:
        return "Just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if hours < 24:
        return f"{hours} hr ago" if hours == 1 else f"{hours} hrs ago"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def _build_latest_history_index(history_items):
    latest = {}

    for item in history_items or []:
        intersection_id = item.get("intersection_id")
        timestamp = _parse_iso_datetime(item.get("timestamp"))
        if not intersection_id or not timestamp:
            continue

        existing = latest.get(intersection_id)
        if not existing or timestamp > existing["timestamp"]:
            latest[intersection_id] = {
                "timestamp": timestamp,
                "record": item,
            }

    return latest


def _build_analysis_snapshot(intersection, latest_entry=None):
    if not latest_entry:
        return {
            "has_analysis": False,
            "freshness_tone": "none",
            "freshness_label": "No analysis",
            "last_analysis_relative": "No analysis yet",
            "last_analysis_display": "-",
            "analysis_mode": None,
            "analysis_mode_label": "Awaiting data",
            "total_vehicles": 0,
            "lanes_analyzed": 0,
            "highest_lane": "-",
            "highest_density": "-",
            "age_hours": None,
        }

    record = latest_entry["record"]
    timestamp = latest_entry["timestamp"]
    summary = record.get("summary") or {}
    age_hours = max(0.0, (datetime.now() - timestamp).total_seconds() / 3600)

    if age_hours <= 6:
        freshness_tone = "good"
        freshness_label = "Fresh"
    elif age_hours <= 24:
        freshness_tone = "warn"
        freshness_label = "Aging"
    else:
        freshness_tone = "bad"
        freshness_label = "Stale"

    analysis_mode = record.get("analysis_mode") or "photo"
    analysis_mode_label = "Video simulation" if analysis_mode == "video" else "Photo analysis"

    return {
        "has_analysis": True,
        "freshness_tone": freshness_tone,
        "freshness_label": freshness_label,
        "last_analysis_relative": _format_relative_timestamp(timestamp),
        "last_analysis_display": timestamp.strftime("%d %b %Y, %I:%M %p"),
        "analysis_mode": analysis_mode,
        "analysis_mode_label": analysis_mode_label,
        "total_vehicles": summary.get("total_vehicles", 0),
        "lanes_analyzed": summary.get("lanes_analyzed", 0),
        "highest_lane": summary.get("highest_congestion_lane") or "-",
        "highest_density": summary.get("highest_congestion_density") or "-",
        "age_hours": age_hours,
    }


def _allowed_video_file(filename):
    return Path(filename or "").suffix.lower() in ALLOWED_VIDEO_EXTENSIONS


def _save_lane_video(intersection_id, lane_id, file_storage):
    filename = secure_filename(file_storage.filename or "")
    if not filename or not _allowed_video_file(filename):
        return None, "Please upload a supported video file (MP4, MOV, AVI, MKV, or WEBM)."

    suffix = Path(filename).suffix.lower()
    saved_name = f"{intersection_id}-{lane_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
    target_dir = LANE_VIDEO_UPLOAD_DIR / intersection_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / saved_name
    file_storage.save(target_path)
    relative_url = f"uploads/lane_videos/{intersection_id}/{saved_name}"
    return {
        "path": str(target_path),
        "static_url": url_for("static", filename=relative_url),
        "filename": saved_name,
    }, None


def _build_lane_media_map(intersection):
    media_payload = load_intersection_media().get(intersection.get("id"), {})
    lane_media = {}
    for lane in intersection.get("lanes", []):
        lane_media[lane.get("id")] = media_payload.get(lane.get("id"), {})
    return lane_media


def _save_lane_media(intersection, lane_payloads):
    media = load_intersection_media()
    intersection_id = intersection.get("id")
    existing = media.get(intersection_id, {})
    existing.update(lane_payloads)
    media[intersection_id] = existing
    save_intersection_media(media)
    return media[intersection_id]


def _delete_lane_video(intersection, lane_id):
    media = load_intersection_media()
    intersection_id = intersection.get("id")
    lane_media = media.get(intersection_id, {})
    existing = lane_media.get(lane_id)
    if not existing:
        return False

    video_url = existing.get("video_url", "")
    static_prefix = "/static/"
    if isinstance(video_url, str) and static_prefix in video_url:
        relative = video_url.split(static_prefix, 1)[1].replace("/", os.sep)
        target_path = BASE_DIR / "static" / relative
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

    lane_media.pop(lane_id, None)
    media[intersection_id] = lane_media
    save_intersection_media(media)
    return True


def _delete_photo_analysis_history(intersection_id):
    history = load_traffic_history()
    filtered = [
        item for item in history
        if not (
            item.get("intersection_id") == intersection_id
            and item.get("analysis_mode", "photo") == "photo"
        )
    ]
    if len(filtered) == len(history):
        return False
    save_traffic_history(filtered)
    return True


def _update_analysis_record(intersection_id, analysis_id, analysis_timestamp=None, event_duration_minutes=None):
    history = load_traffic_history()
    updated = None
    for item in history:
        if item.get("intersection_id") == intersection_id and item.get("id") == analysis_id:
            if analysis_timestamp:
                item["timestamp"] = analysis_timestamp
            if event_duration_minutes is not None:
                item["event_duration_minutes"] = event_duration_minutes
            updated = item
            break
    if not updated:
        return None
    save_traffic_history(history)
    return updated


def _delete_analysis_record(intersection_id, analysis_id):
    history = load_traffic_history()
    filtered = [
        item for item in history
        if not (item.get("intersection_id") == intersection_id and item.get("id") == analysis_id)
    ]
    if len(filtered) == len(history):
        return False
    save_traffic_history(filtered)
    return True


def _append_traffic_history(intersection, payload):
    history = load_traffic_history()
    history.append({
        "id": uuid.uuid4().hex,
        "intersection_id": intersection.get("id"),
        "timestamp": payload.get("analysis_timestamp") or payload.get("decision", {}).get("timestamp") or datetime.now().isoformat(),
        "source": "live",
        "analysis_mode": payload.get("analysis_mode", "photo"),
        "event_duration_minutes": payload.get("event_duration_minutes"),
        "results": payload.get("results", {}),
        "summary": payload.get("summary", {}),
        "decision": payload.get("decision", {}),
    })
    save_traffic_history(history)


def _build_signal_wall_snapshot(intersection):
    intersection_id = intersection.get("id")
    lane_media = _build_lane_media_map(intersection)
    optimizer = get_signal_optimizer()
    parsed_history = []

    for item in load_traffic_history():
        if item.get("intersection_id") != intersection_id:
            continue
        try:
            timestamp = datetime.fromisoformat(item.get("timestamp"))
        except (TypeError, ValueError):
            timestamp = datetime.min
        parsed_history.append((timestamp, item))

    parsed_history.sort(key=lambda entry: entry[0])
    latest_item = parsed_history[-1][1] if parsed_history else None

    if not latest_item:
        return {
            "intersection": {
                "id": intersection["id"],
                "name": intersection["name"],
                "location": intersection.get("location", "Unknown location"),
            },
            "decision": {},
            "optimization": {"cycle_time": 0, "green_times": {}},
            "results": {},
            "lane_media": lane_media,
            "analysis_mode": None,
            "timestamp": None,
            "event_duration_minutes": None,
            "has_live_signal": False,
        }

    results = latest_item.get("results") or {}
    traffic_data = {}
    for lane in intersection.get("lanes", []):
        lane_id = lane.get("id")
        result = results.get(lane_id) if isinstance(results, dict) else None
        if not isinstance(result, dict):
            continue
        direction = (result.get("direction") or lane.get("direction") or lane_id).title()
        vehicles = max(0, int(result.get("vehicle_count", 0)))
        traffic_data[direction] = {
            "vehicles": vehicles,
            "priority": optimizer._get_priority(vehicles),
        }

    optimization = optimizer.adaptive_timing(
        {direction: item["vehicles"] for direction, item in traffic_data.items()}
    ) if traffic_data else {"cycle_time": 0, "green_times": {}}

    return {
        "intersection": {
            "id": intersection["id"],
            "name": intersection["name"],
            "location": intersection.get("location", "Unknown location"),
        },
        "decision": latest_item.get("decision", {}),
        "optimization": optimization,
        "results": results,
        "lane_media": lane_media,
        "analysis_mode": latest_item.get("analysis_mode"),
        "timestamp": latest_item.get("timestamp"),
        "event_duration_minutes": latest_item.get("event_duration_minutes"),
        "has_live_signal": bool(results),
    }


def _build_history_analytics(intersection, days=7):
    intersection_id = intersection.get("id")
    cutoff = datetime.now() - timedelta(days=days)
    history = [
        item for item in load_traffic_history()
        if item.get("intersection_id") == intersection_id
    ]

    parsed_history = []
    for item in history:
        try:
            timestamp = datetime.fromisoformat(item.get("timestamp"))
        except (TypeError, ValueError):
            continue
        if timestamp >= cutoff:
            parsed_history.append((timestamp, item))

    if not parsed_history:
        return {
            "source": "No history yet",
            "days": days,
            "sample_count": 0,
            "overall_average": 0,
            "best_hour": {"label": "-", "value": 0},
            "busiest_lane": {"lane_name": "-", "direction": "-", "average_vehicles": 0},
            "peak_record": {"vehicles": 0, "label": "-", "direction": "-", "timestamp": "-"},
            "hourly_trend": [],
            "daily_totals": [],
            "lane_averages": [],
            "timeline": [],
            "recent_records": [],
            "insights": [
                "No history yet. Upload lane images and run an analysis to start building real traffic trends for this intersection."
            ],
        }

    source = "live uploads"

    parsed_history.sort(key=lambda item: item[0])

    lane_map = {
        lane.get("id"): {
            "direction": lane.get("direction", lane.get("id", "")).title(),
            "name": lane.get("name", lane.get("direction", "Lane").title()),
        }
        for lane in intersection.get("lanes", [])
    }
    lane_totals = {lane_id: 0 for lane_id in lane_map}
    lane_samples = {lane_id: 0 for lane_id in lane_map}
    hour_buckets = {}
    day_buckets = {}
    timeline = []

    peak_record = {"vehicles": -1, "label": "-", "direction": "-", "timestamp": "-"}

    for timestamp, item in parsed_history:
        results = item.get("results", {}) or {}
        total = 0
        busiest_lane = None
        busiest_count = -1
        for lane_id, result in results.items():
            vehicles = int(result.get("vehicle_count", 0))
            lane_totals.setdefault(lane_id, 0)
            lane_samples.setdefault(lane_id, 0)
            lane_totals[lane_id] += vehicles
            lane_samples[lane_id] += 1
            total += vehicles
            if vehicles > busiest_count:
                busiest_count = vehicles
                busiest_lane = result
            if vehicles > peak_record["vehicles"]:
                peak_record = {
                    "vehicles": vehicles,
                    "label": result.get("lane_name", lane_id),
                    "direction": result.get("direction", lane_id),
                    "timestamp": timestamp.strftime("%d %b %Y, %I:%M %p"),
                }

        hour_key = timestamp.strftime("%H:00")
        hour_stats = hour_buckets.setdefault(hour_key, {"total": 0, "count": 0})
        hour_stats["total"] += total
        hour_stats["count"] += 1

        day_key = timestamp.strftime("%d %b")
        day_stats = day_buckets.setdefault(day_key, {"total": 0, "count": 0})
        day_stats["total"] += total
        day_stats["count"] += 1

        timeline.append({
            "label": timestamp.strftime("%d %b %H:%M"),
            "total": total,
            "busiest_lane": (busiest_lane or {}).get("direction", "-"),
        })

    lane_averages = []
    for lane_id, total in lane_totals.items():
        sample_count = max(lane_samples.get(lane_id, 0), 1)
        lane_info = lane_map.get(lane_id, {"direction": lane_id.title(), "name": lane_id})
        lane_averages.append({
            "lane_id": lane_id,
            "lane_name": lane_info["name"],
            "direction": lane_info["direction"],
            "average_vehicles": round(total / sample_count, 1),
        })
    lane_averages.sort(key=lambda item: item["average_vehicles"], reverse=True)

    hourly_trend = [
        {"label": hour, "value": round(stats["total"] / max(stats["count"], 1), 1)}
        for hour, stats in sorted(hour_buckets.items())
    ]
    daily_totals = [
        {"label": day, "value": round(stats["total"] / max(stats["count"], 1), 1)}
        for day, stats in day_buckets.items()
    ]

    overall_average = round(
        sum(item["total"] for item in timeline) / max(len(timeline), 1),
        1
    ) if timeline else 0
    best_hour = max(hourly_trend, key=lambda item: item["value"], default={"label": "-", "value": 0})
    busiest_lane = lane_averages[0] if lane_averages else {"lane_name": "-", "direction": "-", "average_vehicles": 0}

    return {
        "source": source,
        "days": days,
        "sample_count": len(timeline),
        "overall_average": overall_average,
        "best_hour": best_hour,
        "busiest_lane": busiest_lane,
        "peak_record": peak_record,
        "hourly_trend": hourly_trend,
        "daily_totals": daily_totals,
        "lane_averages": lane_averages,
        "timeline": timeline[-18:],
        "recent_records": [
            {
                "id": item.get("id"),
                "timestamp": timestamp.isoformat(),
                "display_timestamp": timestamp.strftime("%d %b %Y, %I:%M %p"),
                "analysis_mode": item.get("analysis_mode", "photo"),
                "event_duration_minutes": item.get("event_duration_minutes", 15),
                "total_vehicles": int((item.get("summary") or {}).get("total_vehicles", 0)),
                "lanes_analyzed": int((item.get("summary") or {}).get("lanes_analyzed", 0)),
            }
            for timestamp, item in parsed_history[-12:]
        ][::-1],
        "insights": [
            f"Peak traffic pressure usually appears around {best_hour['label']} based on the current {source}.",
            f"{busiest_lane['lane_name']} is the heaviest approach on average at {busiest_lane['average_vehicles']} vehicles per sample.",
            f"The intersection-wide average is {overall_average} vehicles across the tracked sampling windows.",
        ]
    }


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


def _allowed_image_file(filename):
    return Path(filename or "").suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def _decode_uploaded_image(file_storage):
    filename = secure_filename(file_storage.filename or "")
    if not filename or not _allowed_image_file(filename):
        return None, "Please upload a JPG, PNG, or WebP image."

    raw_bytes = file_storage.read()
    if not raw_bytes:
        return None, "Uploaded image was empty."

    np_buffer = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if image is None:
        return None, "Could not read the uploaded image."
    return image, None


def _build_lane_analysis(intersection, uploaded_files):
    detector = get_traffic_detector()
    if detector is None:
        return None, "YOLO model is not available. Install the dependencies and keep yolov8n.pt in the project root."
    optimizer = get_signal_optimizer()

    lane_lookup = {lane["id"]: lane for lane in intersection.get("lanes", [])}
    traffic_data = {}
    lane_results = {}
    total_vehicles = 0

    for lane_id, file_storage in uploaded_files.items():
        lane = lane_lookup.get(lane_id)
        if not lane:
            continue

        image, error = _decode_uploaded_image(file_storage)
        if error:
            return None, f"{lane.get('name', lane_id)}: {error}"

        result = detector.detect_vehicles(image)
        if "error" in result:
            return None, f"{lane.get('name', lane_id)}: {result['error']}"

        direction = lane.get("direction", lane_id).title()
        vehicles = int(result.get("vehicle_count", 0))
        priority = optimizer._get_priority(vehicles)

        lane_results[lane_id] = {
            "lane_id": lane_id,
            "lane_name": lane.get("name", direction),
            "direction": direction,
            "vehicle_count": vehicles,
            "density_level": result.get("density_level", "Low"),
            "timestamp": result.get("timestamp"),
            "detections": result.get("detections", []),
        }
        traffic_data[direction] = {"vehicles": vehicles, "priority": priority}
        total_vehicles += vehicles

    if not lane_results:
        return None, "Upload at least one lane image to run analysis."

    optimization = optimizer.adaptive_timing(
        {direction: data["vehicles"] for direction, data in traffic_data.items()}
    )
    schedule = optimizer.get_signal_schedule(traffic_data)
    congestion_score = min(100, int((total_vehicles / max(len(traffic_data), 1)) * 4))
    recommendations = optimizer.get_recommendations(traffic_data, congestion_score)
    decision = optimizer.build_phase_decision(traffic_data)

    ranked_lanes = sorted(
        lane_results.values(),
        key=lambda item: (item["vehicle_count"], item["density_level"]),
        reverse=True,
    )

    summary = {
        "total_vehicles": total_vehicles,
        "lanes_analyzed": len(lane_results),
        "highest_congestion_lane": ranked_lanes[0]["lane_name"],
        "highest_congestion_density": ranked_lanes[0]["density_level"],
    }

    return {
        "intersection": {
            "id": intersection["id"],
            "name": intersection["name"],
            "location": intersection.get("location", "Unknown location"),
        },
        "results": lane_results,
        "traffic_data": traffic_data,
        "summary": summary,
        "optimization": optimization,
        "schedule": schedule,
        "recommendations": recommendations,
        "decision": decision,
    }, None


def _build_live_lane_analysis(intersection, live_frames, analysis_timestamp=None, event_duration_minutes=1):
    detector = get_traffic_detector()
    if detector is None:
        return None, "YOLO model is not available. Install the dependencies and keep yolov8n.pt in the project root."

    optimizer = get_signal_optimizer()
    lane_lookup = {lane["id"]: lane for lane in intersection.get("lanes", [])}
    traffic_data = {}
    lane_results = {}
    total_vehicles = 0

    for lane_id, encoded_frame in (live_frames or {}).items():
        lane = lane_lookup.get(lane_id)
        if not lane:
            continue

        image, error = _decode_base64_image(encoded_frame)
        if error:
            return None, f"{lane.get('name', lane_id)}: {error}"

        result = detector.detect_vehicles(image, image_size=640, max_dimension=960)
        if "error" in result:
            return None, f"{lane.get('name', lane_id)}: {result['error']}"

        direction = lane.get("direction", lane_id).title()
        raw_vehicles = int(result.get("vehicle_count", 0))
        vehicles = _smooth_live_vehicle_count(intersection.get("id"), lane_id, raw_vehicles)
        priority = optimizer._get_priority(vehicles)

        lane_results[lane_id] = {
            "lane_id": lane_id,
            "lane_name": lane.get("name", direction),
            "direction": direction,
            "vehicle_count": vehicles,
            "raw_vehicle_count": raw_vehicles,
            "density_level": _density_level_from_count(vehicles),
            "timestamp": analysis_timestamp or result.get("timestamp"),
            "detections": result.get("detections", []),
        }
        traffic_data[direction] = {"vehicles": vehicles, "priority": priority}
        total_vehicles += vehicles

    if not lane_results:
        return None, "No usable live camera frames were received."

    optimization = optimizer.adaptive_timing(
        {direction: data["vehicles"] for direction, data in traffic_data.items()}
    )
    schedule = optimizer.get_signal_schedule(traffic_data)
    congestion_score = min(100, int((total_vehicles / max(len(traffic_data), 1)) * 4))
    recommendations = optimizer.get_recommendations(traffic_data, congestion_score)
    decision = optimizer.build_phase_decision(traffic_data)

    ranked_lanes = sorted(
        lane_results.values(),
        key=lambda item: (item["vehicle_count"], item["raw_vehicle_count"]),
        reverse=True,
    )

    return {
        "intersection": {
            "id": intersection["id"],
            "name": intersection["name"],
            "location": intersection.get("location", "Unknown location"),
        },
        "analysis_mode": "live",
        "analysis_timestamp": analysis_timestamp or datetime.now().replace(microsecond=0).isoformat(),
        "event_duration_minutes": event_duration_minutes,
        "results": lane_results,
        "traffic_data": traffic_data,
        "summary": {
            "total_vehicles": total_vehicles,
            "lanes_analyzed": len(lane_results),
            "highest_congestion_lane": ranked_lanes[0]["lane_name"],
            "highest_congestion_density": ranked_lanes[0]["density_level"],
        },
        "optimization": optimization,
        "schedule": schedule,
        "recommendations": recommendations,
        "decision": decision,
        "live_meta": {
            "smoothed_counts": True,
            "persist_interval_seconds": LIVE_HISTORY_INTERVAL_SECONDS,
        },
    }, None


def _build_lane_video_analysis(intersection, uploaded_videos, analysis_timestamp=None, event_duration_minutes=15):
    detector = get_traffic_detector()
    if detector is None:
        return None, "YOLO model is not available. Install the dependencies and keep yolov8n.pt in the project root."

    optimizer = get_signal_optimizer()
    lane_lookup = {lane["id"]: lane for lane in intersection.get("lanes", [])}
    lane_results = {}
    traffic_data = {}
    saved_media = {}
    total_vehicles = 0

    for lane_id, file_storage in uploaded_videos.items():
        lane = lane_lookup.get(lane_id)
        if not lane:
            continue

        saved_video, error = _save_lane_video(intersection["id"], lane_id, file_storage)
        if error:
            return None, f"{lane.get('name', lane_id)}: {error}"

        result = detector.detect_vehicles_in_video(
            saved_video["path"],
            max_frames=120,
            frame_stride=2,
            image_size=768,
            max_dimension=1280,
        )
        if "error" in result:
            return None, f"{lane.get('name', lane_id)}: {result['error']}"

        direction = lane.get("direction", lane_id).title()
        vehicles = int(result.get("representative_vehicle_count", round(result.get("avg_vehicles_per_frame", 0))))
        priority = optimizer._get_priority(vehicles)

        lane_results[lane_id] = {
            "lane_id": lane_id,
            "lane_name": lane.get("name", direction),
            "direction": direction,
            "vehicle_count": vehicles,
            "avg_vehicles_per_frame": result.get("avg_vehicles_per_frame", 0),
            "p75_vehicles_per_frame": result.get("p75_vehicles_per_frame", 0),
            "peak_weighted_vehicle_count": result.get("peak_weighted_vehicle_count", vehicles),
            "density_level": result.get("density_level", _density_level_from_count(vehicles)),
            "frames_processed": result.get("frames_processed", 0),
            "max_vehicles_in_frame": result.get("max_vehicles_in_frame", 0),
            "video_url": saved_video["static_url"],
            "timestamp": analysis_timestamp or result.get("timestamp"),
        }
        traffic_data[direction] = {"vehicles": vehicles, "priority": priority}
        saved_media[lane_id] = {
            "video_url": saved_video["static_url"],
            "uploaded_at": datetime.now().replace(microsecond=0).isoformat(),
            "analysis_timestamp": analysis_timestamp,
            "event_duration_minutes": event_duration_minutes,
            "lane_name": lane.get("name", direction),
            "direction": direction,
        }
        total_vehicles += vehicles

    if not lane_results:
        return None, "Upload at least one lane video to run the simulation."

    for lane in intersection.get("lanes", []):
        lane_id = lane.get("id")
        if not lane_id or lane_id in lane_results:
            continue

        direction = lane.get("direction", lane_id).title()
        lane_results[lane_id] = {
            "lane_id": lane_id,
            "lane_name": lane.get("name", direction),
            "direction": direction,
            "vehicle_count": 0,
            "avg_vehicles_per_frame": 0,
            "p75_vehicles_per_frame": 0,
            "peak_weighted_vehicle_count": 0,
            "density_level": _density_level_from_count(0),
            "frames_processed": 0,
            "max_vehicles_in_frame": 0,
            "video_url": "",
            "timestamp": analysis_timestamp,
            "analysis_status": "not_uploaded",
        }
        traffic_data[direction] = {"vehicles": 0, "priority": optimizer._get_priority(0)}

    persisted_media = _save_lane_media(intersection, saved_media)
    optimization = optimizer.adaptive_timing({direction: data["vehicles"] for direction, data in traffic_data.items()})
    schedule = optimizer.get_signal_schedule(traffic_data)
    congestion_score = min(100, int((total_vehicles / max(len(traffic_data), 1)) * 4))
    recommendations = optimizer.get_recommendations(traffic_data, congestion_score)
    decision = optimizer.build_phase_decision(traffic_data)

    return {
        "intersection": {
            "id": intersection["id"],
            "name": intersection["name"],
            "location": intersection.get("location", "Unknown location"),
        },
        "analysis_mode": "video",
        "analysis_timestamp": analysis_timestamp,
        "event_duration_minutes": event_duration_minutes,
        "results": lane_results,
        "traffic_data": traffic_data,
        "summary": {
            "total_vehicles": total_vehicles,
            "lanes_analyzed": len(lane_results),
            "highest_congestion_lane": max(lane_results.values(), key=lambda item: item["vehicle_count"])["lane_name"],
            "highest_congestion_density": max(lane_results.values(), key=lambda item: item["vehicle_count"])["density_level"],
        },
        "optimization": optimization,
        "schedule": schedule,
        "recommendations": recommendations,
        "decision": decision,
        "lane_media": persisted_media,
    }, None


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
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
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
    latest_history = _build_latest_history_index(load_traffic_history())
    total_intersections = len(intersections)
    total_cameras = 0
    active_cameras = 0
    maintenance_intersections = 0
    healthy_intersections = 0
    fresh_analyses = 0
    stale_analyses = 0
    alerts = []
    priority_intersections = []

    for intersection in intersections:
        lanes = intersection.get("lanes", [])
        analysis_snapshot = _build_analysis_snapshot(intersection, latest_history.get(intersection["id"]))
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

        if analysis_snapshot["has_analysis"]:
            if analysis_snapshot["age_hours"] is not None and analysis_snapshot["age_hours"] <= 24:
                fresh_analyses += 1
            elif analysis_snapshot["age_hours"] is not None:
                stale_analyses += 1

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
            "analysis_snapshot": analysis_snapshot,
            "priority_score": (
                300 if status == "maintenance" else 0
            ) + (
                200 if camera_total > 0 and camera_active == 0 else 0
            ) + (camera_offline * 10) + (
                20 if analysis_snapshot["freshness_tone"] == "bad" else 8 if analysis_snapshot["freshness_tone"] == "warn" else 0
            ),
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
        "fresh_analyses": fresh_analyses,
        "stale_analyses": stale_analyses,
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
    latest_history = _build_latest_history_index(load_traffic_history())
    enriched_intersections = []

    for intersection in intersections:
        enriched = dict(intersection)
        enriched["analysis_snapshot"] = _build_analysis_snapshot(intersection, latest_history.get(intersection["id"]))
        enriched_intersections.append(enriched)
    return render_template("intersections.html", intersections=enriched_intersections)


@app.route("/intersection/<intersection_id>")
@login_required
def intersection_detail(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    intersection = dict(intersection)
    latest_history = _build_latest_history_index(load_traffic_history())
    intersection["analysis_snapshot"] = _build_analysis_snapshot(intersection, latest_history.get(intersection_id))
    return render_template("intersection_detail.html", intersection=intersection)


@app.route("/intersection/<intersection_id>/monitor")
@login_required
def intersection_monitor(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    return render_template("intersection_monitor.html", intersection=intersection)


@app.route("/intersection/<intersection_id>/smart-signal")
@login_required
def smart_signal(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    analytics = _build_history_analytics(intersection, days=7)
    lane_media = _build_lane_media_map(intersection)
    return render_template("smart_signal.html", intersection=intersection, analytics=analytics, lane_media=lane_media)


@app.route("/intersection/<intersection_id>/signal-wall")
@login_required
def signal_wall(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        flash("Intersection not found.", "error")
        return redirect(url_for("intersections"))
    signal_snapshot = _build_signal_wall_snapshot(intersection)
    return render_template("signal_wall.html", intersection=intersection, signal_snapshot=signal_snapshot)


@app.route("/api/intersection/<intersection_id>/smart-signal/analyze", methods=["POST"])
@login_required
def analyze_smart_signal(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    uploaded_files = {}
    for key in request.files:
        if not key.startswith("images[") or not key.endswith("]"):
            continue
        lane_id = key[7:-1]
        uploaded_files[lane_id] = request.files[key]

    analysis_timestamp = _normalize_analysis_timestamp(request.form.get("analysis_timestamp"))
    event_duration_minutes = _normalize_event_duration(request.form.get("event_duration_minutes"))

    payload, error = _build_lane_analysis(intersection, uploaded_files)
    if error:
        return {"error": error}, 400
    payload["analysis_mode"] = "photo"
    payload["analysis_timestamp"] = analysis_timestamp
    payload["event_duration_minutes"] = event_duration_minutes
    payload["lane_media"] = _build_lane_media_map(intersection)
    _append_traffic_history(intersection, payload)
    payload["analytics"] = _build_history_analytics(intersection, days=7)

    return payload


@app.route("/api/intersection/<intersection_id>/smart-signal/analyze-video", methods=["POST"])
@login_required
def analyze_smart_signal_video(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    uploaded_videos = {}
    for key in request.files:
        if not key.startswith("videos[") or not key.endswith("]"):
            continue
        lane_id = key[7:-1]
        uploaded_videos[lane_id] = request.files[key]

    analysis_timestamp = _normalize_analysis_timestamp(request.form.get("analysis_timestamp"))
    event_duration_minutes = _normalize_event_duration(request.form.get("event_duration_minutes"))
    payload, error = _build_lane_video_analysis(
        intersection,
        uploaded_videos,
        analysis_timestamp=analysis_timestamp,
        event_duration_minutes=event_duration_minutes,
    )
    if error:
        return {"error": error}, 400

    payload["analysis_mode"] = "video"
    _append_traffic_history(intersection, payload)
    payload["analytics"] = _build_history_analytics(intersection, days=7)
    return payload


@app.route("/api/intersection/<intersection_id>/smart-signal/analyze-live", methods=["POST"])
@login_required
def analyze_smart_signal_live(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    data = request.get_json(silent=True) or {}
    live_frames = data.get("frames") or {}
    analysis_timestamp = _normalize_analysis_timestamp(data.get("analysis_timestamp"))
    event_duration_minutes = _normalize_event_duration(data.get("event_duration_minutes") or 1)

    payload, error = _build_live_lane_analysis(
        intersection,
        live_frames,
        analysis_timestamp=analysis_timestamp,
        event_duration_minutes=event_duration_minutes,
    )
    if error:
        return {"error": error}, 400

    payload["analytics"] = _build_history_analytics(intersection, days=7)
    payload["persisted_to_history"] = False

    if data.get("persist") and _should_persist_live_history(intersection_id):
        _append_traffic_history(intersection, payload)
        payload["persisted_to_history"] = True
        payload["analytics"] = _build_history_analytics(intersection, days=7)

    return payload


@app.route("/api/analyze-traffic", methods=["POST"])
@login_required
def analyze_traffic():
    intersection_id = request.form.get("intersection_id", "").strip()
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    uploaded_files = {}
    for key in request.files:
        if not key.startswith("images[") or not key.endswith("]"):
            continue
        lane_id = key[7:-1]
        uploaded_files[lane_id] = request.files[key]

    analysis_timestamp = _normalize_analysis_timestamp(request.form.get("analysis_timestamp"))
    event_duration_minutes = _normalize_event_duration(request.form.get("event_duration_minutes"))

    payload, error = _build_lane_analysis(intersection, uploaded_files)
    if error:
        return {"error": error}, 400
    payload["analysis_mode"] = "photo"
    payload["analysis_timestamp"] = analysis_timestamp
    payload["event_duration_minutes"] = event_duration_minutes
    _append_traffic_history(intersection, payload)

    return payload


@app.route("/api/intersection/<intersection_id>/smart-signal/history")
@login_required
def smart_signal_history(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    try:
        days = int(request.args.get("days", "7"))
    except ValueError:
        days = 7
    days = max(1, min(days, 30))

    return {
        "intersection_id": intersection_id,
        "analytics": _build_history_analytics(intersection, days=days),
    }


@app.route("/api/intersection/<intersection_id>/signal-wall")
@login_required
def signal_wall_data(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404
    return _build_signal_wall_snapshot(intersection)


@app.route("/api/intersection/<intersection_id>/lane/<lane_id>/video", methods=["DELETE"])
@login_required
def delete_lane_video(intersection_id, lane_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    deleted = _delete_lane_video(intersection, lane_id)
    if not deleted:
        return {"error": "No saved video found for this lane."}, 404

    return {
        "ok": True,
        "lane_id": lane_id,
        "lane_media": _build_lane_media_map(intersection),
        "message": "Lane video removed successfully.",
    }


@app.route("/api/intersection/<intersection_id>/smart-signal/photo-analyses", methods=["DELETE"])
@login_required
def delete_photo_analyses(intersection_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    deleted = _delete_photo_analysis_history(intersection_id)
    if not deleted:
        return {"error": "No photo-based analyses were found for this intersection."}, 404

    return {
        "ok": True,
        "analytics": _build_history_analytics(intersection, days=7),
        "message": "Photo-based analyses deleted successfully.",
    }


@app.route("/api/intersection/<intersection_id>/analysis/<analysis_id>", methods=["PATCH"])
@login_required
def update_analysis_record(intersection_id, analysis_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    data = request.get_json(silent=True) or {}
    analysis_timestamp = _normalize_analysis_timestamp(data.get("analysis_timestamp"))
    event_duration_minutes = _normalize_event_duration(data.get("event_duration_minutes"))
    updated = _update_analysis_record(
        intersection_id,
        analysis_id,
        analysis_timestamp=analysis_timestamp,
        event_duration_minutes=event_duration_minutes,
    )
    if not updated:
        return {"error": "Analysis record not found."}, 404

    return {
        "ok": True,
        "record": updated,
        "analytics": _build_history_analytics(intersection, days=7),
        "message": "Analysis record updated successfully.",
    }


@app.route("/api/intersection/<intersection_id>/analysis/<analysis_id>", methods=["DELETE"])
@login_required
def delete_analysis_record(intersection_id, analysis_id):
    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404

    deleted = _delete_analysis_record(intersection_id, analysis_id)
    if not deleted:
        return {"error": "Analysis record not found."}, 404

    return {
        "ok": True,
        "analytics": _build_history_analytics(intersection, days=7),
        "message": "Analysis record removed successfully.",
    }


@app.route("/api/optimize-signals", methods=["POST"])
@login_required
def optimize_signals():
    data = request.get_json(silent=True) or {}
    intersection_id = data.get("intersection_id", "").strip()
    traffic_data = data.get("traffic_data") or {}

    intersection = get_intersection(intersection_id)
    if not intersection:
        return {"error": "Intersection not found."}, 404
    if not isinstance(traffic_data, dict) or not traffic_data:
        return {"error": "Traffic data is required."}, 400

    normalized_data = {}
    total_vehicles = 0
    for direction, item in traffic_data.items():
        if not isinstance(item, dict):
            continue
        vehicles = max(0, int(item.get("vehicles", 0)))
        priority = max(1, int(item.get("priority", 1)))
        normalized_data[direction] = {"vehicles": vehicles, "priority": priority}
        total_vehicles += vehicles

    if not normalized_data:
        return {"error": "Traffic data is invalid."}, 400

    optimizer = get_signal_optimizer()
    congestion_score = min(100, int((total_vehicles / max(len(normalized_data), 1)) * 4))

    return {
        "intersection_id": intersection_id,
        "optimization": optimizer.optimize_signal(normalized_data),
        "schedule": optimizer.get_signal_schedule(normalized_data),
        "recommendations": optimizer.get_recommendations(normalized_data, congestion_score),
        "decision": optimizer.build_phase_decision(normalized_data),
    }


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

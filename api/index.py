import os
import datetime
import hmac
import hashlib
import base64
import json
import urllib.request
import urllib.parse
from flask import Flask, request, jsonify, redirect, url_for, make_response, send_from_directory
from pymongo import MongoClient
from functools import wraps
try:
    import dns.resolver
except ImportError:
    print("\n[CRITICAL] 'dnspython' module not found! This is required for MongoDB Atlas connections.")
    print("Please run: pip install dnspython\n")

basedir = os.path.abspath(os.path.dirname(__file__))
public_dir = os.path.abspath(os.path.join(basedir, '..', 'public'))

app = Flask(__name__, static_folder=public_dir, template_folder=public_dir, static_url_path='')

def get_asset(filename):
    candidates = [
        public_dir,
        os.path.join(os.getcwd(), 'public'),
        '/var/task/public',
    ]
    for directory in candidates:
        full_path = os.path.join(directory, filename)
        if os.path.exists(full_path):
            return send_from_directory(directory, filename)
    
    raise FileNotFoundError(f"Asset '{filename}' not found")

@app.route('/debug-dir')
def debug_dir():
    import os
    cwd = os.getcwd()
    parent = os.path.abspath(os.path.join(cwd, '..'))
    return jsonify({
        "cwd": cwd,
        "cwd_contents": os.listdir(cwd) if os.path.exists(cwd) else "Not Found",
        "parent": parent,
        "parent_contents": os.listdir(parent) if os.path.exists(parent) else "Not Found",
        "basedir": basedir,
        "basedir_contents": os.listdir(basedir) if os.path.exists(basedir) else "Not Found",
        "static_folder": app.static_folder,
        "static_exists": os.path.exists(app.static_folder),
        "static_contents": os.listdir(app.static_folder) if os.path.exists(app.static_folder) else "Not Found",
        "env": {k: v for k, v in os.environ.items() if "URI" not in k and "PASS" not in k}
    })

def is_authenticated():
    token = request.cookies.get('auth_token')
    if token and verify_token(token):
        return True
        
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            if verify_token(token):
                return True
                
    return False

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_any(path):
    path = path.rstrip('/')
    check_path = f"/{path}" if path else "/"
    
    public_paths = ['/api/login', '/login', '/login.html', '/sitemap.xml', '/robots.txt']
    allowed_exts = ['.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.txt']
    
    is_public = check_path in public_paths or any(check_path.endswith(ext) for ext in allowed_exts)
    
    if path == '':
        if not is_authenticated():
            return redirect('/login')
        return redirect('/home')
        
    if path in ['home', 'home.html', 'dashboard', 'dashboard.html']:
        if not is_authenticated():
            return redirect('/login')
        try:
            return get_asset('home.html')
        except Exception as e:
            return error_404(e)
        
    if path == 'login' or path == 'login.html':
        if is_authenticated():
            return redirect('/home')
        return get_asset('login.html')

    if path == 'admin' or path == 'admin.html':
        if not is_authenticated():
            return redirect('/login')
        role = request.cookies.get('user_role')
        if role not in ['MIC', 'President']:
            return redirect('/home')
        return get_asset('admin.html')

    if path == 'logout':
        response = make_response(redirect('/login'))
        response.delete_cookie('user_email', path='/')
        response.delete_cookie('user_role', path='/')
        return response

    if path.startswith('api/') and not is_authenticated():
        return jsonify({"success": False, "message": "Authentication required"}), 401

    if not is_public and not is_authenticated():
        return redirect('/login')

    if '.' not in path and not path.startswith('api/'):
        full_path = f"{path}.html"
    else:
        full_path = path
        
    try:
        return get_asset(full_path)
    except:
        return error_404(None)

@app.errorhandler(404)
def error_404(e):
    try:
        return get_asset('404.html'), 404
    except:
        return f"Error: 404 - Signal Lost. Coordinate not found in the grid.", 404

@app.route('/404')
def not_found_page():
    try:
        return get_asset('404.html'), 404
    except:
        return f"Error: 404 - Signal Lost. Coordinate not found in the grid.", 404
def sitemap():
    static_pages = ['home.html', 'team.html', 'calendar.html', 'attendance.html', 'inventory.html', 'dispatch.html', 'login.html', 'admin.html']
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for page in static_pages:
        url = page.replace('.html', '') if page != 'index.html' else ''
        xml.append('  <url>')
        xml.append(f'    <loc>{request.host_url}{url}</loc>')
        xml.append(f'    <lastmod>{now}</lastmod>')
        xml.append('    <priority>0.8</priority>')
        xml.append('  </url>')
    xml.append('</urlset>')
    return "\n".join(xml), 200, {'Content-Type': 'application/xml'}

@app.route('/robots.txt')
def robots():
    return f"User-agent: *\nAllow: /\nSitemap: {request.host_url}sitemap.xml", 200, {'Content-Type': 'text/plain'}

MONGO_URI = os.environ.get("MONGODB_URI") or "mongodb+srv://zenitha2026_db_user:XcTad72Wsa1pLufY@cluster0.la5cscc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0&readPreference=primaryPreferred"
SECRET_KEY = os.environ.get("SECRET_KEY") or "mumm-super-secret-2026-key-!@#"

def generate_token(payload):
    payload['exp'] = (datetime.datetime.now() + datetime.timedelta(days=7)).timestamp()
    payload_str = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).digest()
    sig_str = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    return f"{payload_str}.{sig_str}"

def verify_token(token):
    if not token: return None
    try:
        payload_str, sig_str = token.split('.')
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_str.encode(), hashlib.sha256).digest()
        expected_sig_str = base64.urlsafe_b64encode(expected_sig).decode().rstrip('=')
        if not hmac.compare_digest(sig_str, expected_sig_str):
            return None
        padding = '=' * (4 - len(payload_str) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_str + padding).decode())
        if datetime.datetime.now().timestamp() > payload.get('exp', 0):
            return None
        return payload
    except:
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        if not token and 'auth_token' in request.cookies:
            token = request.cookies.get('auth_token')
        user_data = verify_token(token)
        if not user_data:
            return jsonify({"success": False, "message": "Token is missing or invalid"}), 401
        request.user = user_data
        return f(*args, **kwargs)
    return decorated

_mongo_client = None
import traceback

def get_db():
    global _mongo_client
    if _mongo_client is None:
        try:
            _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        except Exception as e:
            print(f"FAILED TO CONNECT TO MONGODB: {e}")
            traceback.print_exc()
            _mongo_client = None
            raise e
    return _mongo_client["mumms_inventory"]

def get_collection(collection_name):
    try:
        db = get_db()
        return db[collection_name]
    except Exception as e:
        print(f"DB Collection Access Error ({collection_name}): {e}")
        return None
        
RECAPTCHA_SECRET = os.environ.get("RECAPTCHA_SECRET") or "6LfouucsAAAAAFcK65IiyszNzaxIRNyLl3vp4RFO"

def verify_captcha(response_token):
    return True

@app.route('/api/login', methods=['POST'])
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    email = data.get('email')
    password = data.get('password')
    captcha = data.get('captcha')
    if not email or not password:
        return jsonify({"success": False, "message": "Missing credentials"}), 400
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        user = collection.find_one({"email": email, "password": password}, {"_id": 0})
        if user:
            token = generate_token({
                "email": user['email'],
                "role": user.get('role', 'Member'),
                "displayName": user.get('displayName', user['email'])
            })
            response = make_response(jsonify({
                "success": True, 
                "token": token,
                "user": {
                    "email": user['email'],
                    "role": user.get('role', 'Member'),
                    "displayName": user.get('displayName', user['email'])
                }
            }))
            response.set_cookie('auth_token', token, httponly=True, max_age=604800, path='/', samesite='Lax')
            response.set_cookie('user_email', user['email'], max_age=604800, path='/', samesite='Lax')
            response.set_cookie('user_role', user.get('role', 'Member'), max_age=604800, path='/', samesite='Lax')
            return response, 200
        else:
            return jsonify({"success": False, "message": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/auth/change-password', methods=['POST'])
@token_required
def change_password():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    if not current_password or not new_password:
        return jsonify({"success": False, "message": "Missing current or new password"}), 400
    email = request.user.get('email')
    collection = get_collection("users")
    try:
        user = collection.find_one({"email": email, "password": current_password})
        if not user:
            return jsonify({"success": False, "message": "Incorrect current password"}), 400
        collection.update_one({"email": email}, {"$set": {"password": new_password}})
        return jsonify({"success": True, "message": "Password updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/logout')
def logout():
    response = make_response(redirect('/login'))
    response.set_cookie('auth_token', '', expires=0, path='/')
    response.set_cookie('user_email', '', expires=0, path='/')
    response.set_cookie('user_role', '', expires=0, path='/')
    return response

@app.route('/api/item', methods=['GET'])
def get_item():
    qr_id = request.args.get('qrId')
    if not qr_id:
        return jsonify({"success": False, "message": "Missing qrId parameter"}), 400
    collection = get_collection("equipment")
    if collection is None:
        return jsonify({
            "success": True, 
            "data": {
                "name": f"Mock Item ({qr_id})",
                "category": "Development",
                "status": "Active"
            },
            "message": "Fallback to mock data (DB connection failed)"
        }), 200
    try:
        item = collection.find_one({"customId": qr_id}, {"_id": 0})
        if item:
            return jsonify({"success": True, "data": item}), 200
        else:
            return jsonify({"success": False, "message": "Item not found in inventory"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/equipment', methods=['GET'])
def get_all_equipment():
    collection = get_collection("equipment")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        current_user = request.args.get('current_user')
        query = {}
        if current_user:
            query["current_user"] = current_user
        items = list(collection.find(query, {"_id": 0}))
        return jsonify({"success": True, "equipment": items}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/users', methods=['GET'])
@token_required
def get_users():
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        users = list(collection.find({}, {"_id": 0, "password": 0}))
        return jsonify({"success": True, "users": users}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/events', methods=['GET'])
@token_required
def get_events():
    collection = get_collection("events")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        events = []
        for doc in collection.find({}):
            doc['_id'] = str(doc['_id'])
            events.append(doc)
        return jsonify({"success": True, "events": events}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/events', methods=['POST'])
@token_required
def create_event():
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    collection = get_collection("events")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        event = {
            "title": data.get('title'),
            "date": data.get('date'),
            "venue": data.get('venue'),
            "status": data.get('status', 'Planned'),
            "assigned_members": data.get('assigned_members', [])
        }
        collection.insert_one(event)
        if '_id' in event:
            event.pop('_id')
        return jsonify({"success": True, "event": event}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/events/<event_id>', methods=['DELETE'])
@token_required
def delete_event(event_id):
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    collection = get_collection("events")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        from bson.objectid import ObjectId
        result = collection.delete_one({"_id": ObjectId(event_id)})
        if result.deleted_count > 0:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": "Event not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/events/<event_id>', methods=['PUT'])
@token_required
def update_event(event_id):
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    collection = get_collection("events")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        from bson.objectid import ObjectId
        update_data = {
            "title": data.get('title'),
            "date": data.get('date'),
            "venue": data.get('venue'),
            "status": data.get('status'),
            "assigned_members": data.get('assigned_members')
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}
        result = collection.update_one({"_id": ObjectId(event_id)}, {"$set": update_data})
        if result.matched_count > 0:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": "Event not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/users', methods=['POST'])
@token_required
def register_user():
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        if collection.find_one({"email": data.get('email')}):
            return jsonify({"success": False, "message": "User already exists"}), 400
        user = {
            "email": data.get('email'),
            "password": data.get('password'),
            "displayName": data.get('displayName'),
            "role": data.get('role', 'Member')
        }
        collection.insert_one(user)
        return jsonify({"success": True}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/users/<email>', methods=['DELETE'])
@token_required
def delete_user(email):
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        result = collection.delete_one({"email": email})
        if result.deleted_count > 0:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": "User not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/users/<email>', methods=['PUT'])
@token_required
def update_user_role(email):
    if request.user.get('role') not in ('MIC', 'President'):
        return jsonify({"success": False, "message": "Permission denied"}), 403
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        result = collection.update_one({"email": email}, {"$set": {"role": data.get('role')}})
        if result.matched_count > 0:
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": "User not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance', methods=['POST'])
def mark_attendance():
    from datetime import datetime, timezone
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    email = data.get('email')
    event_title = data.get('event_title')
    action_type = data.get('type')
    if not email or not event_title or not action_type:
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    collection = get_collection("attendance")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        server_ts = datetime.now(timezone.utc)
        logs = list(collection.find({"email": email}).sort("timestamp", -1).limit(1))
        last_log = logs[0] if logs else None
        is_active = last_log is not None and last_log.get('type') == 'check_in'
        active_event = last_log.get('event_title') if is_active else None
        if action_type == 'check_in':
            if is_active:
                if active_event == event_title:
                    return jsonify({"success": False, "message": "Already checked in to this event"}), 409
                else:
                    return jsonify({"success": False, "message": f"Already checked in to: {active_event}. Check out first."}), 409
        elif action_type == 'check_out':
            if not is_active:
                return jsonify({"success": False, "message": "You are not currently checked in to any event"}), 409
            if active_event != event_title:
                return jsonify({"success": False, "message": f"Check-out failed: you are checked in to '{active_event}', not this event"}), 409
        collection.insert_one({
            "event_title": event_title,
            "email": email,
            "type": action_type,
            "timestamp": server_ts
        })
        return jsonify({"success": True, "timestamp": server_ts.isoformat()}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance/status', methods=['GET'])
@token_required
def get_attendance_status():
    target_email = request.args.get('email') or request.user.get('email')
    collection = get_collection("attendance")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        logs = list(collection.find({"email": target_email}).sort("timestamp", -1).limit(1))
        last_log = logs[0] if logs else None
        is_checked_in = last_log is not None and last_log.get('type') == 'check_in'
        active_event = last_log.get('event_title') if is_checked_in else None
        return jsonify({
            "success": True,
            "is_checked_in": is_checked_in,
            "active_event": active_event
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance', methods=['GET'])
@token_required
def get_attendance():
    requester_email = request.user.get('email')
    requester_role = request.user.get('role')
    target_email = request.args.get('email')
    if requester_role not in ('MIC', 'President'):
        if target_email and target_email != requester_email:
            return jsonify({"success": False, "message": "Permission denied"}), 403
        target_email = requester_email
    collection = get_collection("attendance")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        query = {"email": target_email} if target_email else {}
        logs = list(collection.find(query, {"_id": 0}).sort("timestamp", -1))
        for log in logs:
            if hasattr(log.get('timestamp'), 'isoformat'):
                log['timestamp'] = log['timestamp'].isoformat()
        return jsonify({"success": True, "logs": logs}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/dispatch', methods=['GET'])
@token_required
def get_dispatch():
    if request.user.get('role') not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied"}), 403
    collection = get_collection("dispatch")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        logs = list(collection.find({}, {"_id": 0}).sort("timestamp", -1))
        return jsonify({"success": True, "logs": logs}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/dispatch', methods=['POST'])
def dispatch_item():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
    custom_id = data.get('customId')
    action_type = data.get('type')
    member = data.get('member')
    purpose = data.get('purpose')
    timestamp = data.get('timestamp')
    try:
        equip_coll = get_collection("equipment")
        if equip_coll is None:
            return jsonify({"success": False, "message": "Database connection error"}), 500
        update_data = {"status": "checked_out" if action_type == 'checkout' else 'available'}
        if action_type == 'checkout':
            update_data["current_user"] = member
        else:
            update_data["current_user"] = None
        result = equip_coll.update_one({"customId": custom_id}, {"$set": update_data})
        if result.matched_count == 0:
            return jsonify({"success": False, "message": "Item not found"}), 404
        dispatch_coll = get_collection("dispatch")
        dispatch_coll.insert_one({
            "customId": custom_id,
            "type": action_type,
            "member": member,
            "purpose": purpose,
            "timestamp": timestamp
        })
        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/equipment/active', methods=['GET'])
@token_required
def get_active_equipment():
    if request.user.get('role') not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied"}), 403
    equip_coll = get_collection("equipment")
    if equip_coll is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        active_items = list(equip_coll.find({"status": {"$ne": "available"}}, {"_id": 0}))
        return jsonify({"success": True, "items": active_items}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/equipment/tracker', methods=['GET'])
@token_required
def track_equipment():
    if request.user.get('role') not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied"}), 403
    try:
        custom_id = request.args.get('id')
        if not custom_id:
            return jsonify({"success": False, "message": "ID parameter required"}), 400
        equip_coll = get_collection("equipment")
        item = equip_coll.find_one({"customId": custom_id}, {"_id": 0})
        if not item:
            return jsonify({"success": False, "message": "Equipment not found"}), 404
        att_coll = get_collection("attendance")
        att_logs = list(att_coll.find({"qr_id": custom_id}, {"_id": 0}).sort("timestamp", -1))
        disp_coll = get_collection("dispatch")
        disp_logs = list(disp_coll.find({"customId": custom_id}, {"_id": 0}).sort("timestamp", -1))
        for l in att_logs:
            if hasattr(l.get('timestamp'), 'isoformat'):
                l['timestamp'] = l['timestamp'].isoformat()
        total_uses = len([l for l in att_logs if l.get('type') == 'check_in']) + \
                     len([l for l in disp_logs if l.get('type') == 'checkout'])
        return jsonify({
            "success": True,
            "item": item,
            "stats": {
                "total_uses": total_uses,
                "attendance_logs": att_logs[:10],
                "dispatch_logs": disp_logs[:10]
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)

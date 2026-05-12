import os
from flask import Flask, request, jsonify, redirect, url_for, make_response, send_from_directory
from pymongo import MongoClient

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, static_folder=basedir, template_folder=basedir, static_url_path='')

# Define where to look for assets (now all in the api folder)
def get_asset(filename):
    local_path = os.path.join(basedir, filename)
    if os.path.exists(local_path):
        return send_from_directory(basedir, filename)
    return f"Asset {filename} Not Found at {local_path}", 404

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
    return 'user_email' in request.cookies

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_any(path):
    # Normalize path for checking
    check_path = f"/{path}" if path else "/"
    
    # Public paths that don't need login
    public_paths = ['/api/login', '/login', '/login.html', '/sitemap.xml', '/robots.txt']
    # Allow static assets
    allowed_exts = ['.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.txt']
    
    is_public = check_path in public_paths or any(check_path.endswith(ext) for ext in allowed_exts)
    
    # Handle the root path
    if path == '':
        if not is_authenticated():
            return redirect('/login')
        return redirect('/team')
        
    # Handle the home path specifically (Dashboard)
    if path in ['home', 'home.html', 'index', 'index.html']:
        if not is_authenticated():
            return redirect('/login')
        try:
            # Explicitly serve index.html from the api folder (basedir)
            return send_from_directory(basedir, 'index.html')
        except Exception as e:
            return f"Error serving index.html from {basedir}: {str(e)}", 404
        
    # Handle the login path specifically
    if path == 'login' or path == 'login.html':
        if is_authenticated():
            return redirect('/')
        try:
            return send_from_directory(basedir, 'login.html')
        except:
            return get_asset('login.html')

    # Handle admin path specifically
    if path == 'admin' or path == 'admin.html':
        if not is_authenticated():
            return redirect('/login')
        role = request.cookies.get('user_role')
        if role not in ['MIC', 'President']:
            return redirect('/')
        return get_asset('admin.html')

    # Handle logout
    if path == 'logout':
        response = make_response(redirect('/login'))
        response.delete_cookie('user_email', path='/')
        response.delete_cookie('user_role', path='/')
        return response

    # If it's an API call, return 401 if not authenticated
    if path.startswith('api/') and not is_authenticated():
        return jsonify({"success": False, "message": "Authentication required"}), 401

    # Handle all other pages
    if not is_public and not is_authenticated():
        return redirect('/login')

    # Handle clean URLs by appending .html if it doesn't have an extension
    if '.' not in path:
        full_path = f"{path}.html"
    else:
        full_path = path
        
    try:
        return get_asset(full_path)
    except Exception as e:
        return f"Error serving {full_path}: {str(e)}", 404

@app.route('/sitemap.xml')
def sitemap():
    pages = []
    # Dynamic list of pages
    static_pages = ['index.html', 'team.html', 'calendar.html', 'attendance.html', 'inventory.html', 'dispatch.html', 'login.html', 'admin.html']
    
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

MONGO_URI = os.environ.get("MONGODB_URI") or "mongodb+srv://zenitha2026_db_user:XcTad72Wsa1pLufY@cluster0.la5cscc.mongodb.net/?appName=Cluster0"

def get_collection(collection_name):
    try:
        client = MongoClient(MONGO_URI)
        db = client["mumms_inventory"]
        return db[collection_name]
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
        
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"success": False, "message": "Missing email or password"}), 400
        
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
        
    try:
        # Find user with matching email and password
        user = collection.find_one({"email": email, "password": password}, {"_id": 0})
        if user:
            response = jsonify({"success": True, "user": user})
            # Set a cookie for backend login check
            response.set_cookie('user_email', email, httponly=True, max_age=86400, path='/', samesite='Lax')
            response.set_cookie('user_role', user.get('role', 'Member'), httponly=True, max_age=86400, path='/', samesite='Lax')
            return response, 200
        else:
            return jsonify({"success": False, "message": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/item', methods=['GET'])
def get_item():
    qr_id = request.args.get('qrId')
    if not qr_id:
        return jsonify({"success": False, "message": "Missing qrId parameter"}), 400
    
    collection = get_collection("equipment") # Using 'equipment' collection from your image
    if collection is None:
        # Fallback to mock data for local testing if DB fails
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
        # Query MongoDB for this ID, exclude the _id field
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
def get_users():
    collection = get_collection("users")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    try:
        users = list(collection.find({}, {"_id": 0, "password": 0}))
        return jsonify({"success": True, "users": users}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/events', methods=['GET'])
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
def create_event():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
        
    user_role = data.get('user_role')
    if user_role not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied. Only MIC and President can assign duties."}), 403
        
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
def delete_event(event_id):
    user_role = request.args.get('user_role')
    if user_role not in ['MIC', 'President']:
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
def update_event(event_id):
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
        
    user_role = data.get('user_role')
    if user_role not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied"}), 403
        
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
def register_user():
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
        
    user_role = data.get('admin_role')
    if user_role not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied"}), 403
        
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
def delete_user(email):
    user_role = request.args.get('user_role')
    if user_role not in ['MIC', 'President']:
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
def update_user_role(email):
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
        
    user_role = data.get('admin_role')
    if user_role not in ['MIC', 'President']:
        return jsonify({"success": False, "message": "Permission denied"}), 403
        
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
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "Missing request body"}), 400
        
    collection = get_collection("attendance")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
        
    try:
        attendance_record = {
            "event_title": data.get('event_title'),
            "email": data.get('email'),
            "type": data.get('type'),
            "timestamp": data.get('timestamp')
        }
        collection.insert_one(attendance_record)
        return jsonify({"success": True}), 201
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    requester_email = request.headers.get('X-User-Email')
    requester_password = request.headers.get('X-User-Password')
    target_email = request.args.get('email')
    
    if not requester_email or not requester_password:
        return jsonify({"success": False, "message": "Missing credentials"}), 401
        
    users_coll = get_collection("users")
    requester = users_coll.find_one({"email": requester_email, "password": requester_password})
    
    if not requester:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401
        
    if requester['role'] not in ['MIC', 'President']:
        if target_email and target_email != requester_email:
            return jsonify({"success": False, "message": "Permission denied"}), 403
        target_email = requester_email
        
    collection = get_collection("attendance")
    if collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
        
    try:
        query = {}
        if target_email:
            query["email"] = target_email
            
        logs = list(collection.find(query, {"_id": 0}).sort("timestamp", -1))
        return jsonify({"success": True, "logs": logs}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/dispatch', methods=['GET'])
def get_dispatch():
    requester_email = request.headers.get('X-User-Email')
    requester_password = request.headers.get('X-User-Password')
    
    if not requester_email or not requester_password:
        return jsonify({"success": False, "message": "Missing credentials"}), 401
        
    users_coll = get_collection("users")
    requester = users_coll.find_one({"email": requester_email, "password": requester_password})
    
    if not requester or requester['role'] not in ['MIC', 'President']:
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

if __name__ == '__main__':
    app.run(debug=True)

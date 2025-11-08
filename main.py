from flask import Flask, request, jsonify, render_template_string
import json, os, random, string
from datetime import datetime, timedelta

app = Flask(__name__)

# ==========================
# ⚙️ CONFIGURATION
# ==========================
DATA_FILE = "licenses.json"
ADMIN_PASSWORD = "MySecret123"  # change this
DEFAULT_EXPIRY_DAYS = 30        # license validity duration (in days)

# ==========================
# 🗂️ LOAD & SAVE FUNCTIONS
# ==========================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        licenses = json.load(f)
else:
    licenses = {}

def save_licenses():
    with open(DATA_FILE, "w") as f:
        json.dump(licenses, f, indent=2)

def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

# ==========================
# 🧾 ROUTES
# ==========================

@app.route("/")
def home():
    return "✅ License API running successfully!"

# 🔑 ADMIN: Generate license
# @app.route("/verify", methods=["GET"])
# def verify_license():
#     key = request.args.get("key")
#     user_id = request.args.get("user_id")

#     if not key or key not in licenses:
#         return jsonify({"valid": False, "reason": "invalid_key"}), 404

#     info = licenses[key]
#     expires = datetime.strptime(info["expires"], "%Y-%m-%d")
#     now = datetime.now()

#     # Check expiration
#     if now > expires:
#         return jsonify({
#             "valid": False,
#             "user": info["user"],
#             "reason": "expired",
#             "expired_on": info["expires"]
#         })

#     bound_to = info.get("bound_to")
#     in_use = info.get("in_use", False)
#     last_check = info.get("last_check")

#     # If license not bound → bind it
#     if not bound_to:
#         info["bound_to"] = user_id
#         info["in_use"] = True
#         info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
#         save_licenses()
#         return jsonify({
#             "valid": True,
#             "user": info["user"],
#             "expires": info["expires"],
#             "bound_to": user_id,
#             "note": "License successfully bound and activated"
#         })

#     # Check if license belongs to another server
#     if bound_to != user_id:
#         return jsonify({
#             "valid": False,
#             "reason": "license_already_in_use",
#             "bound_to": bound_to
#         })

#     # License belongs to same server
#     # Check if already in use (other instance running)
#     if in_use:
#         # Allow re-verification if last check > 10 minutes ago (to handle crashed servers)
#         if last_check:
#             last_dt = datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S")
#             if (now - last_dt).total_seconds() < 600:  # 10 minutes
#                 return jsonify({
#                     "valid": False,
#                     "reason": "license_already_in_use",
#                     "note": "Another active session detected"
#                 })

#     # Mark as in use (renew session)
#     info["in_use"] = True
#     info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
#     save_licenses()

#     return jsonify({
#         "valid": True,
#         "user": info["user"],
#         "expires": info["expires"],
#         "bound_to": bound_to
#     })
@app.route("/verify", methods=["GET"])
def verify_license():
    key = request.args.get("key")
    user_id = request.args.get("user_id")

    if not key or key not in licenses:
        return jsonify({"valid": False, "reason": "invalid_key"}), 404

    info = licenses[key]
    expires = datetime.strptime(info["expires"], "%Y-%m-%d")
    now = datetime.now()

    # Check expiration
    if now > expires:
        return jsonify({
            "valid": False,
            "user": info["user"],
            "reason": "expired",
            "expired_on": info["expires"]
        })

    bound_to = info.get("bound_to")
    in_use = info.get("in_use", False)
    last_check = info.get("last_check")

    # Case 1️⃣: License is not bound or not in use → allow new server
    if not bound_to or not in_use:
        info["bound_to"] = user_id
        info["in_use"] = True
        info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_licenses()
        return jsonify({
            "valid": True,
            "user": info["user"],
            "expires": info["expires"],
            "bound_to": user_id,
            "note": "License is now active for this server"
        })

    # Case 2️⃣: License is already in use by another server → deny
    if bound_to != user_id and in_use:
        # Check timeout (if last check >10min ago, assume server crashed → free it)
        if last_check:
            last_dt = datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S")
            if (now - last_dt).total_seconds() > 600:  # 10 minutes
                info["bound_to"] = user_id
                info["in_use"] = True
                info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
                save_licenses()
                return jsonify({
                    "valid": True,
                    "user": info["user"],
                    "expires": info["expires"],
                    "bound_to": user_id,
                    "note": "Previous session timed out, license re-assigned"
                })
        return jsonify({
            "valid": False,
            "reason": "license_in_use",
            "bound_to": bound_to
        })

    # Case 3️⃣: Same server rechecking → refresh timestamp
    if bound_to == user_id:
        info["in_use"] = True
        info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_licenses()
        return jsonify({
            "valid": True,
            "user": info["user"],
            "expires": info["expires"],
            "bound_to": bound_to
        })

# 🕒 ADMIN: Extend license expiration
@app.route("/extend", methods=["POST"])
def extend_license():
    auth = request.args.get("auth")
    key = request.args.get("key")
    days = request.args.get("days")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if key not in licenses:
        return jsonify({"success": False, "error": "License not found"}), 404

    try:
        days = int(days)
    except:
        return jsonify({"success": False, "error": "Invalid days value"}), 400

    current_exp = datetime.strptime(licenses[key]["expires"], "%Y-%m-%d")
    new_exp = current_exp + timedelta(days=days)
    licenses[key]["expires"] = new_exp.strftime("%Y-%m-%d")
    save_licenses()

    return jsonify({
        "success": True,
        "message": f"✅ License {key} extended by {days} days (new expiry: {licenses[key]['expires']})"
    })


# 💾 ADMIN: Download all license data
@app.route("/backup", methods=["GET"])
def backup():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    with open(DATA_FILE, "rb") as f:
        return f.read(), 200, {
            "Content-Type": "application/json",
            "Content-Disposition": "attachment; filename=licenses_backup.json"
        }

@app.route("/generate", methods=["POST", "GET"])
def generate_license():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    user = request.args.get("user", "unknown")
    days = request.args.get("days", DEFAULT_EXPIRY_DAYS)
    try:
        days = int(days)
    except ValueError:
        days = DEFAULT_EXPIRY_DAYS

    key = generate_key()
    expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    licenses[key] = {"user": user, "expires": expires}
    save_licenses()

    return jsonify({
        "success": True,
        "key": key,
        "user": user,
        "expires": expires
    })

# 🗑️ ADMIN: Delete a license
@app.route("/delete", methods=["POST"])
def delete_license():
    auth = request.args.get("auth")
    key = request.args.get("key")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if key not in licenses:
        return jsonify({"success": False, "error": "License not found"}), 404

    del licenses[key]
    save_licenses()

    return jsonify({"success": True, "message": f"🗑️ License {key} deleted successfully."})


# @app.route("/generate", methods=["POST"])
# def generate_license():
#     auth = request.args.get("auth")
#     if auth != ADMIN_PASSWORD:
#         return jsonify({"success": False, "error": "Unauthorized"}), 403

#     user = request.args.get("user", "unknown")
#     days = request.args.get("days", DEFAULT_EXPIRY_DAYS)
#     try:
#         days = int(days)
#     except ValueError:
#         days = DEFAULT_EXPIRY_DAYS

#     key = generate_key()
#     expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

#     licenses[key] = {"user": user, "expires": expires}
#     save_licenses()

#     return jsonify({
#         "success": True,
#         "key": key,
#         "user": user,
#         "expires": expires
#     })

# # 🔍 Plugin verification
# @app.route("/verify", methods=["GET"])
# def verify_license():
#     key = request.args.get("key")
#     user_id = request.args.get("user_id")  # Unique server/player ID

#     if not key or key not in licenses:
#         return jsonify({"valid": False, "reason": "invalid_key"}), 404

#     info = licenses[key]
#     expires = datetime.strptime(info["expires"], "%Y-%m-%d")
#     now = datetime.now()

#     # Expiration check
#     if now > expires:
#         return jsonify({
#             "valid": False,
#             "user": info["user"],
#             "reason": "expired",
#             "expired_on": info["expires"]
#         })

#     # Binding check
#     bound_to = info.get("bound_to")
#     if not bound_to:
#         # Bind to first user who uses it
#         info["bound_to"] = user_id
#         save_licenses()
#         return jsonify({
#             "valid": True,
#             "user": info["user"],
#             "expires": info["expires"],
#             "bound_to": user_id,
#             "note": "License successfully bound to this user."
#         })

#     # Already bound → must match
#     if bound_to != user_id:
#         return jsonify({
#             "valid": False,
#             "reason": "license_already_in_use",
#             "bound_to": bound_to
#         })

#     return jsonify({
#         "valid": True,
#         "user": info["user"],
#         "expires": info["expires"],
#         "bound_to": bound_to
#     })

# 🧹 ADMIN: Unbind a license
@app.route("/unbind", methods=["POST"])
def unbind_license():
    auth = request.args.get("auth")
    key = request.args.get("key")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if key not in licenses:
        return jsonify({"success": False, "error": "Invalid key"}), 404

    licenses[key].pop("bound_to", None)
    save_licenses()

    return jsonify({"success": True, "message": "License unbound successfully"})

# 🕒 ADMIN: Force expire a license immediately
@app.route("/expire", methods=["POST"])
def expire_license():
    auth = request.args.get("auth")
    key = request.args.get("key")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    if key not in licenses:
        return jsonify({"success": False, "error": "License not found"}), 404

    licenses[key]["expires"] = datetime.now().strftime("%Y-%m-%d")
    save_licenses()

    return jsonify({
        "success": True,
        "message": f"✅ License {key} has been expired immediately."
    })

@app.route("/release", methods=["POST"])
def release_license():
    key = request.args.get("key")
    user_id = request.args.get("user_id")
    auth = request.args.get("auth")

    if not key or key not in licenses:
        return jsonify({"success": False, "error": "Invalid key"}), 404

    info = licenses[key]
    if info.get("bound_to") == user_id:
        info["in_use"] = False
        save_licenses()
        return jsonify({"success": True, "message": "License released successfully"})

    return jsonify({"success": False, "error": "Unauthorized release attempt"}), 403



# 🧭 ADMIN DASHBOARD PAGE
# @app.route("/admin")
# def admin_dashboard():
#     auth = request.args.get("auth")
#     if auth != ADMIN_PASSWORD:
#         return "<h2>❌ Unauthorized</h2><p>Missing or incorrect ?auth= password in URL.</p>", 403

#     html = """
#     <html>
#     <head>
#       <title>License Dashboard</title>
#       <style>
#         body { font-family: Arial; background: #f3f3f3; margin: 20px; }
#         h1 { color: #222; }
#         table { border-collapse: collapse; width: 100%; background: white; }
#         th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
#         th { background: #eee; }
#         tr:hover { background: #f9f9f9; }
#         button { padding: 5px 10px; border: none; border-radius: 4px; cursor: pointer; }
#         .delete { background: #e74c3c; color: white; }
#         .expire { background: #f39c12; color: white; }
#         .unbind { background: #3498db; color: white; }
#       </style>
#     </head>
#     <body>
#       <h1>🔐 License Manager</h1>
#       <p>Logged in as <b>admin</b></p>
#       <table>
#         <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound To</th><th>Actions</th></tr>
#         {% for k, v in licenses.items() %}
#           <tr>
#             <td>{{ k }}</td>
#             <td>{{ v['user'] }}</td>
#             <td>{{ v['expires'] }}</td>
#             <td>{{ v.get('bound_to', '-') }}</td>
#             <td>
#               <button class="unbind" onclick="doAction('unbind','{{k}}')">Unbind</button>
#               <button class="expire" onclick="doAction('expire','{{k}}')">Expire</button>
#               <button class="delete" onclick="doAction('delete','{{k}}')">Delete</button>
#             </td>
#           </tr>
#         {% endfor %}
#       </table>

#       <script>
#       async function doAction(action, key) {
#         const res = await fetch(`/${action}?key=${key}&auth={{admin_pass}}`, { method: "POST" });
#         const data = await res.json();
#         alert(JSON.stringify(data, null, 2));
#        alert(data.message ? data.message : JSON.stringify(data, null, 2));

#         location.reload();
#       }
#       </script>
#     </body>
#     </html>
#     """
#     return render_template_string(html, licenses=licenses, admin_pass=ADMIN_PASSWORD)
# @app.route("/admin")
# def admin_dashboard():
#     auth = request.args.get("auth")
#     if auth != ADMIN_PASSWORD:
#         return "<h2>❌ Unauthorized</h2><p>Missing or incorrect ?auth= password in URL.</p>", 403

#     html = """
#     <!DOCTYPE html>
#     <html>
#     <head>
#       <title>License Manager</title>
#       <style>
#         body { font-family: Arial; background: #f5f6fa; margin: 40px; color: #2f3640; }
#         h1 { color: #192a56; }
#         table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
#         th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
#         th { background: #718093; color: white; }
#         tr:nth-child(even) { background: #f1f2f6; }
#         button { padding: 6px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
#         .delete { background: #e84118; color: white; }
#         .expire { background: #f39c12; color: white; }
#         .unbind { background: #0097e6; color: white; }
#         .generate { background: #44bd32; color: white; padding: 8px 15px; }
#         input { padding: 6px; margin-right: 5px; border-radius: 4px; border: 1px solid #ccc; }
#         form { margin-bottom: 20px; }
#       </style>
#     </head>
#     <body>
#       <h1>🔐 License Manager Dashboard</h1>
#       <p>Welcome, Admin!</p>

#       <form id="createForm">
#         <input type="text" id="username" placeholder="User name" required>
#         <input type="number" id="days" placeholder="Days" value="30" required>
#         <button type="submit" class="generate">➕ Create License</button>
#       </form>

#       <table>
#         <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound To</th><th>Actions</th></tr>
#         {% for k, v in licenses.items() %}
#         <tr>
#           <td>{{ k }}</td>
#           <td>{{ v['user'] }}</td>
#           <td>{{ v['expires'] }}</td>
#           <td>{{ v.get('bound_to', '-') }}</td>
#           <td>
#             <button class="unbind" onclick="action('unbind', '{{k}}')">Unbind</button>
#             <button class="expire" onclick="action('expire', '{{k}}')">Expire</button>
#             <button class="delete" onclick="action('delete', '{{k}}')">Delete</button>
#           </td>
#         </tr>
#         {% endfor %}
#       </table>

#       <script>
#       async function action(type, key) {
#         const url = `/${type}?key=${key}&auth={{admin_pass}}`;
#         const res = await fetch(url, { method: "POST" });
#         const data = await res.json();
#         alert(data.message ? data.message : JSON.stringify(data, null, 2));
#         location.reload();
#       }

#       document.getElementById("createForm").addEventListener("submit", async (e) => {
#         e.preventDefault();
#         const user = document.getElementById("username").value;
#         const days = document.getElementById("days").value;
#         const url = `/generate?user=${user}&days=${days}&auth={{admin_pass}}`;
#         const res = await fetch(url, { method: "POST" });
#         const data = await res.json();
#         alert("✅ New License Created: " + data.key);
#         location.reload();
#       });
#       </script>
#     </body>
#     </html>
#     """

#     return render_template_string(html, licenses=licenses, admin_pass=ADMIN_PASSWORD)
# @app.route("/admin")
# def admin_dashboard():
#     auth = request.args.get("auth")
#     if auth != ADMIN_PASSWORD:
#         return "<h2>❌ Unauthorized</h2><p>Missing or incorrect ?auth= password in URL.</p>", 403

#     html = """
#     <!DOCTYPE html>
#     <html>
#     <head>
#       <title>License Manager</title>
#       <style>
#         body { font-family: Arial; background: #f5f6fa; margin: 40px; color: #2f3640; }
#         h1 { color: #192a56; }
#         table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
#         th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
#         th { background: #718093; color: white; }
#         tr:nth-child(even) { background: #f1f2f6; }
#         button { padding: 6px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
#         .delete { background: #e84118; color: white; }
#         .expire { background: #f39c12; color: white; }
#         .extend { background: #44bd32; color: white; }
#         .unbind { background: #0097e6; color: white; }
#         .download { background: #8c7ae6; color: white; padding: 8px 15px; }
#         input { padding: 6px; margin-right: 5px; border-radius: 4px; border: 1px solid #ccc; }
#         form { margin-bottom: 20px; }
#       </style>
#     </head>
#     <body>
#       <h1>🔐 License Manager Dashboard</h1>
#       <p>Welcome, Admin!</p>

#       <form id="createForm">
#         <input type="text" id="username" placeholder="User name" required>
#         <input type="number" id="days" placeholder="Days" value="30" required>
#         <button type="submit" class="extend">➕ Create License</button>
#         <button type="button" class="download" onclick="window.location='/backup?auth={{admin_pass}}'">💾 Download Data</button>
#       </form>

#       <table>
#         <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound To</th><th>Actions</th></tr>
#         {% for k, v in licenses.items() %}
#         <tr>
#           <td>{{ k }}</td>
#           <td>{{ v['user'] }}</td>
#           <td>{{ v['expires'] }}</td>
#           <td>{{ v.get('bound_to', '-') }}</td>
#           <td>
#             <button class="extend" onclick="extendLicense('{{k}}')">Extend</button>
#             <button class="expire" onclick="action('expire', '{{k}}')">Expire</button>
#             <button class="unbind" onclick="action('unbind', '{{k}}')">Unbind</button>
#             <button class="delete" onclick="action('delete', '{{k}}')">Delete</button>
#           </td>
#         </tr>
#         {% endfor %}
#       </table>

#       <script>
#       async function action(type, key) {
#         const res = await fetch(`/${type}?key=${key}&auth={{admin_pass}}`, { method: "POST" });
#         const data = await res.json();
#         alert(data.message || JSON.stringify(data));
#         location.reload();
#       }

#       async function extendLicense(key) {
#         const days = prompt("Enter number of days to extend:");
#         if (!days) return;
#         const res = await fetch(`/extend?key=${key}&days=${days}&auth={{admin_pass}}`, { method: "POST" });
#         const data = await res.json();
#         alert(data.message || JSON.stringify(data));
#         location.reload();
#       }

#       document.getElementById("createForm").addEventListener("submit", async (e) => {
#         e.preventDefault();
#         const user = document.getElementById("username").value;
#         const days = document.getElementById("days").value;
#         const url = `/generate?user=${user}&days=${days}&auth={{admin_pass}}`;
#         const res = await fetch(url, { method: "POST" });
#         const data = await res.json();
#         alert("✅ New License Created: " + data.key);
#         location.reload();
#       });
#       </script>
#     </body>
#     </html>
#     """

#     return render_template_string(html, licenses=licenses, admin_pass=ADMIN_PASSWORD)

# @app.route("/admin")
# def admin_dashboard():
#     auth = request.args.get("auth")
#     if auth != ADMIN_PASSWORD:
#         return "<h2>❌ Unauthorized</h2><p>Missing or incorrect ?auth= password in URL.</p>", 403

#     html = """
#     <!DOCTYPE html>
#     <html>
#     <head>
#       <title>License Manager</title>
#       <style>
#         body { font-family: Arial, sans-serif; background: #f5f6fa; margin: 40px; color: #2f3640; }
#         h1 { color: #192a56; }
#         table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
#         th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
#         th { background: #718093; color: white; }
#         tr:nth-child(even) { background: #f1f2f6; }
#         tr.expired { background: #ff7675 !important; color: white; }      /* red */
#         tr.warning { background: #fbc531 !important; color: black; }     /* yellow */
#         tr.active { background: #44bd32 !important; color: white; }      /* green */
#         tr.unbound { background: #dcdde1 !important; color: #2f3640; }   /* gray */
#         button { padding: 6px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
#         .delete { background: #e84118; color: white; }
#         .expire { background: #f39c12; color: white; }
#         .extend { background: #44bd32; color: white; }
#         .unbind { background: #0097e6; color: white; }
#         .download { background: #8c7ae6; color: white; padding: 8px 15px; }
#         input { padding: 6px; margin-right: 5px; border-radius: 4px; border: 1px solid #ccc; }
#         form { margin-bottom: 20px; }
#       </style>
#     </head>
#     <body>
#       <h1>🔐 License Manager Dashboard</h1>
#       <p>Welcome, Admin!</p>

#       <form id="createForm">
#         <input type="text" id="username" placeholder="User name" required>
#         <input type="number" id="days" placeholder="Days" value="30" required>
#         <button type="submit" class="extend">➕ Create License</button>
#         <button type="button" class="download" onclick="window.location='/backup?auth={{admin_pass}}'">💾 Download Data</button>
#       </form>

#       <table>
#         <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound To</th><th>In Use</th><th>Actions</th></tr>
#         {% for k, v in licenses.items() %}
#         {% set cls = '' %}
#         {% set exp = v['expires'] %}
#         {% set bound = v.get('bound_to', '-') %}
#         {% set in_use = v.get('in_use', False) %}
#         {% set days_left = (datetime.strptime(exp, '%Y-%m-%d') - datetime.now()).days %}

#         {% if days_left < 0 %}
#           {% set cls = 'expired' %}
#         {% elif days_left <= 7 %}
#           {% set cls = 'warning' %}
#         {% elif not bound or bound == '-' %}
#           {% set cls = 'unbound' %}
#         {% else %}
#           {% set cls = 'active' %}
#         {% endif %}

#         <tr class="{{ cls }}">
#           <td>{{ k }}</td>
#           <td>{{ v['user'] }}</td>
#           <td>{{ v['expires'] }}</td>
#           <td>{{ bound }}</td>
#           <td>{{ '🟢' if in_use else '⚫' }}</td>
#           <td>
#             <button class="extend" onclick="extendLicense('{{k}}')">Extend</button>
#             <button class="expire" onclick="action('expire', '{{k}}')">Expire</button>
#             <button class="unbind" onclick="action('unbind', '{{k}}')">Unbind</button>
#             <button class="delete" onclick="action('delete', '{{k}}')">Delete</button>
#           </td>
#         </tr>
#         {% endfor %}
#       </table>

#       <script>
#       async function action(type, key) {
#         const res = await fetch(`/${type}?key=${key}&auth={{admin_pass}}`, { method: "POST" });
#         const data = await res.json();
#         alert(data.message || JSON.stringify(data));
#         location.reload();
#       }

#       async function extendLicense(key) {
#         const days = prompt("Enter number of days to extend:");
#         if (!days) return;
#         const res = await fetch(`/extend?key=${key}&days=${days}&auth={{admin_pass}}`, { method: "POST" });
#         const data = await res.json();
#         alert(data.message || JSON.stringify(data));
#         location.reload();
#       }

#       document.getElementById("createForm").addEventListener("submit", async (e) => {
#         e.preventDefault();
#         const user = document.getElementById("username").value;
#         const days = document.getElementById("days").value;
#         const url = `/generate?user=${user}&days=${days}&auth={{admin_pass}}`;
#         const res = await fetch(url, { method: "POST" });
#         const data = await res.json();
#         alert("✅ New License Created: " + data.key);
#         location.reload();
#       });
#       </script>
#     </body>
#     </html>
#     """

#     return render_template_string(
#         html,
#         licenses=licenses,
#         admin_pass=ADMIN_PASSWORD,
#         datetime=datetime
#     )

@app.route("/admin")
def admin_dashboard():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return "<h2>❌ Unauthorized</h2><p>Missing or incorrect ?auth= password in URL.</p>", 403

    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>License Manager</title>
      <style>
        body { font-family: Arial, sans-serif; background: #f5f6fa; margin: 40px; color: #2f3640; }
        h1 { color: #192a56; }
        table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background: #718093; color: white; }
        tr:nth-child(even) { background: #f1f2f6; }
        tr.expired { background: #ff7675 !important; color: white; }      /* red */
        tr.warning { background: #fbc531 !important; color: black; }     /* yellow */
        tr.active { background: #44bd32 !important; color: white; }      /* green */
        tr.unbound { background: #dcdde1 !important; color: #2f3640; }   /* gray */
        button { padding: 6px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .delete { background: #e84118; color: white; }
        .expire { background: #f39c12; color: white; }
        .extend { background: #44bd32; color: white; }
        .unbind { background: #0097e6; color: white; }
        .download { background: #8c7ae6; color: white; padding: 8px 15px; }
        input { padding: 6px; margin-right: 5px; border-radius: 4px; border: 1px solid #ccc; }
        form { margin-bottom: 20px; }
        #searchBox { width: 40%; padding: 8px; margin-bottom: 20px; border-radius: 8px; border: 1px solid #ccc; font-size: 14px; }
      </style>
    </head>
    <body>
      <h1>🔐 License Manager Dashboard</h1>
      <p>Welcome, Admin!</p>

      <form id="createForm">
        <input type="text" id="username" placeholder="User name" required>
        <input type="number" id="days" placeholder="Days" value="30" required>
        <button type="submit" class="extend">➕ Create License</button>
        <button type="button" class="download" onclick="window.location='/backup?auth={{admin_pass}}'">💾 Download Data</button>
      </form>

      <input type="text" id="searchBox" placeholder="🔍 Search by user, key, or bound server...">

      <table id="licenseTable">
        <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound To</th><th>In Use</th><th>Actions</th></tr>
        {% for k, v in licenses.items() %}
        {% set cls = '' %}
        {% set exp = v['expires'] %}
        {% set bound = v.get('bound_to', '-') %}
        {% set in_use = v.get('in_use', False) %}
        {% set days_left = (datetime.strptime(exp, '%Y-%m-%d') - datetime.now()).days %}

        {% if days_left < 0 %}
          {% set cls = 'expired' %}
        {% elif days_left <= 7 %}
          {% set cls = 'warning' %}
        {% elif not bound or bound == '-' %}
          {% set cls = 'unbound' %}
        {% else %}
          {% set cls = 'active' %}
        {% endif %}

        <tr class="{{ cls }}">
          <td>{{ k }}</td>
          <td>{{ v['user'] }}</td>
          <td>{{ v['expires'] }}</td>
          <td>{{ bound }}</td>
          <td>{{ '🟢' if in_use else '⚫' }}</td>
          <td>
            <button class="extend" onclick="extendLicense('{{k}}')">Extend</button>
            <button class="expire" onclick="action('expire', '{{k}}')">Expire</button>
            <button class="unbind" onclick="action('unbind', '{{k}}')">Unbind</button>
            <button class="delete" onclick="action('delete', '{{k}}')">Delete</button>
          </td>
        </tr>
        {% endfor %}
      </table>

      <script>
      // 🔍 Search Filter
      const searchBox = document.getElementById("searchBox");
      searchBox.addEventListener("keyup", () => {
        const filter = searchBox.value.toLowerCase();
        document.querySelectorAll("#licenseTable tr").forEach((row, i) => {
          if (i === 0) return; // skip header row
          const text = row.innerText.toLowerCase();
          row.style.display = text.includes(filter) ? "" : "none";
        });
      });

      async function action(type, key) {
        const res = await fetch(`/${type}?key=${key}&auth={{admin_pass}}`, { method: "POST" });
        const data = await res.json();
        alert(data.message || JSON.stringify(data));
        location.reload();
      }

      async function extendLicense(key) {
        const days = prompt("Enter number of days to extend:");
        if (!days) return;
        const res = await fetch(`/extend?key=${key}&days=${days}&auth={{admin_pass}}`, { method: "POST" });
        const data = await res.json();
        alert(data.message || JSON.stringify(data));
        location.reload();
      }

      document.getElementById("createForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const user = document.getElementById("username").value;
        const days = document.getElementById("days").value;
        const url = `/generate?user=${user}&days=${days}&auth={{admin_pass}}`;
        const res = await fetch(url, { method: "POST" });
        const data = await res.json();
        alert("✅ New License Created: " + data.key);
        location.reload();
      });
      </script>
    </body>
    </html>
    """

    return render_template_string(
        html,
        licenses=licenses,
        admin_pass=ADMIN_PASSWORD,
        datetime=datetime
    )



# ==========================
# 🚀 START SERVER
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

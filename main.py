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
@app.route("/generate", methods=["POST"])
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

# 🔍 Plugin verification
@app.route("/verify", methods=["GET"])
def verify_license():
    key = request.args.get("key")
    user_id = request.args.get("user_id")  # Unique server/player ID

    if not key or key not in licenses:
        return jsonify({"valid": False, "reason": "invalid_key"}), 404

    info = licenses[key]
    expires = datetime.strptime(info["expires"], "%Y-%m-%d")
    now = datetime.now()

    # Expiration check
    if now > expires:
        return jsonify({
            "valid": False,
            "user": info["user"],
            "reason": "expired",
            "expired_on": info["expires"]
        })

    # Binding check
    bound_to = info.get("bound_to")
    if not bound_to:
        # Bind to first user who uses it
        info["bound_to"] = user_id
        save_licenses()
        return jsonify({
            "valid": True,
            "user": info["user"],
            "expires": info["expires"],
            "bound_to": user_id,
            "note": "License successfully bound to this user."
        })

    # Already bound → must match
    if bound_to != user_id:
        return jsonify({
            "valid": False,
            "reason": "license_already_in_use",
            "bound_to": bound_to
        })

    return jsonify({
        "valid": True,
        "user": info["user"],
        "expires": info["expires"],
        "bound_to": bound_to
    })

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
#         location.reload();
#       }
#       </script>
#     </body>
#     </html>
#     """
#     return render_template_string(html, licenses=licenses, admin_pass=ADMIN_PASSWORD)
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
        body { font-family: Arial; background: #f5f6fa; margin: 40px; color: #2f3640; }
        h1 { color: #192a56; }
        table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background: #718093; color: white; }
        tr:nth-child(even) { background: #f1f2f6; }
        button { padding: 6px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .delete { background: #e84118; color: white; }
        .expire { background: #f39c12; color: white; }
        .unbind { background: #0097e6; color: white; }
        .generate { background: #44bd32; color: white; padding: 8px 15px; }
        input { padding: 6px; margin-right: 5px; border-radius: 4px; border: 1px solid #ccc; }
        form { margin-bottom: 20px; }
      </style>
    </head>
    <body>
      <h1>🔐 License Manager Dashboard</h1>
      <p>Welcome, Admin!</p>

      <form id="createForm">
        <input type="text" id="username" placeholder="User name" required>
        <input type="number" id="days" placeholder="Days" value="30" required>
        <button type="submit" class="generate">➕ Create License</button>
      </form>

      <table>
        <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound To</th><th>Actions</th></tr>
        {% for k, v in licenses.items() %}
        <tr>
          <td>{{ k }}</td>
          <td>{{ v['user'] }}</td>
          <td>{{ v['expires'] }}</td>
          <td>{{ v.get('bound_to', '-') }}</td>
          <td>
            <button class="unbind" onclick="action('unbind', '{{k}}')">Unbind</button>
            <button class="expire" onclick="action('expire', '{{k}}')">Expire</button>
            <button class="delete" onclick="action('delete', '{{k}}')">Delete</button>
          </td>
        </tr>
        {% endfor %}
      </table>

      <script>
      async function action(type, key) {
        const url = `/${type}?key=${key}&auth={{admin_pass}}`;
        const res = await fetch(url, { method: "POST" });
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

    return render_template_string(html, licenses=licenses, admin_pass=ADMIN_PASSWORD)



# ==========================
# 🚀 START SERVER
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

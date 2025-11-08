from flask import Flask, request, jsonify, render_template_string
import json, os, random, string
from datetime import datetime, timedelta

app = Flask(__name__)

# ==========================
# ⚙️ CONFIGURATION
# ==========================
DATA_FILE = "licenses.json"
ADMIN_PASSWORD = "MySecret123"  # change this to your secret
DEFAULT_EXPIRY_DAYS = 30

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

# 🔍 Verify license
@app.route("/verify", methods=["GET"])
def verify_license():
    key = request.args.get("key")
    user_id = request.args.get("user_id")

    if not key or key not in licenses:
        return jsonify({"valid": False, "reason": "invalid_key"}), 404

    info = licenses[key]
    expires = datetime.strptime(info["expires"], "%Y-%m-%d")
    now = datetime.now()

    # Expired
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

    # Not bound or not in use → bind
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

    # Bound to another server → check timeout
    if bound_to != user_id and in_use:
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

    # Same server → refresh heartbeat
    info["in_use"] = True
    info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
    save_licenses()
    return jsonify({
        "valid": True,
        "user": info["user"],
        "expires": info["expires"],
        "bound_to": bound_to
    })

# 🔑 Generate license (auto or custom)
@app.route("/generate", methods=["POST", "GET"])
def generate_license():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    user = request.args.get("user", "unknown")
    days = request.args.get("days", DEFAULT_EXPIRY_DAYS)
    custom_key = request.args.get("key")

    try:
        days = int(days)
    except:
        days = DEFAULT_EXPIRY_DAYS

    if custom_key and len(custom_key.strip()) >= 6:
        key = custom_key.strip().upper()
        if key in licenses:
            return jsonify({"success": False, "error": "Key already exists"}), 400
    else:
        key = generate_key()

    expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    licenses[key] = {
        "user": user,
        "expires": expires,
        "in_use": False,
        "bound_to": None,
        "last_check": None
    }
    save_licenses()
    return jsonify({"success": True, "key": key, "user": user, "expires": expires})

# 🔄 Extend license
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
        return jsonify({"success": False, "error": "Invalid days"}), 400

    exp = datetime.strptime(licenses[key]["expires"], "%Y-%m-%d") + timedelta(days=days)
    licenses[key]["expires"] = exp.strftime("%Y-%m-%d")
    save_licenses()
    return jsonify({"success": True, "message": f"✅ Extended to {licenses[key]['expires']}"})

# ✏️ Edit license
@app.route("/edit", methods=["POST"])
def edit_license():
    auth = request.args.get("auth")
    key = request.args.get("key")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    if key not in licenses:
        return jsonify({"success": False, "error": "License not found"}), 404

    new_user = request.args.get("user")
    new_key = request.args.get("new_key")
    new_days = request.args.get("days")

    info = licenses[key]

    if new_user:
        info["user"] = new_user

    if new_days:
        try:
            new_days = int(new_days)
            new_exp = datetime.now() + timedelta(days=new_days)
            info["expires"] = new_exp.strftime("%Y-%m-%d")
        except:
            return jsonify({"success": False, "error": "Invalid days"}), 400

    if new_key and new_key.strip().upper() != key:
        new_key = new_key.strip().upper()
        if new_key in licenses:
            return jsonify({"success": False, "error": "New key already exists"}), 400
        licenses[new_key] = info
        del licenses[key]
        save_licenses()
        return jsonify({"success": True, "message": f"✅ License key changed to {new_key}!"})

    save_licenses()
    return jsonify({"success": True, "message": "✅ License updated successfully!"})

# 🧹 Unbind license
@app.route("/unbind", methods=["POST"])
def unbind_license():
    auth = request.args.get("auth")
    key = request.args.get("key")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    if key not in licenses:
        return jsonify({"success": False, "error": "Not found"}), 404

    licenses[key]["bound_to"] = None
    licenses[key]["in_use"] = False
    save_licenses()
    return jsonify({"success": True, "message": "✅ License unbound."})

# ⛔ Expire now
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
    return jsonify({"success": True, "message": f"✅ License {key} expired now."})

# 🗑️ Delete license
@app.route("/delete", methods=["POST"])
def delete_license():
    auth = request.args.get("auth")
    key = request.args.get("key")

    if auth != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    if key not in licenses:
        return jsonify({"success": False, "error": "Not found"}), 404

    del licenses[key]
    save_licenses()
    return jsonify({"success": True, "message": f"🗑️ Deleted {key} successfully."})

# 💾 Backup
@app.route("/backup", methods=["GET"])
def backup():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 403

    with open(DATA_FILE, "rb") as f:
        return f.read(), 200, {
            "Content-Type": "application/json",
            "Content-Disposition": "attachment; filename=licenses_backup.json"
        }

# ==========================
# 🧭 ADMIN DASHBOARD
# ==========================
@app.route("/admin")
def admin_dashboard():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return "<h2>❌ Unauthorized</h2><p>Missing or incorrect ?auth= password in URL.</p>", 403

    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>License Manager Dashboard</title>
      <style>
        body { font-family: Arial, sans-serif; background: #f5f6fa; margin: 40px; color: #2f3640; }
        h1 { color: #192a56; }
        table { border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background: #718093; color: white; }
        tr.expired { background: #ff7675; color: white; }
        tr.warning { background: #fbc531; color: black; }
        tr.active { background: #44bd32; color: white; }
        tr.unbound { background: #dcdde1; color: #2f3640; }
        button { padding: 6px 10px; margin: 2px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .delete { background: #e84118; color: white; }
        .expire { background: #f39c12; color: white; }
        .extend { background: #44bd32; color: white; }
        .unbind { background: #0097e6; color: white; }
        .download { background: #8c7ae6; color: white; padding: 8px 15px; }
        input { padding: 6px; border-radius: 4px; border: 1px solid #ccc; margin-right: 5px; }
        #searchBox { width: 40%; padding: 8px; margin: 10px 0; border-radius: 8px; border: 1px solid #ccc; font-size: 14px; }
      </style>
      <script>
        const ADMIN_PASS = "{{ admin_pass }}";
      </script>
    </head>
    <body>
      <h1>🔐 License Manager Dashboard</h1>
      <form id="createForm">
        <input id="username" placeholder="User" required>
        <input id="days" type="number" value="30" required>
        <input id="customKey" placeholder="(Optional custom key)">
        <button class="extend" type="submit">➕ Create</button>
        <button type="button" class="download" onclick="window.location='/backup?auth='+ADMIN_PASS">💾 Backup</button>
        <button type="button" class="unbind" onclick="location.reload()">🔄 Refresh</button>
      </form>

      <input id="searchBox" placeholder="🔍 Search...">

      <table id="licenseTable">
        <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound</th><th>Status</th><th>Last Check</th><th>Actions</th></tr>
        {% for k,v in licenses.items() %}
          {% set exp = v['expires'] %}
          {% set bound = v.get('bound_to','-') %}
          {% set last = v.get('last_check') if v.get('last_check') else '-' %}
          {% set days_left = (datetime.strptime(exp, '%Y-%m-%d') - datetime.now()).days %}
          {% if days_left < 0 %}
            {% set cls = 'expired' %}
          {% elif days_left <= 7 %}
            {% set cls = 'warning' %}
          {% elif bound == '-' %}
            {% set cls = 'unbound' %}
          {% else %}
            {% set cls = 'active' %}
          {% endif %}
          {% if last == '-' %}
            {% set hb = '⚫ Inactive' %}
          {% else %}
            {% set diff = (datetime.now() - datetime.strptime(last, '%Y-%m-%d %H:%M:%S')).total_seconds() %}
            {% if diff <= 5 %}
              {% set hb = '🟢 Active' %}
            {% elif diff <= 10 %}
              {% set hb = '🟡 Slow' %}
            {% else %}
              {% set hb = '⚫ Inactive' %}
            {% endif %}
          {% endif %}
          <tr class="{{ cls }}">
            <td>{{ k }}</td><td>{{ v['user'] }}</td><td>{{ v['expires'] }}</td><td>{{ bound }}</td><td>{{ hb }}</td><td>{{ last }}</td>
            <td>
              <button class="extend" onclick="extendLicense('{{k}}')">Extend</button>
              <button class="unbind" onclick="editLicense('{{k}}')">✏️ Edit</button>
              <button class="expire" onclick="action('expire','{{k}}')">Expire</button>
              <button class="unbind" onclick="action('unbind','{{k}}')">Unbind</button>
              <button class="delete" onclick="action('delete','{{k}}')">Delete</button>
            </td>
          </tr>
        {% endfor %}
      </table>

      <!-- ✏️ Edit Modal -->
      <div id="editModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); justify-content:center; align-items:center; z-index:1000;">
        <div style="background:white; padding:20px; border-radius:8px; width:400px; box-shadow:0 4px 16px rgba(0,0,0,0.2);">
          <h2>✏️ Edit License</h2>
          <form id="editForm">
            <label>License Key:</label><br>
            <input id="editKey" type="text" readonly style="width:100%; margin-bottom:10px;"><br>
            <label>New Key (optional rename):</label><br>
            <input id="editNewKey" type="text" style="width:100%; margin-bottom:10px;"><br>
            <label>User:</label><br>
            <input id="editUser" type="text" style="width:100%; margin-bottom:10px;"><br>
            <label>Days (from today):</label><br>
            <input id="editDays" type="number" style="width:100%; margin-bottom:10px;"><br>
            <button type="submit" style="background:#44bd32;color:white;padding:6px 12px;border:none;border-radius:4px;">💾 Save Changes</button>
            <button type="button" onclick="closeModal()" style="background:#e84118;color:white;padding:6px 12px;border:none;border-radius:4px;margin-left:8px;">✖ Close</button>
          </form>
        </div>
      </div>

      <script>
        let currentEditKey = "";
        function editLicense(key) {
          currentEditKey = key;
          const row = Array.from(document.querySelectorAll("#licenseTable tr")).find(r => r.innerText.includes(key));
          const cells = row ? row.querySelectorAll("td") : [];
          document.getElementById("editKey").value = key;
          document.getElementById("editUser").value = cells[1]?.innerText || "";
          document.getElementById("editNewKey").value = "";
          document.getElementById("editDays").value = "";
          document.getElementById("editModal").style.display = "flex";
        }
        function closeModal() {
          document.getElementById("editModal").style.display = "none";
        }

        document.getElementById("editForm").addEventListener("submit", async function(e){
          e.preventDefault();
          const u = document.getElementById("editUser").value;
          const d = document.getElementById("editDays").value;
          const n = document.getElementById("editNewKey").value;
          let url = `/edit?key=${currentEditKey}&auth=${ADMIN_PASS}`;
          if(u) url += `&user=${encodeURIComponent(u)}`;
          if(d) url += `&days=${encodeURIComponent(d)}`;
          if(n) url += `&new_key=${encodeURIComponent(n)}`;
          const res = await fetch(url, { method: 'POST' });
          const j = await res.json();
          alert(j.message || JSON.stringify(j));
          closeModal();
          location.reload();
        });

        async function action(type, key) {
          const res = await fetch(`/${type}?key=${key}&auth=${ADMIN_PASS}`, { method: 'POST' });
          const j = await res.json();
          alert(j.message || JSON.stringify(j));
          location.reload();
        }

        async function extendLicense(key) {
          const d = prompt("Enter number of days to extend:");
          if(!d) return;
          const res = await fetch(`/extend?key=${key}&days=${d}&auth=${ADMIN_PASS}`, { method: 'POST' });
          const j = await res.json();
          alert(j.message || JSON.stringify(j));
          location.reload();
        }

        document.getElementById("createForm").addEventListener("submit", async function(e){
          e.preventDefault();
          const u = document.getElementById("username").value;
          const d = document.getElementById("days").value;
          const c = document.getElementById("customKey").value;
          let url = `/generate?user=${encodeURIComponent(u)}&days=${encodeURIComponent(d)}&auth=${ADMIN_PASS}`;
          if(c) url += `&key=${encodeURIComponent(c)}`;
          const res = await fetch(url, { method: 'POST' });
          const j = await res.json();
          alert(j.success ? ("✅ Created: " + j.key) : ("❌ " + j.error));
          location.reload();
        });

        document.getElementById("searchBox").addEventListener("keyup", function(){
          const f = this.value.toLowerCase();
          document.querySelectorAll("#licenseTable tr").forEach((r,i) => {
            if(i === 0) return;
            const txt = r.innerText.toLowerCase();
            r.style.display = txt.includes(f) ? "" : "none";
          });
        });
      </script>

    </body>
    </html>
    """
    return render_template_string(html, licenses=licenses, admin_pass=ADMIN_PASSWORD, datetime=datetime)

# 🚀 RUN SERVER
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

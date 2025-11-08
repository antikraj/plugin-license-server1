from flask import Flask, request, jsonify, render_template_string
import json, os, random, string
from datetime import datetime, timedelta

app = Flask(__name__)

# ==========================
# ⚙️ CONFIGURATION
# ==========================
DATA_FILE = "licenses.json"
ADMIN_PASSWORD = "MySecret123"
DEFAULT_EXPIRY_DAYS = 30
HEARTBEAT_TIMEOUT = 10  # seconds before freeing license if no check

# ==========================
# 🧾 DATA HANDLING
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
# 🔍 LICENSE VERIFY
# ==========================
@app.route("/verify", methods=["GET"])
def verify_license():
    key = request.args.get("key")
    user_id = request.args.get("user_id")
    if not key or key not in licenses:
        return jsonify({"valid": False, "reason": "invalid_key"}), 404

    info = licenses[key]
    now = datetime.now()
    expires = datetime.strptime(info["expires"], "%Y-%m-%d")

    # expired license
    if now > expires:
        return jsonify({"valid": False, "reason": "expired", "user": info["user"]})

    bound_to = info.get("bound_to")
    last_check = info.get("last_check")
    in_use = info.get("in_use", False)

    # free if no heartbeat within timeout
    if bound_to and last_check:
        last_dt = datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S")
        if (now - last_dt).total_seconds() > HEARTBEAT_TIMEOUT:
            info["in_use"] = False
            info["bound_to"] = None
            info["last_check"] = None
            save_licenses()

    # not in use → claim it
    if not info.get("in_use") or not info.get("bound_to"):
        info["bound_to"] = user_id
        info["in_use"] = True
        info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_licenses()
        return jsonify({"valid": True, "note": "License activated", "bound_to": user_id})

    # same user → update heartbeat
    if bound_to == user_id:
        info["last_check"] = now.strftime("%Y-%m-%d %H:%M:%S")
        save_licenses()
        return jsonify({"valid": True, "note": "Heartbeat refreshed"})

    # in use elsewhere
    return jsonify({"valid": False, "reason": "license_in_use", "bound_to": bound_to})

# ==========================
# 🔑 GENERATE / ADMIN ROUTES
# ==========================
@app.route("/generate", methods=["POST", "GET"])
def generate_license():
    if request.args.get("auth") != ADMIN_PASSWORD:
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
    licenses[key] = {"user": user, "expires": expires, "in_use": False, "bound_to": None, "last_check": None}
    save_licenses()
    return jsonify({"success": True, "key": key, "user": user, "expires": expires})

@app.route("/extend", methods=["POST"])
def extend_license():
    if request.args.get("auth") != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    key = request.args.get("key")
    days = request.args.get("days")
    if key not in licenses:
        return jsonify({"success": False, "error": "Not found"}), 404
    try:
        days = int(days)
    except:
        return jsonify({"success": False, "error": "Invalid days"}), 400
    exp = datetime.strptime(licenses[key]["expires"], "%Y-%m-%d") + timedelta(days=days)
    licenses[key]["expires"] = exp.strftime("%Y-%m-%d")
    save_licenses()
    return jsonify({"success": True, "message": f"Extended to {licenses[key]['expires']}"})

@app.route("/expire", methods=["POST"])
def expire_license():
    if request.args.get("auth") != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    key = request.args.get("key")
    if key not in licenses:
        return jsonify({"success": False, "error": "Not found"}), 404
    licenses[key]["expires"] = datetime.now().strftime("%Y-%m-%d")
    save_licenses()
    return jsonify({"success": True, "message": "Expired now"})

@app.route("/unbind", methods=["POST"])
def unbind_license():
    if request.args.get("auth") != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    key = request.args.get("key")
    if key not in licenses:
        return jsonify({"success": False, "error": "Not found"}), 404
    licenses[key]["bound_to"] = None
    licenses[key]["in_use"] = False
    licenses[key]["last_check"] = None
    save_licenses()
    return jsonify({"success": True, "message": "Unbound successfully"})

@app.route("/delete", methods=["POST"])
def delete_license():
    if request.args.get("auth") != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    key = request.args.get("key")
    if key not in licenses:
        return jsonify({"success": False, "error": "Not found"}), 404
    del licenses[key]
    save_licenses()
    return jsonify({"success": True, "message": f"Deleted {key}"})

@app.route("/backup")
def backup():
    if request.args.get("auth") != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 403
    with open(DATA_FILE, "rb") as f:
        return f.read(), 200, {"Content-Type": "application/json",
                               "Content-Disposition": "attachment; filename=licenses_backup.json"}

# ==========================
# 🌐 ADMIN DASHBOARD
# ==========================
@app.route("/admin")
def admin_dashboard():
    auth = request.args.get("auth")
    if auth != ADMIN_PASSWORD:
        return "<h2>❌ Unauthorized</h2><p>Use ?auth=MySecret123 in URL.</p>", 403

    html = """
    <!DOCTYPE html>
    <html><head>
    <title>License Dashboard</title>
    <style>
      body { font-family: Arial; background:#f5f6fa; margin:40px; color:#2f3640; }
      h1 { color:#192a56; }
      table { border-collapse:collapse; width:100%; background:#fff; box-shadow:0 2px 8px rgba(0,0,0,0.1); }
      th,td { border:1px solid #ccc; padding:8px; text-align:left; }
      th { background:#718093; color:white; }
      tr.expired{background:#ff7675;color:white;}
      tr.warning{background:#fbc531;color:black;}
      tr.active{background:#44bd32;color:white;}
      tr.unbound{background:#dcdde1;color:#2f3640;}
      button{padding:6px 10px; margin:2px; border:none; border-radius:4px; cursor:pointer; font-weight:bold;}
      .delete{background:#e84118;color:white;}
      .expire{background:#f39c12;color:white;}
      .extend{background:#44bd32;color:white;}
      .unbind{background:#0097e6;color:white;}
      .download{background:#8c7ae6;color:white;padding:8px 15px;}
      input{padding:6px;border-radius:4px;border:1px solid #ccc;margin-right:5px;}
      #searchBox{width:40%;padding:8px;margin:10px 0;border-radius:8px;border:1px solid #ccc;font-size:14px;}
    </style>
    <script>
      const urlParams=new URLSearchParams(window.location.search);
      const ADMIN_PASS=urlParams.get("auth");
      async function action(t,k){const r=await fetch(`/${t}?key=${k}&auth=${ADMIN_PASS}`,{method:"POST"});const j=await r.json();alert(j.message||JSON.stringify(j));location.reload();}
      async function extendLicense(k){const d=prompt("Days to extend:");if(!d)return;const r=await fetch(`/extend?key=${k}&days=${d}&auth=${ADMIN_PASS}`,{method:"POST"});const j=await r.json();alert(j.message||JSON.stringify(j));location.reload();}
      async function createLicense(e){e.preventDefault();const u=document.getElementById("username").value;const d=document.getElementById("days").value;const c=document.getElementById("customKey").value;let url=`/generate?user=${u}&days=${d}&auth=${ADMIN_PASS}`;if(c)url+=`&key=${encodeURIComponent(c)}`;const r=await fetch(url,{method:"POST"});const j=await r.json();alert(j.success?"✅ Created: "+j.key:"❌ "+j.error);location.reload();}
      function search(){const f=document.getElementById("searchBox").value.toLowerCase();document.querySelectorAll("#licenseTable tr").forEach((r,i)=>{if(i===0)return;r.style.display=r.innerText.toLowerCase().includes(f)?'':'none';});}
    </script>
    </head><body>
      <h1>🔐 License Manager Dashboard</h1>
      <form onsubmit="createLicense(event)">
        <input id="username" placeholder="User" required>
        <input id="days" type="number" value="30" required>
        <input id="customKey" placeholder="(Optional custom key)">
        <button class="extend" type="submit">➕ Create</button>
        <button type="button" class="download" onclick="window.location='/backup?auth='+ADMIN_PASS">💾 Backup</button>
      </form>
      <input id="searchBox" onkeyup="search()" placeholder="🔍 Search...">
      <table id="licenseTable">
      <tr><th>Key</th><th>User</th><th>Expires</th><th>Bound</th><th>Status</th><th>Last Check</th><th>Actions</th></tr>
      {% for k,v in licenses.items() %}
        {% set exp=v['expires'] %}
        {% set bound=v.get('bound_to','-') %}
        {% set last=v.get('last_check') if v.get('last_check') else '-' %}
        {% set cls='active' %}
        {% set days_left=(datetime.strptime(exp,'%Y-%m-%d')-datetime.now()).days %}
        {% if days_left<0 %}{% set cls='expired' %}
        {% elif days_left<=7 %}{% set cls='warning' %}
        {% elif not bound or bound=='-' %}{% set cls='unbound' %}{% endif %}
        {% set hb='⚫ Inactive' %}
        {% if last!='-' %}
          {% set diff=(datetime.now()-datetime.strptime(last,'%Y-%m-%d %H:%M:%S')).total_seconds() %}
          {% if diff<=5 %}{% set hb='🟢 Active' %}
          {% elif diff<=10 %}{% set hb='🟡 Slow' %}{% endif %}
        {% endif %}
        <tr class="{{cls}}"><td>{{k}}</td><td>{{v['user']}}</td><td>{{v['expires']}}</td>
        <td>{{bound}}</td><td>{{hb}}</td><td>{{last}}</td>
        <td><button class="extend" onclick="extendLicense('{{k}}')">Extend</button>
        <button class="expire" onclick="action('expire','{{k}}')">Expire</button>
        <button class="unbind" onclick="action('unbind','{{k}}')">Unbind</button>
        <button class="delete" onclick="action('delete','{{k}}')">Delete</button></td></tr>
      {% endfor %}
      </table>
    </body></html>
    """
    return render_template_string(html, licenses=licenses, datetime=datetime)

# ==========================
# 🚀 RUN SERVER
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

from flask import Flask, request, jsonify
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

# ==========================
# 🚀 START SERVER
# ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

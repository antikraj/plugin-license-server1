from flask import Flask, request, jsonify
import json, os, random, string

app = Flask(__name__)

DATA_FILE = "licenses.json"

# Load saved licenses from file
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

@app.route("/generate", methods=["POST"])
def generate_license():
    user = request.args.get("user", "unknown")
    key = generate_key()
    licenses[key] = {"user": user}
    save_licenses()
    return jsonify({"success": True, "key": key})

@app.route("/verify", methods=["GET"])
def verify_license():
    key = request.args.get("key")
    if key in licenses:
        return jsonify({"valid": True, "user": licenses[key]["user"]})
    else:
        return jsonify({"valid": False})

@app.route("/")
def home():
    return "✅ License API running successfully!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

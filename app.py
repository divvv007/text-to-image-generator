from flask import Flask, render_template, request, redirect, url_for, session
import requests, os, uuid, sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

API_KEY = "12670e7c1c200670d0c1e97730bf37df8870b84a28462b87c5dd544f7d0a56a1152cd08a3233cc47eb6d2692bcc01be8"
API_URL = "https://clipdrop-api.co/text-to-image/v1"

IMAGE_FOLDER = "static/images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

USERS = {"admin": "1234"}  # demo users

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("database.db", check_same_thread=False)

db = get_db()
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT,
    prompt TEXT,
    enhanced_prompt TEXT,
    style TEXT,
    image_path TEXT,
    liked INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
db.commit()

# ---------------- PROMPT ENHANCER ----------------
def enhance_prompt(prompt, style):
    base = "high quality, ultra detailed, professional lighting"
    style_map = {
        "realistic": "photorealistic, 8k, DSLR",
        "anime": "anime style, vibrant colors, studio ghibli",
        "sketch": "pencil sketch, black and white, hand drawn"
    }
    return f"{prompt}, {base}, {style_map.get(style, '')}"

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")

        if user in USERS and USERS[user] == pwd:
            session["user"] = user
            return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ---------------- MAIN PAGE ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user" not in session:
        return redirect(url_for("login"))

    images = []

    if request.method == "POST":
        prompt = request.form.get("prompt")
        style = request.form.get("style")
        count = request.form.get("count")

        if not prompt or not style or not count:
            return render_template("index.html", images=[], user=session["user"])

        count = int(count)
        enhanced = enhance_prompt(prompt, style)

        for _ in range(count):
            img_name = f"{uuid.uuid4().hex}.png"
            path = os.path.join(IMAGE_FOLDER, img_name)

            r = requests.post(
                API_URL,
                headers={"x-api-key": API_KEY},
                files={"prompt": (None, enhanced)}
            )

            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)

                cursor.execute("""
                INSERT INTO images (user, prompt, enhanced_prompt, style, image_path)
                VALUES (?, ?, ?, ?, ?)
                """, (session["user"], prompt, enhanced, style, img_name))
                db.commit()

                images.append(img_name)

    return render_template("index.html", images=images, user=session["user"])

# ---------------- LIKE IMAGE ----------------
@app.route("/like/<img>")
def like_image(img):
    if "user" not in session:
        return redirect("/login")

    cursor.execute("""
    UPDATE images
    SET liked = CASE WHEN liked = 1 THEN 0 ELSE 1 END
    WHERE image_path=? AND user=?
    """, (img, session["user"]))
    db.commit()

    return redirect(request.referrer or "/")

# ---------------- DELETE IMAGE ----------------
@app.route("/delete/<img>")
def delete_image(img):
    if "user" not in session:
        return redirect("/login")

    img_path = os.path.join(IMAGE_FOLDER, img)

    if os.path.exists(img_path):
        os.remove(img_path)

    cursor.execute("""
    DELETE FROM images
    WHERE image_path=? AND user=?
    """, (img, session["user"]))
    db.commit()

    return redirect(request.referrer or "/")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    cursor.execute("""
    SELECT prompt, style, image_path, created_at, liked
    FROM images
    WHERE user=?
    ORDER BY created_at DESC
    """, (session["user"],))

    data = cursor.fetchall()
    return render_template("dashboard.html", images=data)

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form.get("username")
        pwd = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if pwd != confirm:
            return render_template("register.html", error="Passwords do not match")

        if user in USERS:
            return render_template("register.html", error="User already exists")

        USERS[user] = pwd   # demo storage (later move to DB)
        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)

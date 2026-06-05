import os
import uuid
import sqlite3
import base64
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect,
    url_for, send_file, jsonify, abort, flash, make_response
)
from datetime import datetime
try:
    import requests as http_requests
    HTTP_OK = True
except ImportError:
    HTTP_OK = False

# ── WeasyPrint optionnel (non dispo sur Vercel) ──────────────────────────────
try:
    from weasyprint import HTML as WeasyHTML
    WEASYPRINT_OK = True
except Exception:
    WEASYPRINT_OK = False

# ── Chemins ──────────────────────────────────────────────────────────────────
# BASE_DIR = dossier où se trouve app.py (racine du projet)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IS_VERCEL = bool(os.environ.get("VERCEL"))

if IS_VERCEL:
    PDF_DIR    = "/tmp/pdf"
    UPLOAD_DIR = "/tmp/uploads"
    DB_PATH    = "/tmp/database.db"
else:
    PDF_DIR    = os.path.join(BASE_DIR, "pdf")
    UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
    DB_PATH    = os.path.join(BASE_DIR, "database.db")

for d in [PDF_DIR, UPLOAD_DIR]:
    os.makedirs(d, exist_ok=True)

# ── Flask — chemins explicites vers templates/ et static/ ───────────────────
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "cv_saas_secret_2024")

ADMIN_PASSWORD  = os.environ.get("ADMIN_PASSWORD", "JESUS")
LEEKPAY_SK      = os.environ.get("LEEKPAY_SK", "")   # Clé secrète LeekPay (sk_live_...)
LEEKPAY_PK      = os.environ.get("LEEKPAY_PK", "pk_live_yXrH97aZ0APcEsQCMAtBJEWPPf1JLYlV")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

TEMPLATE_PRICES_FCFA = {
    "simple": 1000,
    "professionnel": 1500,
    "premium": 3000,
}


# ── Contexte global Jinja ────────────────────────────────────────────────────
@app.context_processor
def inject_globals():
    return {"TEMPLATE_PRICES_FCFA": TEMPLATE_PRICES_FCFA}


# ── Base de données ──────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cv_clients (
                id          TEXT PRIMARY KEY,
                nom         TEXT,
                email       TEXT,
                telephone   TEXT,
                ville       TEXT,
                pays        TEXT,
                poste       TEXT,
                objectif    TEXT,
                formation   TEXT,
                experience  TEXT,
                competences TEXT,
                langues     TEXT,
                template    TEXT DEFAULT 'simple',
                photo_path  TEXT,
                paid        INTEGER DEFAULT 0,
                created_at  TEXT,
                notes_admin TEXT DEFAULT ''
            )
        """)
        conn.commit()


init_db()


# ── Utilitaires ──────────────────────────────────────────────────────────────
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_id():
    return uuid.uuid4().hex[:10]


def photo_to_base64(photo_path):
    """Encode la photo en data URI base64 (fonctionne en HTML et PDF)."""
    if not photo_path:
        return None
    # Chemin absolu selon l'environnement
    if IS_VERCEL or os.path.isabs(photo_path):
        full_path = photo_path
    else:
        full_path = os.path.join(BASE_DIR, photo_path)
    if not os.path.exists(full_path):
        return None
    try:
        with open(full_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext  = photo_path.rsplit(".", 1)[1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        return f"data:{mime};base64,{data}"
    except Exception as e:
        print(f"Erreur encodage photo : {e}")
        return None


def improve_text(text):
    if not text:
        return text
    text = text.strip()
    if text and not text[0].isupper():
        text = text[0].upper() + text[1:]
    return text


def parse_list_field(text):
    if not text:
        return []
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip().lstrip("-•·*").strip()
        if line:
            lines.append(line)
    return lines


def get_client(client_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM cv_clients WHERE id = ?", (client_id,)
        ).fetchone()
    return dict(row) if row else None


def prepare_cv_data(data):
    photo_b64 = photo_to_base64(data.get("photo_path", ""))
    return {
        "id":          data.get("id", ""),
        "nom":         improve_text(data.get("nom", "")),
        "email":       data.get("email", ""),
        "telephone":   data.get("telephone", ""),
        "ville":       improve_text(data.get("ville", "")),
        "pays":        improve_text(data.get("pays", "")),
        "poste":       improve_text(data.get("poste", "")),
        "objectif":    improve_text(data.get("objectif", "")),
        "formation":   parse_list_field(data.get("formation", "")),
        "experience":  parse_list_field(data.get("experience", "")),
        "competences": parse_list_field(data.get("competences", "")),
        "langues":     parse_list_field(data.get("langues", "")),
        "template":    data.get("template", "simple"),
        "paid":        data.get("paid", 0),
        "created_at":  data.get("created_at", ""),
        "photo_base64": photo_b64,
        "photo_path":  data.get("photo_path", ""),
    }


# ── Génération PDF ───────────────────────────────────────────────────────────
def generate_pdf(client_id):
    if not WEASYPRINT_OK:
        print("WeasyPrint non disponible.")
        return False
    client = get_client(client_id)
    if not client:
        return False
    data     = prepare_cv_data(client)
    tpl_name = f"cv_{data['template']}.html"
    with app.app_context():
        html_content = render_template(tpl_name, cv=data, preview_mode=False)
    pdf_path = os.path.join(PDF_DIR, f"{client_id}.pdf")
    base_url = Path(BASE_DIR).resolve().as_uri() + "/"
    try:
        WeasyHTML(
            string=html_content,
            base_url=base_url,
            media_type="print"
        ).write_pdf(pdf_path)
        return True
    except Exception as e:
        print(f"Erreur PDF : {e}")
        return False


# ── Helper admin ─────────────────────────────────────────────────────────────
def admin_required():
    return bool(request.cookies.get("admin_auth"))


# ── Routes principales ───────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        client_id   = generate_id()
        nom         = request.form.get("nom",         "").strip()
        email       = request.form.get("email",       "").strip()
        telephone   = request.form.get("telephone",   "").strip()
        ville       = request.form.get("ville",       "").strip()
        pays        = request.form.get("pays",        "").strip()
        poste       = request.form.get("poste",       "").strip()
        objectif    = request.form.get("objectif",    "").strip()
        formation   = request.form.get("formation",   "").strip()
        experience  = request.form.get("experience",  "").strip()
        competences = request.form.get("competences", "").strip()
        langues     = request.form.get("langues",     "").strip()
        template    = request.form.get("template",    "simple")

        if not nom or not email:
            flash("Nom et email sont obligatoires.", "error")
            return render_template("index.html")

        # Upload photo
        photo_path = ""
        if "photo" in request.files:
            photo = request.files["photo"]
            if photo and photo.filename and allowed_file(photo.filename):
                ext       = photo.filename.rsplit(".", 1)[1].lower()
                filename  = f"{client_id}.{ext}"
                save_path = os.path.join(UPLOAD_DIR, filename)
                photo.save(save_path)
                # Stocker le chemin relatif (local) ou absolu (Vercel)
                photo_path = save_path if IS_VERCEL else f"static/uploads/{filename}"

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db() as conn:
            conn.execute("""
                INSERT INTO cv_clients
                  (id, nom, email, telephone, ville, pays, poste, objectif,
                   formation, experience, competences, langues,
                   template, photo_path, paid, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)
            """, (
                client_id, nom, email, telephone, ville, pays,
                poste, objectif, formation, experience,
                competences, langues, template, photo_path, created_at
            ))
            conn.commit()

        try:
            generate_pdf(client_id)
        except Exception as e:
            print(f"PDF non généré : {e}")

        return redirect(url_for("success", client_id=client_id))

    return render_template("index.html")


@app.route("/success/<client_id>")
def success(client_id):
    client = get_client(client_id)
    if not client:
        abort(404)
    return render_template("success.html", client=client)


@app.route("/preview/<client_id>")
def preview(client_id):
    client = get_client(client_id)
    if not client:
        abort(404)
    data         = prepare_cv_data(client)
    tpl_name     = f"cv_{data['template']}.html"
    # preview_mode=True = watermark + blocage impression si non payé
    preview_mode = not bool(int(client.get("paid", 0)))
    return render_template(tpl_name, cv=data, preview_mode=preview_mode)


@app.route("/download/<client_id>")
def download(client_id):
    client = get_client(client_id)
    if not client:
        abort(404)
    # STRICT : bloquer tout accès si non payé — rediriger vers paiement
    if not int(client.get("paid", 0)):
        return redirect(url_for("success", client_id=client_id))
    # Payé uniquement → page téléchargement
    data = prepare_cv_data(client)
    return render_template("cv_download.html", cv=data)



# ── Création checkout LeekPay (serveur) ──────────────────────────────────────
@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    """
    Crée un checkout LeekPay côté serveur et retourne le checkout_id.
    Le client n'a plus besoin de connaître la clé secrète.
    """
    data = request.get_json(silent=True) or {}
    amount   = data.get("amount", 0)
    plan     = data.get("plan", "pro")
    ref      = data.get("reference", "")  # notre ref interne

    if not LEEKPAY_SK or not HTTP_OK:
        return jsonify({"error": "Service indisponible"}), 500

    SITE = os.environ.get("SITE_URL", "https://crea-cv-kappa.vercel.app")

    try:
        resp = http_requests.post(
            "https://leekpay.fr/api/v1/checkout",
            headers={
                "Authorization": f"Bearer {LEEKPAY_SK}",
                "Content-Type":  "application/json"
            },
            json={
                "amount":      int(amount),
                "currency":    "XOF",
                "description": f"CVCraft — CV {plan.capitalize()}",
                "return_url":  f"{SITE}?cv_paid=1&sk={ref}",
                "cancel_url":  f"{SITE}?cv_cancel=1",
                "metadata":    {"internal_ref": ref, "plan": plan}
            },
            timeout=10
        )
        result = resp.json()
        if resp.status_code in (200, 201) and result.get("success"):
            checkout = result["data"]
            return jsonify({
                "checkout_id":  checkout["id"],
                "payment_url":  checkout["payment_url"]
            })
        else:
            return jsonify({"error": result.get("message", "Erreur LeekPay")}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Vérification paiement LeekPay (serveur) ──────────────────────────────────
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    """
    Vérifie côté serveur si une transaction LeekPay est bien payée.
    Le client envoie sa référence, on interroge l'API LeekPay avec la clé secrète.
    """
    data = request.get_json(silent=True) or {}
    reference = data.get("reference", "").strip()

    if not reference:
        return jsonify({"paid": False, "error": "Référence manquante"}), 400

    # Si pas de clé secrète configurée → refuser systématiquement
    if not LEEKPAY_SK:
        return jsonify({"paid": False, "error": "Clé secrète LeekPay non configurée"}), 500

    if not HTTP_OK:
        return jsonify({"paid": False, "error": "Module requests manquant"}), 500

    try:
        # Appel API LeekPay : récupérer la transaction par référence
        resp = http_requests.get(
            f"https://api.leekpay.fr/v1/transactions",
            headers={
                "Authorization": f"Bearer {LEEKPAY_SK}",
                "Content-Type": "application/json"
            },
            params={"reference": reference},
            timeout=10
        )
        if resp.status_code != 200:
            return jsonify({"paid": False, "error": f"API LeekPay: {resp.status_code}"}), 502

        result = resp.json()

        # LeekPay retourne une liste ou un objet selon l'endpoint
        transactions = result.get("data") or result.get("transactions") or []
        if isinstance(transactions, dict):
            transactions = [transactions]

        # Chercher la transaction avec notre référence et statut "paid"
        for tx in transactions:
            ref = tx.get("reference") or tx.get("ref") or ""
            status = tx.get("status") or tx.get("state") or ""
            if ref == reference and status.lower() in ("paid", "success", "completed", "approved"):
                return jsonify({"paid": True, "transaction": tx})

        return jsonify({"paid": False, "status": "not_found_or_pending"})

    except Exception as e:
        return jsonify({"paid": False, "error": str(e)}), 500


# ── Routes Admin ─────────────────────────────────────────────────────────────
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password", "") == ADMIN_PASSWORD:
            resp = make_response(redirect(url_for("admin")))
            resp.set_cookie("admin_auth", "1", max_age=3600 * 8, httponly=True)
            return resp
        flash("Mot de passe incorrect.", "error")
        return render_template("admin_login.html")

    if not admin_required():
        return render_template("admin_login.html")

    search      = request.args.get("search", "").strip()
    filter_paid = request.args.get("paid", "all")
    with get_db() as conn:
        query  = "SELECT * FROM cv_clients WHERE 1=1"
        params = []
        if search:
            query  += " AND (nom LIKE ? OR email LIKE ? OR poste LIKE ?)"
            params += [f"%{search}%"] * 3
        if filter_paid == "paid":
            query += " AND paid = 1"
        elif filter_paid == "unpaid":
            query += " AND paid = 0"
        query  += " ORDER BY created_at DESC"
        clients = [dict(r) for r in conn.execute(query, params).fetchall()]

    return render_template("admin.html", clients=clients,
                           search=search, filter_paid=filter_paid)


@app.route("/admin/logout")
def admin_logout():
    resp = make_response(redirect(url_for("admin")))
    resp.delete_cookie("admin_auth")
    return resp


@app.route("/admin/validate/<client_id>", methods=["POST"])
def validate_payment(client_id):
    if not admin_required():
        abort(403)
    generate_pdf(client_id)
    with get_db() as conn:
        conn.execute("UPDATE cv_clients SET paid = 1 WHERE id = ?", (client_id,))
        conn.commit()
    return jsonify({"success": True, "message": "Paiement validé ✓"})


@app.route("/admin/unvalidate/<client_id>", methods=["POST"])
def unvalidate_payment(client_id):
    if not admin_required():
        abort(403)
    with get_db() as conn:
        conn.execute("UPDATE cv_clients SET paid = 0 WHERE id = ?", (client_id,))
        conn.commit()
    return jsonify({"success": True, "message": "Paiement annulé"})


@app.route("/admin/notes/<client_id>", methods=["POST"])
def save_notes(client_id):
    if not admin_required():
        abort(403)
    notes = request.json.get("notes", "")
    with get_db() as conn:
        conn.execute("UPDATE cv_clients SET notes_admin = ? WHERE id = ?",
                     (notes, client_id))
        conn.commit()
    return jsonify({"success": True})


@app.route("/admin/delete/<client_id>", methods=["POST"])
def delete_client(client_id):
    if not admin_required():
        abort(403)
    client = get_client(client_id)
    if client:
        for f in [os.path.join(PDF_DIR, f"{client_id}.pdf")]:
            if os.path.exists(f):
                os.remove(f)
        if client.get("photo_path"):
            p = client["photo_path"] if IS_VERCEL else os.path.join(BASE_DIR, client["photo_path"])
            if os.path.exists(p):
                os.remove(p)
        with get_db() as conn:
            conn.execute("DELETE FROM cv_clients WHERE id = ?", (client_id,))
            conn.commit()
    return jsonify({"success": True})


@app.route("/admin/regenerate/<client_id>", methods=["POST"])
def regenerate_pdf(client_id):
    if not admin_required():
        abort(403)
    return jsonify({"success": generate_pdf(client_id)})


@app.route("/admin/stats")
def admin_stats():
    if not admin_required():
        abort(403)
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM cv_clients").fetchone()[0]
        paid  = conn.execute("SELECT COUNT(*) FROM cv_clients WHERE paid=1").fetchone()[0]
        today_count = conn.execute(
            "SELECT COUNT(*) FROM cv_clients WHERE created_at LIKE ?",
            (f"{today}%",)
        ).fetchone()[0]
    return jsonify({"total": total, "paid": paid,
                    "unpaid": total - paid, "today": today_count})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

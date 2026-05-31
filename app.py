import os
import threading
import time
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

import database as db
import fund_logic

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "changeme-in-production")


# ---------------------------------------------------------------------------
# DB init + seed admin
# ---------------------------------------------------------------------------

def seed_admin():
    existing = db.get_investisseur_by_nom("Malick")
    if not existing:
        pwd = os.environ.get("ADMIN_PASSWORD", "admin123")
        db.create_investisseur(
            nom="Malick",
            password_hash=generate_password_hash(pwd),
            depot=50.0,
            role="admin",
        )
        print("[seed] Admin Malick créé.")


with app.app_context():
    db.init_db()
    seed_admin()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Accès réservé à l'admin.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes auth
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        pwd = request.form.get("password", "")
        inv = db.get_investisseur_by_nom(nom)
        if inv and check_password_hash(inv["password_hash"], pwd):
            session["user"] = inv["nom"]
            session["role"] = inv["role"]
            return redirect(url_for("dashboard"))
        flash("Identifiants incorrects.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard dispatch
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("investor_dashboard"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    data = fund_logic.get_dashboard_admin()
    return render_template("dashboard_admin.html", **data)


@app.route("/investor")
@login_required
def investor_dashboard():
    nom = session["user"]
    data = fund_logic.get_dashboard_investor(nom)
    if not data:
        flash("Investisseur introuvable.", "error")
        return redirect(url_for("login"))
    return render_template("dashboard_investor.html", **data)


# ---------------------------------------------------------------------------
# Admin — gestion investisseurs
# ---------------------------------------------------------------------------

@app.route("/admin/add_investor", methods=["POST"])
@admin_required
def add_investor():
    nom = request.form.get("nom", "").strip()
    depot = request.form.get("depot", "0")
    pwd = request.form.get("password", "")

    if not nom or not pwd:
        flash("Nom et mot de passe requis.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        depot = float(depot)
    except ValueError:
        flash("Montant invalide.", "error")
        return redirect(url_for("admin_dashboard"))

    if db.get_investisseur_by_nom(nom):
        flash(f"L'investisseur '{nom}' existe déjà.", "error")
        return redirect(url_for("admin_dashboard"))

    db.create_investisseur(nom, generate_password_hash(pwd), depot)
    flash(f"Investisseur '{nom}' ajouté avec {depot} USDT.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/add_funds", methods=["POST"])
@admin_required
def add_funds():
    nom = request.form.get("nom", "").strip()
    montant = request.form.get("montant", "0")

    try:
        montant = float(montant)
    except ValueError:
        flash("Montant invalide.", "error")
        return redirect(url_for("admin_dashboard"))

    if montant <= 0:
        flash("Le montant doit être positif.", "error")
        return redirect(url_for("admin_dashboard"))

    if not db.get_investisseur_by_nom(nom):
        flash(f"Investisseur '{nom}' introuvable.", "error")
        return redirect(url_for("admin_dashboard"))

    db.add_funds(nom, montant)
    flash(f"+{montant} USDT ajoutés à '{nom}'.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete_investor", methods=["POST"])
@admin_required
def delete_investor():
    nom = request.form.get("nom", "").strip()
    if not nom:
        flash("Nom requis.", "error")
        return redirect(url_for("admin_dashboard"))
    db.delete_investisseur(nom)
    flash(f"Investisseur '{nom}' supprimé.", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Snapshot manuel
# ---------------------------------------------------------------------------

@app.route("/admin/snapshot", methods=["POST"])
@admin_required
def manual_snapshot():
    result = fund_logic.faire_snapshot()
    if result is None:
        flash("Erreur lors de la connexion Bybit.", "error")
    else:
        _, solde, gain, pct = result
        flash(f"Snapshot OK — Solde: {solde} USDT | Gain jour: {gain} USDT ({pct}%)", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# API JSON (pour refresh AJAX si besoin)
# ---------------------------------------------------------------------------

@app.route("/api/solde")
@admin_required
def api_solde():
    from bybit_service import get_solde_usdt
    solde = get_solde_usdt()
    return jsonify({"solde": solde})


# ---------------------------------------------------------------------------
# Snapshot automatique 23h59
# ---------------------------------------------------------------------------

def scheduler_loop():
    last_snap_date = None
    while True:
        now = datetime.utcnow()
        if now.hour == 23 and now.minute == 59 and now.strftime("%Y-%m-%d") != last_snap_date:
            print(f"[scheduler] Snapshot automatique {now}")
            fund_logic.faire_snapshot()
            last_snap_date = now.strftime("%Y-%m-%d")
        time.sleep(30)


scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
scheduler_thread.start()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

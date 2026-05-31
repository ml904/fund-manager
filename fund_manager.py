"""
╔══════════════════════════════════════════════════════════╗
║         FUND MANAGER — Gestion Fonds d'Investissement   ║
║         Flask + Bybit API + Snapshot quotidien          ║
╚══════════════════════════════════════════════════════════╝

VARIABLES D'ENVIRONNEMENT :
    BYBIT_API_KEY      → clé API Bybit
    BYBIT_API_SECRET   → secret API Bybit
    ADMIN_PASSWORD     → mot de passe admin
    SECRET_KEY         → clé secrète Flask (n'importe quelle chaîne)
"""

import os
import json
import threading
import time
import hashlib
from datetime import datetime, date
from dotenv import load_dotenv
from flask import Flask, render_template_string, request, jsonify, session, redirect
from pybit.unified_trading import HTTP

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey123")

# ──────────────────────────────────────────────
#  FICHIER DE DONNÉES
# ──────────────────────────────────────────────
DATA_FILE = "fund_data.json"

def charger_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "capital_reference": 50.0,
        "capital_par_trade_base": 11.0,
        "capital_par_trade_actuel": 11.0,
        "investisseurs": {
            "Malick": {
                "password": hashlib.md5("admin123".encode()).hexdigest(),
                "depot_total": 50.0,
                "role": "admin"
            }
        },
        "historique": [],
        "snapshot_hier": None,
        "dernier_snapshot": None,
    }

def sauvegarder_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ──────────────────────────────────────────────
#  BYBIT
# ──────────────────────────────────────────────
def obtenir_solde_bybit():
    try:
        session_bybit = HTTP(
            testnet=False,
            api_key=os.getenv("BYBIT_API_KEY", ""),
            api_secret=os.getenv("BYBIT_API_SECRET", ""),
        )
        r     = session_bybit.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        liste = r["result"]["list"]
        for compte in liste:
            for champ in ["totalEquity", "totalWalletBalance"]:
                val = compte.get(champ, "0") or "0"
                if float(val) > 0:
                    return round(float(val), 2)
        return 0.0
    except Exception as e:
        return 0.0

# ──────────────────────────────────────────────
#  CALCUL DES PARTS
# ──────────────────────────────────────────────
def calculer_parts(data):
    total_depot = sum(v["depot_total"] for v in data["investisseurs"].values())
    parts = {}
    for nom, info in data["investisseurs"].items():
        pct = (info["depot_total"] / total_depot * 100) if total_depot > 0 else 0
        parts[nom] = round(pct, 2)
    return parts, total_depot

def ajuster_capital_par_trade(data, solde_actuel):
    """Augmente le capital par trade de 5$ tous les 25$ de gain."""
    base        = data["capital_reference"]
    base_trade  = data["capital_par_trade_base"]
    gain        = solde_actuel - base
    paliers     = int(gain / 25)
    nouveau     = base_trade + (paliers * 5)
    nouveau     = max(base_trade, nouveau)
    data["capital_par_trade_actuel"] = round(nouveau, 2)
    return nouveau

# ──────────────────────────────────────────────
#  SNAPSHOT QUOTIDIEN
# ──────────────────────────────────────────────
def faire_snapshot():
    data         = charger_data()
    solde        = obtenir_solde_bybit()
    aujourd_hui  = date.today().isoformat()

    gain_jour = 0.0
    pct_jour  = 0.0
    if data["snapshot_hier"] is not None:
        gain_jour = round(solde - data["snapshot_hier"], 2)
        pct_jour  = round((gain_jour / data["snapshot_hier"] * 100), 2) if data["snapshot_hier"] > 0 else 0

    parts, total_depot = calculer_parts(data)

    # Gains/pertes par investisseur
    gains_investisseurs = {}
    for nom, pct in parts.items():
        gains_investisseurs[nom] = round(gain_jour * pct / 100, 2)

    # Ajuster capital par trade
    nouveau_capital = ajuster_capital_par_trade(data, solde)

    # Sauvegarder snapshot
    snapshot = {
        "date":                aujourd_hui,
        "solde":               solde,
        "gain_jour":           gain_jour,
        "pct_jour":            pct_jour,
        "parts":               parts,
        "gains_investisseurs": gains_investisseurs,
        "capital_par_trade":   nouveau_capital,
    }

    data["historique"].insert(0, snapshot)
    if len(data["historique"]) > 30:
        data["historique"].pop()

    data["snapshot_hier"]    = solde
    data["dernier_snapshot"] = aujourd_hui
    sauvegarder_data(data)
    return snapshot

# ──────────────────────────────────────────────
#  THREAD SNAPSHOT 23H59
# ──────────────────────────────────────────────
def boucle_snapshot():
    while True:
        now = datetime.now()
        if now.hour == 23 and now.minute == 59:
            faire_snapshot()
            time.sleep(61)
        time.sleep(30)

threading.Thread(target=boucle_snapshot, daemon=True).start()

# ──────────────────────────────────────────────
#  HTML TEMPLATE
# ──────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fund Manager</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=Space+Mono&display=swap');
  :root {
    --bg: #080c10; --panel: #0d1117; --border: #1a2332;
    --green: #00ff88; --red: #ff3b5c; --yellow: #f5c518;
    --blue: #4da6ff; --text: #c9d1d9; --muted: #4a5568;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Space Mono', monospace; background: var(--bg); color: var(--text); min-height: 100vh; padding: 20px; }
  .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border); }
  .logo { font-family: 'Syne', sans-serif; font-size: 20px; font-weight: 800; color: #fff; }
  .logo span { color: var(--green); }
  .btn { padding: 8px 16px; border-radius: 8px; border: none; cursor: pointer; font-family: 'Space Mono', monospace; font-size: 12px; }
  .btn-green { background: #0d2818; color: var(--green); border: 1px solid #1a4d2e; }
  .btn-red { background: #2a0d13; color: var(--red); border: 1px solid #4d1a22; }
  .btn-blue { background: #0d1a2a; color: var(--blue); border: 1px solid #1a3350; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
  .card-label { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }
  .card-value { font-family: 'Syne', sans-serif; font-size: 26px; font-weight: 800; color: #fff; }
  .card-value.green { color: var(--green); }
  .card-value.red { color: var(--red); }
  .card-value.yellow { color: var(--yellow); }
  .section-title { font-family: 'Syne', sans-serif; font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th { text-align: left; color: var(--muted); font-size: 10px; text-transform: uppercase; padding: 0 0 10px 0; border-bottom: 1px solid var(--border); }
  td { padding: 10px 0; border-bottom: 1px solid #0f1923; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 11px; }
  .badge-green { background: #0d2818; color: var(--green); }
  .badge-red { background: #2a0d13; color: var(--red); }
  .input { background: #050810; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: var(--text); font-family: 'Space Mono', monospace; font-size: 12px; width: 100%; margin-bottom: 10px; }
  .form-row { display: flex; gap: 10px; align-items: flex-end; }
  .form-group { flex: 1; }
  .form-label { font-size: 10px; color: var(--muted); margin-bottom: 6px; display: block; }
  .progress-bar { height: 6px; background: var(--border); border-radius: 3px; margin-top: 8px; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: 3px; }
  .investor-card { background: #050810; border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
  .investor-name { font-family: 'Syne', sans-serif; font-weight: 600; font-size: 14px; color: #fff; }
  .login-box { max-width: 400px; margin: 100px auto; }
  .alert { padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 12px; }
  .alert-red { background: #2a0d13; border: 1px solid var(--red); color: var(--red); }
  .alert-green { background: #0d2818; border: 1px solid var(--green); color: var(--green); }
  @media(max-width:768px){ .grid-3{grid-template-columns:1fr 1fr;} .grid-2{grid-template-columns:1fr;} }
</style>
</head>
<body>

{% if not logged_in %}
<!-- PAGE LOGIN -->
<div class="login-box">
  <div style="text-align:center; margin-bottom:32px;">
    <div class="logo">FUND<span>MGR</span></div>
    <div style="font-size:12px; color:var(--muted); margin-top:8px;">Gestion de fonds d'investissement</div>
  </div>
  {% if error %}<div class="alert alert-red">{{ error }}</div>{% endif %}
  <div class="card">
    <div class="section-title">Connexion</div>
    <form method="POST" action="/login">
      <label class="form-label">Nom d'investisseur</label>
      <input class="input" type="text" name="nom" placeholder="Ex: Malick" required>
      <label class="form-label">Mot de passe</label>
      <input class="input" type="password" name="password" required>
      <button class="btn btn-green" type="submit" style="width:100%; padding:12px;">Se connecter</button>
    </form>
  </div>
</div>

{% else %}
<!-- DASHBOARD -->
<div class="header">
  <div class="logo">FUND<span>MGR</span> 💼</div>
  <div style="display:flex; gap:10px; align-items:center;">
    <span style="font-size:11px; color:var(--muted);">{{ user }}</span>
    {% if role == 'admin' %}
    <button class="btn btn-blue" onclick="faireSnapshot()">📸 Snapshot</button>
    {% endif %}
    <a href="/logout"><button class="btn btn-red">Déconnexion</button></a>
  </div>
</div>

<!-- KPI -->
<div class="grid-2">
  <div class="card">
    <div class="card-label">Solde Bybit</div>
    <div class="card-value green" id="solde">{{ solde }} USDT</div>
    <div style="font-size:11px; color:var(--muted); margin-top:6px;">Mis à jour à 23h59</div>
  </div>
  <div class="card">
    <div class="card-label">Gain/Perte aujourd'hui</div>
    <div class="card-value {{ 'green' if gain_jour >= 0 else 'red' }}" id="gain-jour">
      {{ '+' if gain_jour >= 0 else '' }}{{ gain_jour }} USDT
    </div>
    <div style="font-size:11px; color:var(--muted); margin-top:6px;">
      {{ '+' if pct_jour >= 0 else '' }}{{ pct_jour }}% vs hier
    </div>
  </div>
</div>

<div class="grid-2">

  <!-- INVESTISSEURS -->
  <div class="card">
    <div class="section-title">Investisseurs</div>
    {% for nom, info in investisseurs.items() %}
    <div class="investor-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <div class="investor-name">{{ nom }} {% if nom == user %}(toi){% endif %}</div>
        <div style="font-family:'Syne',sans-serif; font-size:18px; font-weight:800; color:var(--blue);">{{ parts[nom] }}%</div>
      </div>
      <div style="font-size:11px; color:var(--muted); margin-top:4px;">
        Dépôt total : {{ info.depot_total }} USDT
      </div>
      <div class="progress-bar">
        <div class="progress-fill" style="width:{{ parts[nom] }}%; background:var(--blue);"></div>
      </div>
      {% if gain_jour != 0 %}
      <div style="font-size:11px; margin-top:8px; color:{{ '#00ff88' if gain_jour >= 0 else '#ff3b5c' }};">
        Gain/Perte du jour : {{ '+' if gain_jour >= 0 else '' }}{{ (gain_jour * parts[nom] / 100)|round(2) }} USDT
      </div>
      {% endif %}
    </div>
    {% endfor %}

    {% if role == 'admin' %}
    <div style="margin-top:16px; border-top:1px solid var(--border); padding-top:16px;">
      <div class="section-title">Ajouter un investisseur</div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">Nom</label>
          <input class="input" id="new-nom" placeholder="Prénom">
        </div>
        <div class="form-group">
          <label class="form-label">Montant (USDT)</label>
          <input class="input" id="new-montant" type="number" placeholder="25">
        </div>
        <div class="form-group">
          <label class="form-label">Mot de passe</label>
          <input class="input" id="new-password" type="password" placeholder="****">
        </div>
      </div>
      <button class="btn btn-green" onclick="ajouterInvestisseur()">+ Ajouter</button>
    </div>
    {% endif %}
  </div>

  <!-- HISTORIQUE -->
  <div class="card">
    <div class="section-title">Historique 30 jours</div>
    {% if historique %}
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Solde</th>
          <th>Gain/Perte</th>
          <th>%</th>
        </tr>
      </thead>
      <tbody>
        {% for h in historique[:15] %}
        <tr>
          <td style="color:var(--muted);">{{ h.date }}</td>
          <td>{{ h.solde }} $</td>
          <td class="{{ 'badge badge-green' if h.gain_jour >= 0 else 'badge badge-red' }}">
            {{ '+' if h.gain_jour >= 0 else '' }}{{ h.gain_jour }}$
          </td>
          <td style="color:{{ '#00ff88' if h.pct_jour >= 0 else '#ff3b5c' }};">
            {{ '+' if h.pct_jour >= 0 else '' }}{{ h.pct_jour }}%
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div style="color:var(--muted); font-size:12px; text-align:center; padding:20px;">
      Aucun historique — le premier snapshot sera fait à 23h59 ce soir
    </div>
    {% endif %}
  </div>

</div>

{% if role == 'admin' %}
<!-- AJOUTER DES FONDS -->
<div class="card" style="margin-bottom:20px;">
  <div class="section-title">Ajouter des fonds à un investisseur existant</div>
  <div class="form-row">
    <div class="form-group">
      <label class="form-label">Investisseur</label>
      <select class="input" id="depot-nom">
        {% for nom in investisseurs.keys() %}
        <option>{{ nom }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Montant à ajouter (USDT)</label>
      <input class="input" id="depot-montant" type="number" placeholder="25">
    </div>
    <div>
      <label class="form-label">&nbsp;</label>
      <button class="btn btn-green" onclick="ajouterFonds()">+ Ajouter fonds</button>
    </div>
  </div>
</div>
{% endif %}

<div id="message" style="display:none;" class="alert"></div>

<script>
function afficherMessage(msg, ok) {
  const el = document.getElementById('message');
  el.textContent = msg;
  el.className = 'alert ' + (ok ? 'alert-green' : 'alert-red');
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 4000);
}

function ajouterInvestisseur() {
  const nom      = document.getElementById('new-nom').value;
  const montant  = document.getElementById('new-montant').value;
  const password = document.getElementById('new-password').value;
  if (!nom || !montant || !password) return afficherMessage('Remplis tous les champs', false);
  fetch('/api/ajouter-investisseur', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({nom, montant: parseFloat(montant), password})
  }).then(r => r.json()).then(d => {
    afficherMessage(d.message, d.ok);
    if (d.ok) setTimeout(() => location.reload(), 1500);
  });
}

function ajouterFonds() {
  const nom     = document.getElementById('depot-nom').value;
  const montant = document.getElementById('depot-montant').value;
  if (!montant) return afficherMessage('Entre un montant', false);
  fetch('/api/ajouter-fonds', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({nom, montant: parseFloat(montant)})
  }).then(r => r.json()).then(d => {
    afficherMessage(d.message, d.ok);
    if (d.ok) setTimeout(() => location.reload(), 1500);
  });
}

function faireSnapshot() {
  afficherMessage('Snapshot en cours...', true);
  fetch('/api/snapshot', {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      afficherMessage(d.message, d.ok);
      if (d.ok) setTimeout(() => location.reload(), 1500);
    });
}
</script>
{% endif %}
</body>
</html>
"""

# ──────────────────────────────────────────────
#  ROUTES
# ──────────────────────────────────────────────
@app.route("/", methods=["GET"])
def index():
    data     = charger_data()
    user     = session.get("user")
    role     = session.get("role", "")
    logged_in = user is not None

    solde          = 0.0
    gain_jour      = 0.0
    pct_jour       = 0.0
    parts          = {}
    capital_trade  = data["capital_par_trade_actuel"]
    historique     = data["historique"]
    investisseurs  = data["investisseurs"]

    if logged_in:
        if data["historique"]:
            dernier = data["historique"][0]
            solde      = dernier["solde"]
            gain_jour  = dernier["gain_jour"]
            pct_jour   = dernier["pct_jour"]
        parts, _ = calculer_parts(data)

    return render_template_string(HTML,
        logged_in=logged_in, user=user, role=role,
        solde=solde, gain_jour=gain_jour, pct_jour=pct_jour,
        capital_par_trade=capital_trade,
        investisseurs=investisseurs, parts=parts,
        historique=historique, error=None
    )

@app.route("/login", methods=["POST"])
def login():
    data     = charger_data()
    nom      = request.form.get("nom", "").strip()
    password = request.form.get("password", "")
    pwd_hash = hashlib.md5(password.encode()).hexdigest()

    if nom in data["investisseurs"] and data["investisseurs"][nom]["password"] == pwd_hash:
        session["user"] = nom
        session["role"] = data["investisseurs"][nom].get("role", "investor")
        return redirect("/")

    parts, _ = calculer_parts(data)
    return render_template_string(HTML,
        logged_in=False, error="Nom ou mot de passe incorrect",
        user=None, role=None, solde=0, gain_jour=0, pct_jour=0,
        capital_par_trade=data["capital_par_trade_actuel"],
        investisseurs=data["investisseurs"], parts=parts,
        historique=data["historique"]
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/ajouter-investisseur", methods=["POST"])
def api_ajouter_investisseur():
    if session.get("role") != "admin":
        return jsonify({"ok": False, "message": "Non autorisé"})
    body     = request.json
    data     = charger_data()
    nom      = body.get("nom", "").strip()
    montant  = float(body.get("montant", 0))
    password = body.get("password", "")
    if not nom or montant <= 0 or not password:
        return jsonify({"ok": False, "message": "Données invalides"})
    if nom in data["investisseurs"]:
        return jsonify({"ok": False, "message": "Investisseur déjà existant"})
    data["investisseurs"][nom] = {
        "password":   hashlib.md5(password.encode()).hexdigest(),
        "depot_total": montant,
        "role":        "investor"
    }
    sauvegarder_data(data)
    return jsonify({"ok": True, "message": f"{nom} ajouté avec {montant} USDT ✅"})

@app.route("/api/ajouter-fonds", methods=["POST"])
def api_ajouter_fonds():
    if session.get("role") != "admin":
        return jsonify({"ok": False, "message": "Non autorisé"})
    body    = request.json
    data    = charger_data()
    nom     = body.get("nom", "")
    montant = float(body.get("montant", 0))
    if nom not in data["investisseurs"] or montant <= 0:
        return jsonify({"ok": False, "message": "Données invalides"})
    data["investisseurs"][nom]["depot_total"] += montant
    sauvegarder_data(data)
    parts, _ = calculer_parts(data)
    return jsonify({"ok": True, "message": f"+{montant} USDT ajouté à {nom} — Part : {parts[nom]}% ✅"})

@app.route("/api/snapshot", methods=["POST"])
def api_snapshot():
    if session.get("role") != "admin":
        return jsonify({"ok": False, "message": "Non autorisé"})
    snap = faire_snapshot()
    return jsonify({
        "ok":      True,
        "message": f"Snapshot fait ✅ — Solde: {snap['solde']} USDT | Gain: {snap['gain_jour']} USDT"
    })

@app.route("/api/solde")
def api_solde():
    return jsonify({"solde": obtenir_solde_bybit()})

# ──────────────────────────────────────────────
#  LANCEMENT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

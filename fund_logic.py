from datetime import datetime
import database as db
import bybit_service


def calculer_parts():
    """Return list of investors with their share percentage."""
    investisseurs = db.get_all_investisseurs()
    total = db.get_total_depots()
    result = []
    for inv in investisseurs:
        part = (inv["depot_total"] / total * 100) if total > 0 else 0
        result.append({
            "nom": inv["nom"],
            "depot_total": inv["depot_total"],
            "part_pct": round(part, 4),
        })
    return result


def faire_snapshot():
    """
    Read Bybit balance, compare with previous snapshot,
    compute daily gain/loss, save to DB.
    Returns (snapshot_id, solde, gain_jour, pct_jour) or None on error.
    """
    solde = bybit_service.get_solde_usdt()
    if solde is None:
        return None

    dernier = db.get_last_snapshot()
    if dernier:
        gain_jour = round(solde - dernier["solde"], 4)
        pct_jour = round((gain_jour / dernier["solde"] * 100), 4) if dernier["solde"] else 0
    else:
        gain_jour = 0.0
        pct_jour = 0.0

    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    snap_id = db.save_snapshot(date_str, solde, gain_jour, pct_jour)

    parts = calculer_parts()
    for inv in parts:
        gain_inv = round(gain_jour * inv["part_pct"] / 100, 4)
        db.save_gain_investisseur(snap_id, inv["nom"], gain_inv, inv["part_pct"])

    return snap_id, solde, gain_jour, pct_jour


def get_dashboard_admin():
    """Aggregate data for admin dashboard."""
    solde_live = bybit_service.get_solde_usdt()
    dernier = db.get_last_snapshot()
    snapshots = db.get_snapshots_30j()
    parts = calculer_parts()
    total_depots = db.get_total_depots()

    gain_jour = 0.0
    pct_jour = 0.0
    if dernier and solde_live is not None:
        gain_jour = round(solde_live - dernier["solde"], 4)
        pct_jour = round((gain_jour / dernier["solde"] * 100), 4) if dernier["solde"] else 0

    return {
        "solde_live": solde_live,
        "gain_jour": gain_jour,
        "pct_jour": pct_jour,
        "parts": parts,
        "snapshots": snapshots,
        "total_depots": total_depots,
        "dernier_snapshot": dernier,
    }


def get_dashboard_investor(nom):
    """Aggregate data for a given investor dashboard."""
    inv = db.get_investisseur_by_nom(nom)
    if not inv:
        return None

    total_depots = db.get_total_depots()
    part_pct = (inv["depot_total"] / total_depots * 100) if total_depots > 0 else 0

    gain_aujourd_hui, _ = db.get_gains_investisseur_today(nom)
    gain_total = db.get_total_gain_investisseur(nom)
    historique = db.get_gains_investisseur_30j(nom)

    return {
        "nom": nom,
        "depot_total": inv["depot_total"],
        "part_pct": round(part_pct, 4),
        "gain_aujourd_hui": gain_aujourd_hui,
        "gain_total": gain_total,
        "historique": historique,
    }

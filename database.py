import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "fund.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS investisseurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            depot_total REAL DEFAULT 0,
            role TEXT DEFAULT 'investor',
            date_ajout TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            solde REAL NOT NULL,
            gain_jour REAL DEFAULT 0,
            pct_jour REAL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS gains_investisseurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            investisseur_nom TEXT NOT NULL,
            gain REAL DEFAULT 0,
            part_pct REAL DEFAULT 0,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
        )
    """)

    conn.commit()
    conn.close()


def get_all_investisseurs():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM investisseurs WHERE role != 'admin' ORDER BY depot_total DESC"
    ).fetchall()
    conn.close()
    return rows


def get_investisseur_by_nom(nom):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM investisseurs WHERE nom = ?", (nom,)
    ).fetchone()
    conn.close()
    return row


def get_investisseur_by_id(id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM investisseurs WHERE id = ?", (id,)
    ).fetchone()
    conn.close()
    return row


def create_investisseur(nom, password_hash, depot, role="investor"):
    conn = get_db()
    conn.execute(
        "INSERT INTO investisseurs (nom, password_hash, depot_total, role) VALUES (?, ?, ?, ?)",
        (nom, password_hash, depot, role),
    )
    conn.commit()
    conn.close()


def add_funds(nom, montant):
    conn = get_db()
    conn.execute(
        "UPDATE investisseurs SET depot_total = depot_total + ? WHERE nom = ?",
        (montant, nom),
    )
    conn.commit()
    conn.close()


def delete_investisseur(nom):
    conn = get_db()
    conn.execute("DELETE FROM investisseurs WHERE nom = ? AND role != 'admin'", (nom,))
    conn.commit()
    conn.close()


def get_total_depots():
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(depot_total), 0) as total FROM investisseurs WHERE role != 'admin'"
    ).fetchone()
    conn.close()
    return row["total"] if row else 0


def save_snapshot(date, solde, gain_jour, pct_jour):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO snapshots (date, solde, gain_jour, pct_jour) VALUES (?, ?, ?, ?)",
        (date, solde, gain_jour, pct_jour),
    )
    snap_id = c.lastrowid
    conn.commit()
    conn.close()
    return snap_id


def save_gain_investisseur(snapshot_id, nom, gain, part_pct):
    conn = get_db()
    conn.execute(
        "INSERT INTO gains_investisseurs (snapshot_id, investisseur_nom, gain, part_pct) VALUES (?, ?, ?, ?)",
        (snapshot_id, nom, gain, part_pct),
    )
    conn.commit()
    conn.close()


def get_last_snapshot():
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def get_snapshots_30j():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM snapshots ORDER BY id DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return list(reversed(rows))


def get_gains_investisseur_30j(nom):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT s.date, gi.gain, gi.part_pct, s.solde
        FROM gains_investisseurs gi
        JOIN snapshots s ON gi.snapshot_id = s.id
        WHERE gi.investisseur_nom = ?
        ORDER BY s.id DESC LIMIT 30
        """,
        (nom,),
    ).fetchall()
    conn.close()
    return list(reversed(rows))


def get_gains_investisseur_today(nom):
    last = get_last_snapshot()
    if not last:
        return 0, 0
    conn = get_db()
    row = conn.execute(
        "SELECT gain, part_pct FROM gains_investisseurs WHERE snapshot_id = ? AND investisseur_nom = ?",
        (last["id"], nom),
    ).fetchone()
    conn.close()
    if row:
        return row["gain"], row["part_pct"]
    return 0, 0


def get_total_gain_investisseur(nom):
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(gain), 0) as total FROM gains_investisseurs WHERE investisseur_nom = ?",
        (nom,),
    ).fetchone()
    conn.close()
    return row["total"] if row else 0

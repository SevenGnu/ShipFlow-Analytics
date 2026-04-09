import sqlite3
import os
import hashlib
import secrets
import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, session, g

app = Flask(__name__, static_folder="static")
app.secret_key = secrets.token_hex(32)

DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")

# Demo account ID — only this account gets seed data
DEMO_ACCOUNT_EMAIL = "admin@shipflow.com"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        -- ===== ACCOUNTS & AUTH =====
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            name TEXT NOT NULL,
            company TEXT,
            phone TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'starter',
            account_type TEXT NOT NULL DEFAULT 'personal',
            api_key TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            onboarding_complete INTEGER DEFAULT 0,
            company_size TEXT,
            industry TEXT,
            monthly_shipments TEXT,
            annual_revenue TEXT,
            team_size TEXT,
            enterprise_quote REAL,
            enterprise_quote_status TEXT DEFAULT 'none',
            created_at TEXT NOT NULL,
            last_login TEXT
        );

        -- ===== USE CASES =====
        CREATE TABLE IF NOT EXISTS account_use_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            use_case TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            UNIQUE(account_id, use_case)
        );

        -- ===== CONNECTED PLATFORMS =====
        CREATE TABLE IF NOT EXISTS connected_platforms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            platform_key TEXT NOT NULL,
            platform_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            config TEXT,
            connected_at TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            UNIQUE(account_id, platform_key)
        );

        -- ===== PRICING TIERS =====
        CREATE TABLE IF NOT EXISTS pricing_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tier_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            price_monthly REAL NOT NULL DEFAULT 0,
            description TEXT,
            features TEXT,
            max_shipments INTEGER,
            max_platforms INTEGER,
            max_team_members INTEGER,
            sort_order INTEGER DEFAULT 0
        );

        -- ===== ENTERPRISE QUESTIONNAIRE =====
        CREATE TABLE IF NOT EXISTS enterprise_questionnaires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            company_name TEXT,
            company_size TEXT,
            industry TEXT,
            monthly_shipments TEXT,
            annual_revenue TEXT,
            team_size TEXT,
            current_tools TEXT,
            pain_points TEXT,
            timeline TEXT,
            additional_notes TEXT,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        -- ===== MEETING REQUESTS =====
        CREATE TABLE IF NOT EXISTS meeting_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            contact_phone TEXT,
            preferred_date TEXT,
            preferred_time TEXT,
            timezone TEXT DEFAULT 'EST',
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        -- ===== TEAM MEMBERS (enterprise) =====
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'viewer',
            status TEXT NOT NULL DEFAULT 'invited',
            invited_at TEXT NOT NULL,
            joined_at TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        -- ===== PAYMENT METHODS =====
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            label TEXT NOT NULL,
            provider TEXT,
            last_four TEXT,
            bank_name TEXT,
            routing_number_masked TEXT,
            card_brand TEXT,
            exp_month INTEGER,
            exp_year INTEGER,
            billing_address TEXT,
            is_default INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        -- ===== INVOICES & BILLING =====
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            invoice_number TEXT UNIQUE NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            subtotal REAL NOT NULL,
            tax REAL DEFAULT 0,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            payment_method_id INTEGER,
            paid_at TEXT,
            due_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (payment_method_id) REFERENCES payment_methods(id)
        );

        CREATE TABLE IF NOT EXISTS invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            total REAL NOT NULL,
            shipment_id INTEGER,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        -- ===== SHIPPING RATES =====
        CREATE TABLE IF NOT EXISTS shipping_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            carrier_id INTEGER NOT NULL,
            service_level TEXT NOT NULL,
            origin_region TEXT,
            destination_region TEXT,
            min_weight REAL DEFAULT 0,
            max_weight REAL DEFAULT 999,
            base_rate REAL NOT NULL,
            per_lb_rate REAL NOT NULL DEFAULT 0,
            fuel_surcharge_pct REAL DEFAULT 0,
            insurance_rate_pct REAL DEFAULT 0,
            estimated_days_min INTEGER,
            estimated_days_max INTEGER,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (carrier_id) REFERENCES carriers(id)
        );

        -- ===== NOTIFICATIONS =====
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'normal',
            title TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT 'ShipFlow System',
            entity_type TEXT,
            entity_id INTEGER,
            action_label TEXT,
            action_link TEXT,
            read INTEGER DEFAULT 0,
            starred INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        -- ===== ACTIVITY LOG =====
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL
        );

        -- ===== EXISTING SHIPPING TABLES =====
        CREATE TABLE IF NOT EXISTS carriers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL,
            contact_email TEXT,
            contact_phone TEXT,
            rating REAL DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            region TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            current_load INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            company TEXT,
            phone TEXT,
            address TEXT,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip TEXT,
            region TEXT NOT NULL,
            tier TEXT NOT NULL DEFAULT 'standard',
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );

        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT UNIQUE NOT NULL,
            account_id INTEGER,
            customer_id INTEGER NOT NULL,
            carrier_id INTEGER NOT NULL,
            origin_warehouse_id INTEGER NOT NULL,
            destination_name TEXT,
            destination_address TEXT,
            destination_city TEXT NOT NULL,
            destination_state TEXT NOT NULL,
            destination_zip TEXT,
            destination_region TEXT NOT NULL,
            weight_lbs REAL NOT NULL,
            dimensions TEXT,
            package_type TEXT NOT NULL,
            service_level TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'label_created',
            shipping_cost REAL NOT NULL,
            insurance_cost REAL DEFAULT 0,
            declared_value REAL DEFAULT 0,
            quoted_days INTEGER NOT NULL,
            actual_days INTEGER,
            special_instructions TEXT,
            shipped_at TEXT,
            delivered_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (carrier_id) REFERENCES carriers(id)
        );

        CREATE TABLE IF NOT EXISTS shipment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            location TEXT,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (shipment_id) REFERENCES shipments(id)
        );

        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            account_id INTEGER,
            type TEXT NOT NULL,
            reason TEXT NOT NULL,
            description TEXT,
            amount REAL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (shipment_id) REFERENCES shipments(id)
        );

        CREATE TABLE IF NOT EXISTS saved_addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip TEXT NOT NULL,
            phone TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        );
    """)
    conn.commit()
    conn.close()


# ---------- Auth helpers ----------

def _now():
    return datetime.now(timezone.utc)


def _hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def _gen_api_key():
    return "sf_" + secrets.token_hex(24)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check session or API key
        if "account_id" in session:
            return f(*args, **kwargs)
        api_key = request.headers.get("X-API-Key")
        if api_key:
            db = get_db()
            acct = db.execute("SELECT id FROM accounts WHERE api_key=? AND status='active'", (api_key,)).fetchone()
            if acct:
                session["account_id"] = acct["id"]
                return f(*args, **kwargs)
        return jsonify({"error": "Authentication required"}), 401
    return decorated


def get_account_id():
    return session.get("account_id")


# ============================================================
#  STATIC
# ============================================================

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ============================================================
#  AUTH ROUTES
# ============================================================

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.json
    if not data or not data.get("email") or not data.get("password") or not data.get("name"):
        return jsonify({"error": "Email, password, and name are required"}), 400

    db = get_db()
    existing = db.execute("SELECT id FROM accounts WHERE email=?", (data["email"],)).fetchone()
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    salt = secrets.token_hex(16)
    pw_hash = _hash_pw(data["password"], salt)
    api_key = _gen_api_key()
    now = _now().isoformat()
    account_type = data.get("account_type", "personal")
    plan = data.get("plan", "free" if account_type == "personal" else "enterprise_starter")

    db.execute("""INSERT INTO accounts (email, password_hash, salt, name, company, phone, plan, account_type,
                  api_key, onboarding_complete, created_at, last_login)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
               (data["email"], pw_hash, salt, data["name"], data.get("company"),
                data.get("phone"), plan, account_type, api_key, 0, now, now))
    db.commit()

    acct = db.execute("SELECT * FROM accounts WHERE email=?", (data["email"],)).fetchone()
    session["account_id"] = acct["id"]

    db.execute("INSERT INTO activity_log (account_id, action, details, created_at) VALUES (?,?,?,?)",
               (acct["id"], "account_created", f"New {account_type} account signup", now))
    db.commit()

    return jsonify({"id": acct["id"], "email": acct["email"], "name": acct["name"],
                     "api_key": api_key, "plan": acct["plan"], "account_type": account_type,
                     "onboarding_complete": 0}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password required"}), 400

    db = get_db()
    acct = db.execute("SELECT * FROM accounts WHERE email=?", (data["email"],)).fetchone()
    if not acct:
        return jsonify({"error": "Invalid credentials"}), 401

    pw_hash = _hash_pw(data["password"], acct["salt"])
    if pw_hash != acct["password_hash"]:
        return jsonify({"error": "Invalid credentials"}), 401

    session["account_id"] = acct["id"]
    now = _now().isoformat()
    db.execute("UPDATE accounts SET last_login=? WHERE id=?", (now, acct["id"]))
    db.execute("INSERT INTO activity_log (account_id, action, created_at) VALUES (?,?,?)",
               (acct["id"], "login", now))
    db.commit()

    return jsonify({"id": acct["id"], "email": acct["email"], "name": acct["name"],
                     "plan": acct["plan"], "api_key": acct["api_key"],
                     "account_type": acct["account_type"] if "account_type" in acct.keys() else "personal",
                     "onboarding_complete": acct["onboarding_complete"] if "onboarding_complete" in acct.keys() else 1})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
@login_required
def me():
    db = get_db()
    acct = db.execute("""SELECT id, email, name, company, phone, role, plan, account_type, api_key, status,
                         onboarding_complete, company_size, industry, monthly_shipments, annual_revenue,
                         team_size, enterprise_quote, enterprise_quote_status, created_at, last_login
                         FROM accounts WHERE id=?""",
                      (get_account_id(),)).fetchone()
    result = dict(acct)
    # Get use cases
    use_cases = db.execute("SELECT use_case FROM account_use_cases WHERE account_id=?", (get_account_id(),)).fetchall()
    result["use_cases"] = [r["use_case"] for r in use_cases]
    # Get connected platforms
    platforms = db.execute("SELECT * FROM connected_platforms WHERE account_id=?", (get_account_id(),)).fetchall()
    result["platforms"] = [dict(p) for p in platforms]
    return jsonify(result)


@app.route("/api/auth/update", methods=["PUT"])
@login_required
def update_account():
    data = request.json
    db = get_db()
    fields = []
    vals = []
    for f in ("name", "company", "phone"):
        if f in data:
            fields.append(f"{f}=?")
            vals.append(data[f])
    if fields:
        vals.append(get_account_id())
        db.execute(f"UPDATE accounts SET {','.join(fields)} WHERE id=?", vals)
        db.commit()
    acct = db.execute("SELECT id, email, name, company, phone, role, plan, api_key, status, created_at FROM accounts WHERE id=?",
                      (get_account_id(),)).fetchone()
    return jsonify(dict(acct))


@app.route("/api/auth/regenerate-key", methods=["POST"])
@login_required
def regenerate_api_key():
    db = get_db()
    new_key = _gen_api_key()
    db.execute("UPDATE accounts SET api_key=? WHERE id=?", (new_key, get_account_id()))
    db.execute("INSERT INTO activity_log (account_id, action, details, created_at) VALUES (?,?,?,?)",
               (get_account_id(), "api_key_regenerated", "API key was regenerated", _now().isoformat()))
    db.commit()
    return jsonify({"api_key": new_key})


# ============================================================
#  PAYMENT METHODS
# ============================================================

@app.route("/api/payment-methods")
@login_required
def list_payment_methods():
    db = get_db()
    rows = db.execute("SELECT * FROM payment_methods WHERE account_id=? AND status='active' ORDER BY is_default DESC, created_at DESC",
                      (get_account_id(),)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/payment-methods", methods=["POST"])
@login_required
def add_payment_method():
    data = request.json
    if not data or not data.get("type"):
        return jsonify({"error": "Payment method type required"}), 400

    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()
    ptype = data["type"]  # "bank_account", "credit_card", "debit_card", "paypal", "wire"

    label = data.get("label", "")
    last_four = data.get("last_four", "")
    bank_name = data.get("bank_name")
    routing_masked = data.get("routing_number", "")
    if routing_masked and len(routing_masked) > 4:
        routing_masked = "****" + routing_masked[-4:]
    card_brand = data.get("card_brand")
    exp_month = data.get("exp_month")
    exp_year = data.get("exp_year")
    billing_address = data.get("billing_address")
    provider = data.get("provider")

    # Auto-set label if not given
    if not label:
        if ptype == "bank_account":
            label = f"{bank_name or 'Bank'} ****{last_four}"
        elif ptype in ("credit_card", "debit_card"):
            label = f"{card_brand or 'Card'} ****{last_four}"
        elif ptype == "paypal":
            label = f"PayPal ({data.get('paypal_email', '')})"
        elif ptype == "wire":
            label = f"Wire Transfer - {bank_name or 'Bank'}"
        else:
            label = ptype

    # If first payment method, make default
    existing = db.execute("SELECT COUNT(*) FROM payment_methods WHERE account_id=? AND status='active'", (aid,)).fetchone()[0]
    is_default = 1 if existing == 0 else data.get("is_default", 0)

    if is_default:
        db.execute("UPDATE payment_methods SET is_default=0 WHERE account_id=?", (aid,))

    db.execute("""INSERT INTO payment_methods
        (account_id, type, label, provider, last_four, bank_name, routing_number_masked,
         card_brand, exp_month, exp_year, billing_address, is_default, verified, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid, ptype, label, provider, last_four, bank_name, routing_masked,
         card_brand, exp_month, exp_year, billing_address, is_default, 0, now))
    db.commit()

    pm_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    db.execute("INSERT INTO activity_log (account_id, action, entity_type, entity_id, details, created_at) VALUES (?,?,?,?,?,?)",
               (aid, "payment_method_added", "payment_method", pm_id, f"Added {ptype}: {label}", now))

    # Auto-create verification notification
    db.execute("INSERT INTO notifications (account_id, type, title, message, created_at) VALUES (?,?,?,?,?)",
               (aid, "payment", "Payment method added",
                f"Your {ptype.replace('_',' ')} ending in {last_four} has been added. Verification may take 1-2 business days.", now))
    db.commit()

    return jsonify(dict(db.execute("SELECT * FROM payment_methods WHERE id=?", (pm_id,)).fetchone())), 201


@app.route("/api/payment-methods/<int:pm_id>", methods=["DELETE"])
@login_required
def remove_payment_method(pm_id):
    db = get_db()
    db.execute("UPDATE payment_methods SET status='removed' WHERE id=? AND account_id=?", (pm_id, get_account_id()))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/payment-methods/<int:pm_id>/default", methods=["PUT"])
@login_required
def set_default_payment(pm_id):
    db = get_db()
    aid = get_account_id()
    db.execute("UPDATE payment_methods SET is_default=0 WHERE account_id=?", (aid,))
    db.execute("UPDATE payment_methods SET is_default=1 WHERE id=? AND account_id=?", (pm_id, aid))
    db.commit()
    return jsonify({"ok": True})


# ============================================================
#  INVOICES & BILLING
# ============================================================

@app.route("/api/invoices")
@login_required
def list_invoices():
    db = get_db()
    rows = db.execute("""SELECT i.*, pm.label as payment_label
        FROM invoices i LEFT JOIN payment_methods pm ON i.payment_method_id=pm.id
        WHERE i.account_id=? ORDER BY i.created_at DESC""", (get_account_id(),)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/invoices/<int:inv_id>")
@login_required
def get_invoice(inv_id):
    db = get_db()
    inv = db.execute("SELECT * FROM invoices WHERE id=? AND account_id=?", (inv_id, get_account_id())).fetchone()
    if not inv:
        return jsonify({"error": "Not found"}), 404
    lines = db.execute("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,)).fetchall()
    result = dict(inv)
    result["lines"] = [dict(l) for l in lines]
    return jsonify(result)


@app.route("/api/invoices/<int:inv_id>/pay", methods=["POST"])
@login_required
def pay_invoice(inv_id):
    db = get_db()
    aid = get_account_id()
    inv = db.execute("SELECT * FROM invoices WHERE id=? AND account_id=?", (inv_id, aid)).fetchone()
    if not inv:
        return jsonify({"error": "Not found"}), 404
    if inv["status"] == "paid":
        return jsonify({"error": "Already paid"}), 400

    data = request.json or {}
    pm_id = data.get("payment_method_id")
    if not pm_id:
        pm = db.execute("SELECT id FROM payment_methods WHERE account_id=? AND is_default=1 AND status='active'", (aid,)).fetchone()
        if not pm:
            return jsonify({"error": "No payment method available"}), 400
        pm_id = pm["id"]

    now = _now().isoformat()
    db.execute("UPDATE invoices SET status='paid', paid_at=?, payment_method_id=? WHERE id=?", (now, pm_id, inv_id))
    db.execute("INSERT INTO activity_log (account_id, action, entity_type, entity_id, details, created_at) VALUES (?,?,?,?,?,?)",
               (aid, "invoice_paid", "invoice", inv_id, f"Paid invoice {inv['invoice_number']}: ${inv['total']:.2f}", now))
    db.execute("INSERT INTO notifications (account_id, type, title, message, created_at) VALUES (?,?,?,?,?)",
               (aid, "billing", "Payment confirmed", f"Payment of ${inv['total']:.2f} for invoice {inv['invoice_number']} has been processed.", now))
    db.commit()
    return jsonify({"ok": True, "status": "paid"})


@app.route("/api/billing/summary")
@login_required
def billing_summary():
    db = get_db()
    aid = get_account_id()
    c = db.cursor()
    c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE account_id=? AND status='paid'", (aid,))
    total_paid = round(c.fetchone()[0], 2)
    c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE account_id=? AND status='pending'", (aid,))
    outstanding = round(c.fetchone()[0], 2)
    c.execute("SELECT COUNT(*) FROM invoices WHERE account_id=? AND status='pending' AND due_date < ?", (aid, _now().isoformat()))
    overdue = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM payment_methods WHERE account_id=? AND status='active'", (aid,))
    pm_count = c.fetchone()[0]
    return jsonify({"total_paid": total_paid, "outstanding": outstanding, "overdue_count": overdue, "payment_methods": pm_count})


# ============================================================
#  RATE CALCULATOR
# ============================================================

@app.route("/api/rates/calculate", methods=["POST"])
def calculate_rate():
    data = request.json
    if not data:
        return jsonify({"error": "Provide weight, origin_region, destination_region"}), 400

    weight = data.get("weight", 1)
    origin = data.get("origin_region", "")
    dest = data.get("destination_region", "")

    db = get_db()
    rates = db.execute("""
        SELECT sr.*, c.name as carrier_name
        FROM shipping_rates sr
        JOIN carriers c ON sr.carrier_id = c.id
        WHERE sr.active = 1
          AND (sr.origin_region IS NULL OR sr.origin_region = ?)
          AND (sr.destination_region IS NULL OR sr.destination_region = ?)
          AND sr.min_weight <= ? AND sr.max_weight >= ?
        ORDER BY sr.base_rate
    """, (origin, dest, weight, weight)).fetchall()

    results = []
    for r in rates:
        base = r["base_rate"] + (weight * r["per_lb_rate"])
        fuel = base * (r["fuel_surcharge_pct"] / 100) if r["fuel_surcharge_pct"] else 0
        declared = data.get("declared_value", 0)
        insurance = declared * (r["insurance_rate_pct"] / 100) if r["insurance_rate_pct"] and declared else 0
        total = round(base + fuel + insurance, 2)
        results.append({
            "carrier": r["carrier_name"],
            "service_level": r["service_level"],
            "base_rate": round(base, 2),
            "fuel_surcharge": round(fuel, 2),
            "insurance": round(insurance, 2),
            "total": total,
            "estimated_days_min": r["estimated_days_min"],
            "estimated_days_max": r["estimated_days_max"],
        })

    results.sort(key=lambda x: x["total"])
    return jsonify(results)


@app.route("/api/rates")
def list_rates():
    db = get_db()
    rows = db.execute("""
        SELECT sr.*, c.name as carrier_name FROM shipping_rates sr
        JOIN carriers c ON sr.carrier_id = c.id WHERE sr.active=1
        ORDER BY c.name, sr.service_level
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ============================================================
#  CREATE SHIPMENT
# ============================================================

@app.route("/api/shipments/create", methods=["POST"])
@login_required
def create_shipment():
    data = request.json
    if not data:
        return jsonify({"error": "Shipment data required"}), 400

    required = ["destination_city", "destination_state", "weight_lbs", "service_level", "carrier_id"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing field: {f}"}), 400

    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()

    # Generate tracking number
    tracking = "SF" + secrets.token_hex(6).upper()

    # Determine region from state
    state_to_region = {}
    for region_data in [
        ("Northeast", ["NY","NJ","PA","MA","CT","NH","VT","ME","RI"]),
        ("Southeast", ["FL","GA","NC","SC","VA","TN","AL"]),
        ("Midwest", ["IL","OH","MI","IN","WI","MN","MO","IA"]),
        ("Southwest", ["TX","AZ","NM","OK","NV"]),
        ("West", ["CA","WA","OR","CO","UT"]),
    ]:
        for st in region_data[1]:
            state_to_region[st] = region_data[0]

    dest_region = state_to_region.get(data["destination_state"], "Unknown")

    # Pick warehouse
    wh = db.execute("SELECT id FROM warehouses ORDER BY RANDOM() LIMIT 1").fetchone()

    # Calculate cost from rates or use a default
    weight = float(data["weight_lbs"])
    rate = db.execute("""SELECT * FROM shipping_rates WHERE carrier_id=? AND service_level=? AND min_weight<=? AND max_weight>=? AND active=1 LIMIT 1""",
                      (data["carrier_id"], data["service_level"], weight, weight)).fetchone()

    if rate:
        cost = round(rate["base_rate"] + weight * rate["per_lb_rate"], 2)
        quoted_days = rate["estimated_days_max"] or 5
    else:
        cost = round(8.99 + weight * 0.5, 2)
        quoted_days = 5

    insurance = round(float(data.get("declared_value", 0)) * 0.02, 2)

    # Get or create customer
    customer_id = data.get("customer_id")
    if not customer_id and data.get("destination_name"):
        db.execute("""INSERT INTO customers (name, email, city, state, region, created_at)
                      VALUES (?,?,?,?,?,?)""",
                   (data["destination_name"], data.get("destination_email", f"customer_{secrets.token_hex(4)}@example.com"),
                    data["destination_city"], data["destination_state"], dest_region, now))
        customer_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    if not customer_id:
        customer_id = db.execute("SELECT id FROM customers LIMIT 1").fetchone()["id"]

    db.execute("""INSERT INTO shipments
        (tracking_number, account_id, customer_id, carrier_id, origin_warehouse_id,
         destination_name, destination_address, destination_city, destination_state, destination_zip, destination_region,
         weight_lbs, dimensions, package_type, service_level, status, shipping_cost, insurance_cost,
         declared_value, quoted_days, special_instructions, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tracking, aid, customer_id, data["carrier_id"], wh["id"],
         data.get("destination_name"), data.get("destination_address"),
         data["destination_city"], data["destination_state"], data.get("destination_zip"), dest_region,
         weight, data.get("dimensions"), data.get("package_type", "parcel"),
         data["service_level"], "label_created", cost, insurance,
         data.get("declared_value", 0), quoted_days, data.get("special_instructions"), now, now))

    ship_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    db.execute("INSERT INTO shipment_events (shipment_id, event_type, description, created_at) VALUES (?,?,?,?)",
               (ship_id, "label_created", "Shipping label created", now))

    db.execute("INSERT INTO activity_log (account_id, action, entity_type, entity_id, details, created_at) VALUES (?,?,?,?,?,?)",
               (aid, "shipment_created", "shipment", ship_id, f"Created shipment {tracking}", now))
    db.commit()

    return jsonify({"id": ship_id, "tracking_number": tracking, "cost": cost, "insurance": insurance,
                     "quoted_days": quoted_days, "status": "label_created"}), 201


# ============================================================
#  NOTIFICATIONS
# ============================================================

@app.route("/api/notifications")
@login_required
def list_notifications():
    db = get_db()
    filter_type = request.args.get("type")
    starred = request.args.get("starred")
    archived = request.args.get("archived", "0")

    query = "SELECT * FROM notifications WHERE account_id=? AND archived=?"
    params = [get_account_id(), int(archived)]

    if filter_type:
        query += " AND type=?"
        params.append(filter_type)
    if starred:
        query += " AND starred=1"

    query += " ORDER BY created_at DESC LIMIT 100"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/notifications/<int:nid>")
@login_required
def get_notification(nid):
    db = get_db()
    row = db.execute("SELECT * FROM notifications WHERE id=? AND account_id=?",
                     (nid, get_account_id())).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    # Auto-mark as read when opened
    if not row["read"]:
        db.execute("UPDATE notifications SET read=1 WHERE id=?", (nid,))
        db.commit()
    return jsonify(dict(row))


@app.route("/api/notifications/unread-count")
@login_required
def unread_count():
    db = get_db()
    c = db.execute("SELECT COUNT(*) FROM notifications WHERE account_id=? AND read=0 AND archived=0",
                   (get_account_id(),)).fetchone()[0]
    return jsonify({"count": c})


@app.route("/api/notifications/<int:nid>/read", methods=["PUT"])
@login_required
def mark_read(nid):
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE id=? AND account_id=?", (nid, get_account_id()))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/notifications/<int:nid>/star", methods=["PUT"])
@login_required
def toggle_star(nid):
    db = get_db()
    row = db.execute("SELECT starred FROM notifications WHERE id=? AND account_id=?",
                     (nid, get_account_id())).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    new_val = 0 if row["starred"] else 1
    db.execute("UPDATE notifications SET starred=? WHERE id=?", (new_val, nid))
    db.commit()
    return jsonify({"starred": new_val})


@app.route("/api/notifications/<int:nid>/archive", methods=["PUT"])
@login_required
def archive_notification(nid):
    db = get_db()
    db.execute("UPDATE notifications SET archived=1 WHERE id=? AND account_id=?", (nid, get_account_id()))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/notifications/<int:nid>", methods=["DELETE"])
@login_required
def delete_notification(nid):
    db = get_db()
    db.execute("DELETE FROM notifications WHERE id=? AND account_id=?", (nid, get_account_id()))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/notifications/read-all", methods=["PUT"])
@login_required
def mark_all_read():
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE account_id=? AND archived=0", (get_account_id(),))
    db.commit()
    return jsonify({"ok": True})


# ============================================================
#  ACTIVITY LOG
# ============================================================

@app.route("/api/activity")
@login_required
def activity():
    db = get_db()
    rows = db.execute("SELECT * FROM activity_log WHERE account_id=? ORDER BY created_at DESC LIMIT 50",
                      (get_account_id(),)).fetchall()
    return jsonify([dict(r) for r in rows])


# ============================================================
#  SAVED ADDRESSES
# ============================================================

@app.route("/api/addresses")
@login_required
def list_addresses():
    db = get_db()
    rows = db.execute("SELECT * FROM saved_addresses WHERE account_id=? ORDER BY is_default DESC, label",
                      (get_account_id(),)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/addresses", methods=["POST"])
@login_required
def add_address():
    data = request.json
    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()
    db.execute("""INSERT INTO saved_addresses (account_id, label, name, address, city, state, zip, phone, created_at)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (aid, data.get("label",""), data.get("name",""), data.get("address",""),
                data.get("city",""), data.get("state",""), data.get("zip",""), data.get("phone"), now))
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/addresses/<int:addr_id>", methods=["DELETE"])
@login_required
def delete_address(addr_id):
    db = get_db()
    db.execute("DELETE FROM saved_addresses WHERE id=? AND account_id=?", (addr_id, get_account_id()))
    db.commit()
    return jsonify({"ok": True})


# ============================================================
#  TRACKING LOOKUP (public)
# ============================================================

@app.route("/api/track/<tracking_number>")
def track_shipment(tracking_number):
    db = get_db()
    ship = db.execute("""SELECT s.*, c.name as carrier_name FROM shipments s
        JOIN carriers c ON s.carrier_id=c.id WHERE s.tracking_number=?""", (tracking_number,)).fetchone()
    if not ship:
        return jsonify({"error": "Tracking number not found"}), 404
    events = db.execute("SELECT * FROM shipment_events WHERE shipment_id=? ORDER BY created_at", (ship["id"],)).fetchall()
    result = dict(ship)
    result["events"] = [dict(e) for e in events]
    return jsonify(result)


# ============================================================
#  ANALYTICS ENDPOINTS (existing, improved)
# ============================================================

@app.route("/api/overview")
def overview():
    db = get_db()
    c = db.cursor()
    ms = _now().replace(day=1).strftime("%Y-%m-%d")
    pms = (_now().replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d")

    c.execute("SELECT COUNT(*) FROM shipments")
    total_shipments = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shipments WHERE created_at >= ?", (ms,))
    month_shipments = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shipments WHERE created_at >= ? AND created_at < ?", (pms, ms))
    prev_month_shipments = c.fetchone()[0]
    shipment_growth = round(((month_shipments - prev_month_shipments) / prev_month_shipments * 100), 2) if prev_month_shipments else 0

    c.execute("SELECT COALESCE(SUM(shipping_cost + insurance_cost), 0) FROM shipments")
    total_revenue = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(shipping_cost + insurance_cost), 0) FROM shipments WHERE created_at >= ?", (ms,))
    month_revenue = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(shipping_cost + insurance_cost), 0) FROM shipments WHERE created_at >= ? AND created_at < ?", (pms, ms))
    prev_month_revenue = c.fetchone()[0]
    revenue_growth = round(((month_revenue - prev_month_revenue) / prev_month_revenue * 100), 2) if prev_month_revenue else 0

    c.execute("SELECT COUNT(*) FROM shipments WHERE status='delivered'")
    delivered = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shipments WHERE status IN ('in_transit','out_for_delivery')")
    in_transit = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shipments WHERE status='delivered' AND actual_days <= quoted_days")
    on_time = c.fetchone()[0]
    on_time_rate = round(on_time / delivered * 100, 1) if delivered else 0
    c.execute("SELECT COALESCE(AVG(actual_days), 0) FROM shipments WHERE status='delivered'")
    avg_delivery_days = round(c.fetchone()[0], 1)
    c.execute("SELECT COALESCE(AVG(shipping_cost), 0) FROM shipments")
    avg_cost = round(c.fetchone()[0], 2)
    c.execute("SELECT COUNT(*) FROM shipments WHERE status='returned'")
    returned = c.fetchone()[0]
    return_rate = round(returned / total_shipments * 100, 1) if total_shipments else 0
    c.execute("SELECT COUNT(*) FROM claims WHERE status='open'")
    open_claims = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM shipments WHERE status='exception'")
    exceptions = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM customers")
    total_customers = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts")
    total_accounts = c.fetchone()[0]

    return jsonify({
        "total_shipments": total_shipments, "month_shipments": month_shipments, "shipment_growth": shipment_growth,
        "total_revenue": round(total_revenue, 2), "month_revenue": round(month_revenue, 2), "revenue_growth": revenue_growth,
        "delivered": delivered, "in_transit": in_transit, "on_time_rate": on_time_rate,
        "avg_delivery_days": avg_delivery_days, "avg_cost": avg_cost,
        "return_rate": return_rate, "returned": returned, "open_claims": open_claims, "exceptions": exceptions,
        "total_customers": total_customers, "total_accounts": total_accounts,
    })


@app.route("/api/shipments/daily")
def shipments_daily():
    days = request.args.get("days", 30, type=int)
    db = get_db()
    since = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.execute("""SELECT DATE(created_at) as date, COUNT(*) as count,
        SUM(shipping_cost + insurance_cost) as revenue FROM shipments WHERE created_at >= ?
        GROUP BY DATE(created_at) ORDER BY date""", (since,)).fetchall()
    return jsonify([{"date": r["date"], "count": r["count"], "revenue": round(r["revenue"], 2)} for r in rows])


@app.route("/api/shipments/by-status")
def shipments_by_status():
    db = get_db()
    rows = db.execute("SELECT status, COUNT(*) as count FROM shipments GROUP BY status ORDER BY count DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/shipments/by-service")
def shipments_by_service():
    db = get_db()
    rows = db.execute("""SELECT service_level, COUNT(*) as count, ROUND(AVG(shipping_cost),2) as avg_cost,
        ROUND(AVG(actual_days),1) as avg_days FROM shipments GROUP BY service_level ORDER BY count DESC""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/shipments/by-package")
def shipments_by_package():
    db = get_db()
    rows = db.execute("SELECT package_type, COUNT(*) as count FROM shipments GROUP BY package_type ORDER BY count DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/carriers/performance")
def carriers_performance():
    db = get_db()
    rows = db.execute("""SELECT ca.name as carrier, ca.type as carrier_type,
        COUNT(s.id) as total_shipments,
        SUM(CASE WHEN s.status='delivered' THEN 1 ELSE 0 END) as delivered,
        SUM(CASE WHEN s.status='delivered' AND s.actual_days <= s.quoted_days THEN 1 ELSE 0 END) as on_time,
        ROUND(AVG(CASE WHEN s.status='delivered' THEN s.actual_days END), 1) as avg_days,
        ROUND(AVG(s.shipping_cost), 2) as avg_cost,
        SUM(CASE WHEN s.status='returned' THEN 1 ELSE 0 END) as returns,
        SUM(CASE WHEN s.status='exception' THEN 1 ELSE 0 END) as exceptions
        FROM shipments s JOIN carriers ca ON s.carrier_id = ca.id GROUP BY ca.id ORDER BY total_shipments DESC""").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["on_time_rate"] = round(d["on_time"] / d["delivered"] * 100, 1) if d["delivered"] else 0
        d["return_rate"] = round(d["returns"] / d["total_shipments"] * 100, 1) if d["total_shipments"] else 0
        result.append(d)
    return jsonify(result)


@app.route("/api/delivery/time-distribution")
def delivery_time_dist():
    db = get_db()
    rows = db.execute("SELECT actual_days as days, COUNT(*) as count FROM shipments WHERE status='delivered' AND actual_days IS NOT NULL GROUP BY actual_days ORDER BY actual_days").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/delivery/ontime-trend")
def ontime_trend():
    days = request.args.get("days", 30, type=int)
    db = get_db()
    since = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.execute("""SELECT DATE(delivered_at) as date, COUNT(*) as total,
        SUM(CASE WHEN actual_days <= quoted_days THEN 1 ELSE 0 END) as on_time
        FROM shipments WHERE status='delivered' AND delivered_at >= ?
        GROUP BY DATE(delivered_at) ORDER BY date""", (since,)).fetchall()
    return jsonify([{"date": r["date"], "rate": round(r["on_time"]/r["total"]*100, 1) if r["total"] else 0} for r in rows])


@app.route("/api/regions/volume")
def regions_volume():
    db = get_db()
    rows = db.execute("""SELECT destination_region as region, COUNT(*) as shipments,
        ROUND(SUM(shipping_cost + insurance_cost), 2) as revenue,
        ROUND(AVG(actual_days), 1) as avg_days,
        SUM(CASE WHEN status='delivered' AND actual_days <= quoted_days THEN 1 ELSE 0 END) as on_time,
        SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) as delivered
        FROM shipments GROUP BY destination_region ORDER BY shipments DESC""").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["on_time_rate"] = round(d["on_time"]/d["delivered"]*100, 1) if d["delivered"] else 0
        result.append(d)
    return jsonify(result)


@app.route("/api/regions/top-states")
def top_states():
    db = get_db()
    rows = db.execute("SELECT destination_state as state, COUNT(*) as count FROM shipments GROUP BY destination_state ORDER BY count DESC LIMIT 15").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/routes/popular")
def popular_routes():
    db = get_db()
    rows = db.execute("""SELECT w.region as origin, s.destination_region as destination, COUNT(*) as volume,
        ROUND(AVG(s.shipping_cost), 2) as avg_cost, ROUND(AVG(s.actual_days), 1) as avg_days
        FROM shipments s JOIN warehouses w ON s.origin_warehouse_id = w.id
        GROUP BY w.region, s.destination_region ORDER BY volume DESC LIMIT 20""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/costs/breakdown")
def cost_breakdown():
    db = get_db()
    by_service = db.execute("""SELECT service_level, ROUND(AVG(shipping_cost),2) as avg_shipping,
        ROUND(AVG(insurance_cost),2) as avg_insurance, ROUND(AVG(weight_lbs),1) as avg_weight, COUNT(*) as volume
        FROM shipments GROUP BY service_level""").fetchall()
    by_weight = db.execute("""SELECT
        CASE WHEN weight_lbs<1 THEN '< 1 lb' WHEN weight_lbs<5 THEN '1-5 lbs'
        WHEN weight_lbs<20 THEN '5-20 lbs' WHEN weight_lbs<50 THEN '20-50 lbs' ELSE '50+ lbs' END as weight_bracket,
        COUNT(*) as count, ROUND(AVG(shipping_cost),2) as avg_cost
        FROM shipments GROUP BY weight_bracket ORDER BY MIN(weight_lbs)""").fetchall()
    return jsonify({"by_service": [dict(r) for r in by_service], "by_weight": [dict(r) for r in by_weight]})


@app.route("/api/revenue/daily")
def revenue_daily():
    days = request.args.get("days", 30, type=int)
    db = get_db()
    since = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = db.execute("""SELECT DATE(created_at) as date, ROUND(SUM(shipping_cost),2) as shipping,
        ROUND(SUM(insurance_cost),2) as insurance FROM shipments WHERE created_at >= ?
        GROUP BY DATE(created_at) ORDER BY date""", (since,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/claims/summary")
def claims_summary():
    db = get_db()
    by_type = db.execute("SELECT type, COUNT(*) as count FROM claims GROUP BY type ORDER BY count DESC").fetchall()
    by_reason = db.execute("SELECT reason, COUNT(*) as count FROM claims GROUP BY reason ORDER BY count DESC LIMIT 10").fetchall()
    by_status = db.execute("SELECT status, COUNT(*) as count FROM claims GROUP BY status").fetchall()
    total_paid = round(db.execute("SELECT COALESCE(SUM(amount),0) FROM claims WHERE status='resolved'").fetchone()[0], 2)
    return jsonify({"by_type": [dict(r) for r in by_type], "by_reason": [dict(r) for r in by_reason],
                     "by_status": [dict(r) for r in by_status], "total_paid": total_paid})


@app.route("/api/shipments/recent")
def shipments_recent():
    limit = request.args.get("limit", 30, type=int)
    db = get_db()
    rows = db.execute("""SELECT s.id, s.tracking_number, s.status, s.service_level, s.package_type,
        s.weight_lbs, s.shipping_cost, s.insurance_cost, s.quoted_days, s.actual_days,
        s.destination_city, s.destination_state, s.created_at, s.delivered_at,
        cu.name as customer_name, cu.company, ca.name as carrier_name
        FROM shipments s JOIN customers cu ON s.customer_id = cu.id
        JOIN carriers ca ON s.carrier_id = ca.id ORDER BY s.created_at DESC LIMIT ?""", (limit,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/warehouses")
def warehouses():
    db = get_db()
    rows = db.execute("""SELECT w.*, COUNT(s.id) as shipments_out FROM warehouses w
        LEFT JOIN shipments s ON s.origin_warehouse_id = w.id GROUP BY w.id ORDER BY shipments_out DESC""").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["utilization"] = round(d["current_load"]/d["capacity"]*100, 1) if d["capacity"] else 0
        result.append(d)
    return jsonify(result)


@app.route("/api/customers/top")
def top_customers():
    db = get_db()
    rows = db.execute("""SELECT cu.name, cu.company, cu.tier, cu.city, cu.state,
        COUNT(s.id) as shipments, ROUND(SUM(s.shipping_cost + s.insurance_cost),2) as total_spent,
        ROUND(AVG(s.shipping_cost),2) as avg_cost
        FROM customers cu JOIN shipments s ON s.customer_id = cu.id
        GROUP BY cu.id ORDER BY total_spent DESC LIMIT 20""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/customers/by-tier")
def customers_by_tier():
    db = get_db()
    rows = db.execute("""SELECT cu.tier, COUNT(DISTINCT cu.id) as customers, COUNT(s.id) as shipments,
        ROUND(SUM(s.shipping_cost + s.insurance_cost),2) as revenue
        FROM customers cu LEFT JOIN shipments s ON s.customer_id = cu.id
        GROUP BY cu.tier ORDER BY revenue DESC""").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/funnel")
def shipping_funnel():
    db = get_db()
    steps = [("label_created","Label Created"),("picked_up","Picked Up"),("in_transit","In Transit"),
             ("out_for_delivery","Out for Delivery"),("delivered","Delivered")]
    results = []
    for val, label in steps:
        count = db.execute("SELECT COUNT(*) FROM shipment_events WHERE event_type=?", (val,)).fetchone()[0]
        results.append({"step": label, "count": count})
    return jsonify(results)


@app.route("/api/carriers/list")
def list_carriers():
    db = get_db()
    rows = db.execute("SELECT * FROM carriers WHERE active=1 ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])


# ============================================================
#  ONBOARDING & PRICING
# ============================================================

PLATFORM_CATALOG = [
    {"key": "shopify", "name": "Shopify", "category": "ecommerce", "difficulty": 1, "free": True, "description": "Sync orders and inventory from your Shopify store"},
    {"key": "woocommerce", "name": "WooCommerce", "category": "ecommerce", "difficulty": 1, "free": True, "description": "Connect your WordPress WooCommerce store"},
    {"key": "bigcommerce", "name": "BigCommerce", "category": "ecommerce", "difficulty": 1, "free": True, "description": "Import orders from BigCommerce"},
    {"key": "amazon", "name": "Amazon Seller", "category": "marketplace", "difficulty": 2, "free": False, "description": "Sync Amazon Seller Central orders"},
    {"key": "ebay", "name": "eBay", "category": "marketplace", "difficulty": 2, "free": True, "description": "Connect your eBay seller account"},
    {"key": "etsy", "name": "Etsy", "category": "marketplace", "difficulty": 1, "free": True, "description": "Import Etsy shop orders"},
    {"key": "walmart", "name": "Walmart Marketplace", "category": "marketplace", "difficulty": 2, "free": False, "description": "Sync Walmart marketplace orders"},
    {"key": "stripe", "name": "Stripe", "category": "payments", "difficulty": 1, "free": True, "description": "Track payments and revenue via Stripe"},
    {"key": "paypal_business", "name": "PayPal Business", "category": "payments", "difficulty": 1, "free": True, "description": "Connect PayPal for payment tracking"},
    {"key": "square", "name": "Square", "category": "payments", "difficulty": 1, "free": True, "description": "Sync Square POS transactions"},
    {"key": "quickbooks", "name": "QuickBooks", "category": "accounting", "difficulty": 2, "free": False, "description": "Sync invoices and expenses with QuickBooks"},
    {"key": "xero", "name": "Xero", "category": "accounting", "difficulty": 2, "free": False, "description": "Connect Xero for accounting integration"},
    {"key": "google_analytics", "name": "Google Analytics", "category": "analytics", "difficulty": 1, "free": True, "description": "Track website traffic and conversions"},
    {"key": "google_sheets", "name": "Google Sheets", "category": "productivity", "difficulty": 1, "free": True, "description": "Export data to Google Sheets automatically"},
    {"key": "slack", "name": "Slack", "category": "communication", "difficulty": 1, "free": True, "description": "Get shipping alerts in Slack channels"},
    {"key": "hubspot", "name": "HubSpot", "category": "crm", "difficulty": 2, "free": False, "description": "Sync customer data with HubSpot CRM"},
    {"key": "salesforce", "name": "Salesforce", "category": "crm", "difficulty": 3, "free": False, "description": "Enterprise CRM integration with Salesforce"},
    {"key": "zapier", "name": "Zapier", "category": "automation", "difficulty": 1, "free": True, "description": "Connect 5000+ apps through Zapier"},
    {"key": "shipstation", "name": "ShipStation", "category": "shipping", "difficulty": 2, "free": False, "description": "Sync with ShipStation for multi-carrier shipping"},
    {"key": "easypost", "name": "EasyPost", "category": "shipping", "difficulty": 3, "free": False, "description": "Advanced shipping API integration"},
    {"key": "customs_api", "name": "Customs / Trade API", "category": "international", "difficulty": 3, "free": False, "description": "Automate customs declarations and duties"},
    {"key": "warehouse_mgmt", "name": "Warehouse Management (WMS)", "category": "logistics", "difficulty": 3, "free": False, "description": "Connect your WMS for inventory sync"},
    {"key": "erp_sap", "name": "SAP ERP", "category": "enterprise", "difficulty": 3, "free": False, "description": "Full SAP integration for enterprise logistics"},
    {"key": "erp_oracle", "name": "Oracle NetSuite", "category": "enterprise", "difficulty": 3, "free": False, "description": "Oracle NetSuite ERP integration"},
]

USE_CASE_CATALOG = [
    {"key": "domestic_shipping", "name": "Domestic Shipping", "icon": "truck", "description": "Ship within the US"},
    {"key": "international_shipping", "name": "International / Overseas Shipping", "icon": "globe", "description": "Ship internationally with customs handling"},
    {"key": "ecommerce", "name": "E-Commerce", "icon": "cart", "description": "Online store order fulfillment"},
    {"key": "dropshipping", "name": "Dropshipping", "icon": "box", "description": "Dropship products from suppliers"},
    {"key": "marketplace", "name": "Marketplace Selling", "icon": "store", "description": "Sell on Amazon, eBay, Etsy, etc."},
    {"key": "wholesale_b2b", "name": "Wholesale / B2B", "icon": "building", "description": "Bulk and business-to-business shipping"},
    {"key": "fulfillment_3pl", "name": "Fulfillment / 3PL", "icon": "warehouse", "description": "Third-party logistics and fulfillment"},
    {"key": "subscription_box", "name": "Subscription Box", "icon": "refresh", "description": "Recurring subscription box shipments"},
    {"key": "returns_management", "name": "Returns Management", "icon": "return", "description": "Manage and process customer returns"},
    {"key": "freight_ltl", "name": "Freight / LTL", "icon": "freight", "description": "Large freight and less-than-truckload"},
    {"key": "cold_chain", "name": "Cold Chain / Perishables", "icon": "snowflake", "description": "Temperature-controlled shipping"},
    {"key": "hazmat", "name": "Hazardous Materials", "icon": "warning", "description": "Regulated hazmat shipping compliance"},
]

PERSONAL_TIERS = [
    {"key": "free", "name": "Free", "price": 0, "description": "Get started with basic shipping analytics",
     "features": ["Up to 50 shipments/month", "2 platform connections", "Basic analytics dashboard", "Email support", "1 user"],
     "max_shipments": 50, "max_platforms": 2, "max_team": 1},
    {"key": "starter", "name": "Starter", "price": 19, "description": "For growing sellers and small businesses",
     "features": ["Up to 500 shipments/month", "5 platform connections", "Full analytics suite", "Priority email support", "Rate calculator", "1 user"],
     "max_shipments": 500, "max_platforms": 5, "max_team": 1},
    {"key": "pro", "name": "Pro", "price": 49, "description": "For serious sellers who need advanced tools",
     "features": ["Up to 5,000 shipments/month", "15 platform connections", "Advanced analytics & reports", "Priority support + chat", "API access", "Custom alerts", "3 users"],
     "max_shipments": 5000, "max_platforms": 15, "max_team": 3},
    {"key": "business", "name": "Business", "price": 99, "description": "For teams managing high-volume shipping",
     "features": ["Up to 25,000 shipments/month", "Unlimited platform connections", "All analytics features", "Phone + chat support", "Full API access", "Custom integrations", "10 users", "Priority carrier rates"],
     "max_shipments": 25000, "max_platforms": 999, "max_team": 10},
]

ENTERPRISE_SIZE_PRICING = [
    {"size": "1-50", "label": "Small (1-50 employees)", "min_price": 199, "max_price": 499},
    {"size": "51-200", "label": "Mid-size (51-200 employees)", "min_price": 499, "max_price": 1499},
    {"size": "201-500", "label": "Large (201-500 employees)", "min_price": 1499, "max_price": 2999},
    {"size": "501-1000", "label": "Enterprise (501-1000 employees)", "min_price": 2999, "max_price": 4999},
    {"size": "1000+", "label": "Global (1000+ employees)", "min_price": 4999, "max_price": 9999},
]


@app.route("/api/onboarding/catalogs")
def onboarding_catalogs():
    return jsonify({
        "platforms": PLATFORM_CATALOG,
        "use_cases": USE_CASE_CATALOG,
        "personal_tiers": PERSONAL_TIERS,
        "enterprise_pricing": ENTERPRISE_SIZE_PRICING,
    })


@app.route("/api/onboarding/save-use-cases", methods=["POST"])
@login_required
def save_use_cases():
    data = request.json
    use_cases = data.get("use_cases", [])
    db = get_db()
    aid = get_account_id()
    db.execute("DELETE FROM account_use_cases WHERE account_id=?", (aid,))
    for uc in use_cases:
        db.execute("INSERT INTO account_use_cases (account_id, use_case) VALUES (?,?)", (aid, uc))
    db.commit()
    return jsonify({"ok": True, "count": len(use_cases)})


@app.route("/api/onboarding/save-platforms", methods=["POST"])
@login_required
def save_platforms():
    data = request.json
    platforms = data.get("platforms", [])
    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()
    db.execute("DELETE FROM connected_platforms WHERE account_id=?", (aid,))
    for pkey in platforms:
        pinfo = next((p for p in PLATFORM_CATALOG if p["key"] == pkey), None)
        if pinfo:
            db.execute("""INSERT INTO connected_platforms (account_id, platform_key, platform_name, status, connected_at)
                          VALUES (?,?,?,?,?)""", (aid, pkey, pinfo["name"], "connected", now))
    db.commit()
    return jsonify({"ok": True, "count": len(platforms)})


@app.route("/api/onboarding/save-plan", methods=["POST"])
@login_required
def save_plan():
    data = request.json
    plan = data.get("plan", "free")
    db = get_db()
    aid = get_account_id()
    db.execute("UPDATE accounts SET plan=? WHERE id=?", (plan, aid))
    db.commit()
    return jsonify({"ok": True, "plan": plan})


@app.route("/api/onboarding/enterprise-questionnaire", methods=["POST"])
@login_required
def submit_enterprise_questionnaire():
    data = request.json
    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()

    db.execute("""INSERT INTO enterprise_questionnaires
        (account_id, company_name, company_size, industry, monthly_shipments, annual_revenue,
         team_size, current_tools, pain_points, timeline, additional_notes, submitted_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid, data.get("company_name"), data.get("company_size"), data.get("industry"),
         data.get("monthly_shipments"), data.get("annual_revenue"), data.get("team_size"),
         data.get("current_tools"), data.get("pain_points"), data.get("timeline"),
         data.get("additional_notes"), now))

    # Calculate quote based on company size
    size = data.get("company_size", "1-50")
    pricing = next((p for p in ENTERPRISE_SIZE_PRICING if p["size"] == size), ENTERPRISE_SIZE_PRICING[0])
    # Base quote on midpoint, adjusted by shipment volume
    base = (pricing["min_price"] + pricing["max_price"]) / 2
    shipment_vol = data.get("monthly_shipments", "0-500")
    if "5000" in shipment_vol or "10000" in shipment_vol:
        base *= 1.3
    elif "1000" in shipment_vol:
        base *= 1.1
    quote = round(min(max(base, pricing["min_price"]), pricing["max_price"]), 0)

    db.execute("""UPDATE accounts SET company_size=?, industry=?, monthly_shipments=?, annual_revenue=?,
                  team_size=?, enterprise_quote=?, enterprise_quote_status='quoted', company=?
                  WHERE id=?""",
        (data.get("company_size"), data.get("industry"), data.get("monthly_shipments"),
         data.get("annual_revenue"), data.get("team_size"), quote, data.get("company_name"), aid))
    db.commit()

    return jsonify({"ok": True, "quote": quote, "min_price": pricing["min_price"], "max_price": pricing["max_price"]})


@app.route("/api/onboarding/accept-quote", methods=["POST"])
@login_required
def accept_enterprise_quote():
    db = get_db()
    aid = get_account_id()
    db.execute("UPDATE accounts SET enterprise_quote_status='accepted' WHERE id=?", (aid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/onboarding/request-meeting", methods=["POST"])
@login_required
def request_meeting():
    data = request.json
    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()
    db.execute("""INSERT INTO meeting_requests (account_id, contact_name, contact_email, contact_phone,
                  preferred_date, preferred_time, timezone, notes, created_at)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
        (aid, data.get("contact_name", ""), data.get("contact_email", ""),
         data.get("contact_phone"), data.get("preferred_date"), data.get("preferred_time"),
         data.get("timezone", "EST"), data.get("notes"), now))
    db.execute("UPDATE accounts SET enterprise_quote_status='meeting_requested' WHERE id=?", (aid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/onboarding/complete", methods=["POST"])
@login_required
def complete_onboarding():
    db = get_db()
    aid = get_account_id()
    db.execute("UPDATE accounts SET onboarding_complete=1 WHERE id=?", (aid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/team", methods=["GET"])
@login_required
def list_team():
    db = get_db()
    aid = get_account_id()
    acct = db.execute("SELECT role, account_type FROM accounts WHERE id=?", (aid,)).fetchone()
    if acct["account_type"] != "enterprise":
        return jsonify({"error": "Team management is an enterprise feature"}), 403
    members = db.execute("SELECT * FROM team_members WHERE account_id=? ORDER BY invited_at DESC", (aid,)).fetchall()
    return jsonify([dict(m) for m in members])


@app.route("/api/team", methods=["POST"])
@login_required
def invite_team_member():
    data = request.json
    db = get_db()
    aid = get_account_id()
    now = _now().isoformat()
    acct = db.execute("SELECT account_type FROM accounts WHERE id=?", (aid,)).fetchone()
    if acct["account_type"] != "enterprise":
        return jsonify({"error": "Team management is an enterprise feature"}), 403
    db.execute("""INSERT INTO team_members (account_id, email, name, role, invited_at)
                  VALUES (?,?,?,?,?)""",
        (aid, data.get("email"), data.get("name", ""), data.get("role", "viewer"), now))
    db.commit()
    return jsonify({"ok": True}), 201


@app.route("/api/pricing/tiers")
def get_pricing_tiers():
    return jsonify({
        "personal": PERSONAL_TIERS,
        "enterprise": ENTERPRISE_SIZE_PRICING,
        "enterprise_features": [
            "Unlimited shipments", "Unlimited platform connections", "Unlimited team members",
            "Admin roles: Owner, Admin, Manager, Analyst, Viewer",
            "SSO / SAML authentication", "Dedicated account manager",
            "Custom analytics & reporting", "SLA guarantee",
            "Priority API rate limits", "Onboarding & training",
            "Custom integrations", "Audit log & compliance"
        ]
    })


# ============================================================
#  STARTUP
# ============================================================

def print_banner():
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    RED = "\033[91m"
    RESET = "\033[0m"
    UNDERLINE = "\033[4m"

    print(f"""
{BLUE}{BOLD}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ███████╗██╗  ██╗██╗██████╗ ███████╗██╗      ██████╗ ██╗    ██╗║
║   ██╔════╝██║  ██║██║██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║║
║   ███████╗███████║██║██████╔╝█████╗  ██║     ██║   ██║██║ █╗ ██║║
║   ╚════██║██╔══██║██║██╔═══╝ ██╔══╝  ██║     ██║   ██║██║███╗██║║
║   ███████║██║  ██║██║██║     ██║     ███████╗╚██████╔╝╚███╔███╔╝║
║   ╚══════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝║
║                                                                  ║
║          {CYAN}Shipping Analytics Platform v2.0{BLUE}                      ║
╚══════════════════════════════════════════════════════════════════╝{RESET}

{BOLD}{CYAN}━━━ What is ShipFlow? ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}

  ShipFlow is a {BOLD}full-featured shipping analytics and management{RESET}
  platform for businesses that ship products. Think of it as your
  command center for everything shipping.

{BOLD}{GREEN}━━━ Core Features ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}

  {GREEN}✓{RESET} {BOLD}Dashboard & Analytics{RESET}
    Real-time KPIs: shipment volume, revenue, on-time rates,
    delivery speed, returns, and exceptions — all visualized
    with interactive charts.

  {GREEN}✓{RESET} {BOLD}Shipment Management{RESET}
    Create shipments, track packages in real-time, view the
    shipping funnel (label → pickup → transit → delivery).

  {GREEN}✓{RESET} {BOLD}Carrier Performance{RESET}
    Compare 8 carriers (FedEx, UPS, USPS, DHL, etc.) by
    on-time %, avg delivery days, cost, and return rates.

  {GREEN}✓{RESET} {BOLD}Rate Calculator{RESET}
    Get instant quotes across all carriers/service levels.
    Supports ground, express, overnight, economy, and freight.

  {GREEN}✓{RESET} {BOLD}Geographic Analytics{RESET}
    See where you're shipping — regional volume, top states,
    popular routes, and regional performance comparisons.

  {GREEN}✓{RESET} {BOLD}Cost Analysis{RESET}
    Revenue breakdown (shipping vs insurance), cost by service
    level, cost by weight bracket — find where your money goes.

{BOLD}{YELLOW}━━━ Account & Payments ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}

  {YELLOW}${RESET} {BOLD}Account System{RESET}
    Sign up, log in, manage your profile, and get an API key
    for programmatic access.

  {YELLOW}${RESET} {BOLD}Payment Methods{RESET} — Connect how you pay:
    {DIM}├─{RESET} {BOLD}Bank Accounts{RESET}    (ACH transfers, routing + account #)
    {DIM}├─{RESET} {BOLD}Credit Cards{RESET}     (Visa, Mastercard, Amex, Discover)
    {DIM}├─{RESET} {BOLD}Debit Cards{RESET}      (direct bank-linked cards)
    {DIM}├─{RESET} {BOLD}PayPal{RESET}           (link your PayPal account)
    {DIM}└─{RESET} {BOLD}Wire Transfer{RESET}    (for enterprise/large invoices)

  {YELLOW}${RESET} {BOLD}Billing & Invoices{RESET}
    Monthly invoices auto-generated from your shipping usage.
    Pay invoices directly from the dashboard, view history,
    track outstanding balances.

{BOLD}{MAGENTA}━━━ Additional Features ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}

  {MAGENTA}◆{RESET} {BOLD}Claims Management{RESET}    — File and track damage/loss/delay claims
  {MAGENTA}◆{RESET} {BOLD}Warehouse Monitoring{RESET} — Utilization, capacity, outbound volume
  {MAGENTA}◆{RESET} {BOLD}Customer Insights{RESET}   — Top customers, tier analysis, spend
  {MAGENTA}◆{RESET} {BOLD}Saved Addresses{RESET}     — Quick-ship to frequent destinations
  {MAGENTA}◆{RESET} {BOLD}Notifications{RESET}       — Payment confirmations, delivery alerts
  {MAGENTA}◆{RESET} {BOLD}Activity Log{RESET}        — Full audit trail of all actions
  {MAGENTA}◆{RESET} {BOLD}Public Tracking{RESET}     — Anyone can track via /api/track/<id>
  {MAGENTA}◆{RESET} {BOLD}API Access{RESET}          — Full REST API with API key auth

{BOLD}{RED}━━━ Quick Start ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}

  {DIM}Demo account:{RESET}
    Email:    {BOLD}admin@shipflow.com{RESET}
    Password: {BOLD}admin123{RESET}

  {DIM}API key:{RESET}  Use the API key from your account settings.
            Pass it as {CYAN}X-API-Key{RESET} header in requests.

  {DIM}Create a shipment:{RESET}
    {CYAN}POST /api/shipments/create{RESET}
    {DIM}{{"destination_city":"Miami","destination_state":"FL",
     "weight_lbs":5,"service_level":"express","carrier_id":1}}{RESET}

  {DIM}Track a package:{RESET}
    {CYAN}GET /api/track/SF<tracking_number>{RESET}

  {DIM}Get a rate quote:{RESET}
    {CYAN}POST /api/rates/calculate{RESET}
    {DIM}{{"weight":10,"origin_region":"Northeast","destination_region":"West"}}{RESET}

{BOLD}{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}
""")


def seed_pricing_tiers():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM pricing_tiers")
    if c.fetchone()[0] == 0:
        for i, t in enumerate(PERSONAL_TIERS):
            c.execute("""INSERT INTO pricing_tiers (tier_key, name, account_type, price_monthly, description, features,
                         max_shipments, max_platforms, max_team_members, sort_order)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (t["key"], t["name"], "personal", t["price"], t["description"],
                 json.dumps(t["features"]), t["max_shipments"], t["max_platforms"], t["max_team"], i))
        conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_pricing_tiers()
    print_banner()
    print(f"\033[92m\033[1m  ▶ Server running at: http://localhost:8080\033[0m")
    print(f"\033[2m  Press Ctrl+C to stop\033[0m\n")
    app.run(debug=False, port=8080)

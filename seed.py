"""Generate realistic shipping analytics data with accounts, payments, billing."""
import sqlite3
import random
import os
import secrets
import hashlib
import string
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")

CARRIERS = [
    ("FedEx", "national", "support@fedex.com", "1-800-463-3339"),
    ("UPS", "national", "support@ups.com", "1-800-742-5877"),
    ("USPS", "national", "support@usps.gov", "1-800-275-8777"),
    ("DHL Express", "international", "support@dhl.com", "1-800-225-5345"),
    ("OnTrac", "regional", "support@ontrac.com", "1-800-334-5000"),
    ("LaserShip", "regional", "support@lasership.com", "1-804-414-2590"),
    ("Amazon Logistics", "national", "support@amazon.com", "1-888-280-4331"),
    ("XPO Logistics", "freight", "support@xpo.com", "1-844-742-5976"),
]

REGIONS = {
    "Northeast": {"states": ["NY","NJ","PA","MA","CT","NH","VT","ME","RI"],
                  "cities": ["New York","Boston","Philadelphia","Newark","Hartford"],
                  "zips": ["10001","02101","19103","07102","06103"]},
    "Southeast": {"states": ["FL","GA","NC","SC","VA","TN","AL"],
                  "cities": ["Miami","Atlanta","Charlotte","Nashville","Tampa"],
                  "zips": ["33101","30301","28201","37201","33601"]},
    "Midwest": {"states": ["IL","OH","MI","IN","WI","MN","MO","IA"],
                "cities": ["Chicago","Detroit","Columbus","Indianapolis","Milwaukee"],
                "zips": ["60601","48201","43201","46201","53201"]},
    "Southwest": {"states": ["TX","AZ","NM","OK","NV"],
                  "cities": ["Houston","Dallas","Phoenix","San Antonio","Austin"],
                  "zips": ["77001","75201","85001","78201","73301"]},
    "West": {"states": ["CA","WA","OR","CO","UT"],
             "cities": ["Los Angeles","San Francisco","Seattle","Denver","Portland"],
             "zips": ["90001","94101","98101","80201","97201"]},
}

WAREHOUSES = [
    ("East Hub", "Newark", "NJ", "Northeast", 5000),
    ("Southeast DC", "Atlanta", "GA", "Southeast", 4000),
    ("Central Hub", "Chicago", "IL", "Midwest", 6000),
    ("Texas DC", "Dallas", "TX", "Southwest", 4500),
    ("West Coast Hub", "Los Angeles", "CA", "West", 5500),
    ("Pacific NW", "Seattle", "WA", "West", 3000),
]

FIRST_NAMES = ["Emma","Liam","Olivia","Noah","Ava","James","Sophia","Lucas",
               "Mia","Mason","Isabella","Ethan","Charlotte","Logan","Amelia",
               "Alex","Harper","Jack","Ella","Benjamin","Luna","Henry","Chloe",
               "Sebastian","Lily","Daniel","Grace","Matthew","Zoe","Owen"]

LAST_NAMES = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller",
              "Davis","Rodriguez","Martinez","Hernandez","Lopez","Gonzalez",
              "Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin"]

COMPANIES = [None,None,None,"Acme Corp","TechStart Inc","Global Goods LLC",
             "Fresh Foods Co","StyleHouse","HomeBase Supply","Peak Outdoors",
             "DataFlow Inc","GreenLeaf Brands","BlueSky Retail","Quantum Parts"]

SERVICE_LEVELS = [
    ("ground", 5, 7, 8.99, 24.99),
    ("express", 2, 3, 18.99, 44.99),
    ("overnight", 1, 1, 34.99, 79.99),
    ("economy", 7, 10, 4.99, 14.99),
    ("freight", 5, 14, 49.99, 299.99),
]

PACKAGE_TYPES = ["parcel","envelope","box_small","box_medium","box_large","pallet","tube","flat_rate"]
CLAIM_TYPES = ["damage","lost","delay","wrong_address","theft"]
CLAIM_REASONS = ["Package arrived crushed","Contents broken on arrival","Never received package",
    "Delivered to wrong address","Package stolen from porch","Significant delay beyond SLA",
    "Missing items in package","Water damage during transit","Label fell off in transit","Refused by recipient"]

STATUSES = ["label_created","picked_up","in_transit","out_for_delivery","delivered","returned","exception"]
STATUS_WEIGHTS = [5, 3, 12, 4, 65, 6, 5]

BANK_NAMES = ["Chase","Bank of America","Wells Fargo","Citibank","US Bank","Capital One","TD Bank","PNC Bank"]
CARD_BRANDS = ["Visa","Mastercard","Amex","Discover"]


def gen_tracking():
    prefix = random.choice(["SHP","FX","UP","DH","AM","SF"])
    return f"{prefix}{''.join(random.choices(string.digits, k=12))}"


def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()


def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for t in ["meeting_requests","enterprise_questionnaires","team_members","connected_platforms",
              "account_use_cases","pricing_tiers","activity_log","notifications","invoice_lines",
              "invoices","shipping_rates","saved_addresses","payment_methods","shipment_events",
              "claims","shipments","customers","warehouses","carriers","accounts"]:
        c.execute(f"DELETE FROM {t}")

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=120)

    # ===== ACCOUNTS =====
    accounts = []

    # Admin/demo account — all seed data is tied to this account
    salt = secrets.token_hex(16)
    api_key = "sf_" + secrets.token_hex(24)
    c.execute("""INSERT INTO accounts (email, password_hash, salt, name, company, phone, role, plan, account_type, api_key, status, onboarding_complete, created_at, last_login)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              ("admin@shipflow.com", hash_pw("admin123", salt), salt, "Julian Grossman", "ShipFlow Inc",
               "555-0100", "admin", "enterprise", "enterprise", api_key, "active", 1, (now - timedelta(days=120)).isoformat(), now.isoformat()))
    demo_account_id = c.lastrowid
    accounts.append({"id": demo_account_id, "plan": "enterprise"})

    # More accounts (these are extra demo accounts, all data still tied to demo)
    for i in range(15):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        salt = secrets.token_hex(16)
        plan = random.choices(["starter","pro","enterprise_starter"], weights=[50,35,15])[0]
        acct_type = "enterprise" if "enterprise" in plan else "personal"
        created = start_date + timedelta(days=random.randint(0, 90))
        c.execute("""INSERT INTO accounts (email, password_hash, salt, name, company, phone, role, plan, account_type, api_key, status, onboarding_complete, created_at, last_login)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (f"{first.lower()}.{last.lower()}{i}@example.com", hash_pw("password123", salt), salt,
                   f"{first} {last}", random.choice([co for co in COMPANIES if co]),
                   f"555-{random.randint(1000,9999)}", "user", plan, acct_type, "sf_" + secrets.token_hex(24),
                   "active", 1, created.isoformat(), (now - timedelta(days=random.randint(0,7))).isoformat()))
        accounts.append({"id": c.lastrowid, "plan": plan})

    # ===== PAYMENT METHODS =====
    for acct in accounts:
        num_methods = random.randint(1, 3)
        for j in range(num_methods):
            ptype = random.choices(["bank_account","credit_card","debit_card","paypal","wire"],
                                   weights=[30,35,15,15,5])[0]
            last4 = ''.join(random.choices(string.digits, k=4))
            bank = random.choice(BANK_NAMES)
            brand = random.choice(CARD_BRANDS)
            created = start_date + timedelta(days=random.randint(0, 60))

            if ptype == "bank_account":
                label = f"{bank} ****{last4}"
                routing = "****" + ''.join(random.choices(string.digits, k=4))
            elif ptype in ("credit_card", "debit_card"):
                label = f"{brand} ****{last4}"
                routing = None
            elif ptype == "paypal":
                label = f"PayPal (user{acct['id']}@email.com)"
                routing = None
                bank = None
                brand = None
            else:
                label = f"Wire Transfer - {bank}"
                routing = "****" + ''.join(random.choices(string.digits, k=4))

            c.execute("""INSERT INTO payment_methods
                (account_id, type, label, provider, last_four, bank_name, routing_number_masked,
                 card_brand, exp_month, exp_year, billing_address, is_default, status, verified, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (acct["id"], ptype, label, bank or brand, last4, bank, routing,
                 brand if ptype in ("credit_card","debit_card") else None,
                 random.randint(1,12), random.randint(2026,2030),
                 f"{random.randint(100,9999)} Main St, Anytown, US",
                 1 if j == 0 else 0, "active", random.choice([0,1,1]), created.isoformat()))

    # ===== CARRIERS =====
    carrier_ids = []
    for name, ctype, email, phone in CARRIERS:
        c.execute("INSERT INTO carriers (name, type, contact_email, contact_phone, rating, active) VALUES (?,?,?,?,?,?)",
                  (name, ctype, email, phone, round(random.uniform(3.2, 4.9), 1), 1))
        carrier_ids.append(c.lastrowid)

    # ===== SHIPPING RATES =====
    for cid in carrier_ids:
        for svc_name, min_d, max_d, min_cost, max_cost in SERVICE_LEVELS:
            base = round(random.uniform(min_cost, (min_cost + max_cost) / 2), 2)
            per_lb = round(random.uniform(0.15, 0.85), 2)
            fuel = round(random.uniform(3, 12), 1)
            ins = round(random.uniform(1.5, 4), 1)
            # General rate (no specific region)
            c.execute("""INSERT INTO shipping_rates
                (carrier_id, service_level, origin_region, destination_region,
                 min_weight, max_weight, base_rate, per_lb_rate,
                 fuel_surcharge_pct, insurance_rate_pct, estimated_days_min, estimated_days_max)
                VALUES (?,?,NULL,NULL,?,?,?,?,?,?,?,?)""",
                (cid, svc_name, 0, 999, base, per_lb, fuel, ins, min_d, max_d))

    # ===== WAREHOUSES =====
    warehouse_ids = []
    for name, city, state, region, cap in WAREHOUSES:
        load = random.randint(int(cap * 0.4), int(cap * 0.9))
        c.execute("INSERT INTO warehouses (name, city, state, region, capacity, current_load) VALUES (?,?,?,?,?,?)",
                  (name, city, state, region, cap, load))
        warehouse_ids.append(c.lastrowid)

    # ===== CUSTOMERS =====
    customer_data = []
    for i in range(350):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        region = random.choice(list(REGIONS.keys()))
        rdata = REGIONS[region]
        tier = random.choices(["standard","premium","enterprise"], weights=[60,28,12])[0]
        created = start_date + timedelta(days=random.randint(0, 90))
        acct = random.choice(accounts)
        city = random.choice(rdata["cities"])
        state = random.choice(rdata["states"])
        c.execute("""INSERT INTO customers (account_id, name, email, company, phone, address, city, state, zip, region, tier, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (acct["id"], f"{first} {last}", f"{first.lower()}.{last.lower()}{i}@example.com",
                   random.choice(COMPANIES), f"555-{random.randint(1000,9999)}",
                   f"{random.randint(100,9999)} {random.choice(['Main','Oak','Elm','Pine','Cedar'])} St",
                   city, state, random.choice(rdata["zips"]), region, tier, created.isoformat()))
        customer_data.append({"id": c.lastrowid, "region": region, "tier": tier, "created": created, "account_id": acct["id"]})

    # ===== SHIPMENTS =====
    shipment_data = []
    for _ in range(2500):
        cust = random.choice(customer_data)
        dest_region = random.choice(list(REGIONS.keys()))
        dest_rdata = REGIONS[dest_region]
        dest_city = random.choice(dest_rdata["cities"])
        dest_state = random.choice(dest_rdata["states"])
        dest_zip = random.choice(dest_rdata["zips"])

        if random.random() < 0.4:
            wh_id = random.choice(warehouse_ids)
        else:
            same = [wid for wid, (_, _, _, reg, _) in zip(warehouse_ids, WAREHOUSES) if reg == dest_region]
            wh_id = random.choice(same) if same else random.choice(warehouse_ids)

        carrier_id = random.choice(carrier_ids)
        svc = random.choices(SERVICE_LEVELS, weights=[40, 25, 10, 15, 10])[0]
        svc_name, min_d, max_d, min_cost, max_cost = svc

        weight = round(random.uniform(0.3, 70), 1)
        if svc_name == "freight":
            weight = round(random.uniform(30, 200), 1)

        base_cost = round(random.uniform(min_cost, max_cost), 2)
        if weight > 20:
            base_cost += round(weight * 0.35, 2)
        insurance = round(random.uniform(0, 5.99), 2) if random.random() < 0.3 else 0
        declared = round(random.uniform(20, 500), 2) if insurance > 0 else 0

        status = random.choices(STATUSES, weights=STATUS_WEIGHTS)[0]
        quoted_days = random.randint(min_d, max_d)
        created = start_date + timedelta(days=random.randint(0, 120), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        if created > now:
            created = now - timedelta(hours=random.randint(1, 48))

        shipped_at = delivered_at = None
        actual_days = None

        if status in ("picked_up","in_transit","out_for_delivery","delivered","returned","exception"):
            shipped_at = (created + timedelta(hours=random.randint(1, 24))).isoformat()

        if status == "delivered":
            if random.random() < 0.78:
                actual_days = random.randint(max(1, min_d - 1), quoted_days)
            else:
                actual_days = random.randint(quoted_days + 1, quoted_days + 5)
            delivered_at = (created + timedelta(days=actual_days, hours=random.randint(8, 18))).isoformat()
        elif status == "returned":
            actual_days = random.randint(quoted_days + 2, quoted_days + 10)

        pkg_type = random.choice(PACKAGE_TYPES)
        if svc_name == "freight":
            pkg_type = "pallet"
        dims = f"{random.randint(4,36)}x{random.randint(4,24)}x{random.randint(2,18)}"

        c.execute("""INSERT INTO shipments
            (tracking_number, account_id, customer_id, carrier_id, origin_warehouse_id,
             destination_name, destination_address, destination_city, destination_state, destination_zip, destination_region,
             weight_lbs, dimensions, package_type, service_level, status, shipping_cost, insurance_cost,
             declared_value, quoted_days, actual_days, shipped_at, delivered_at, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (gen_tracking(), cust["account_id"], cust["id"], carrier_id, wh_id,
             f"Recipient {random.randint(1,999)}", f"{random.randint(100,9999)} Delivery Ave",
             dest_city, dest_state, dest_zip, dest_region,
             weight, dims, pkg_type, svc_name, status, base_cost, insurance,
             declared, quoted_days, actual_days, shipped_at, delivered_at,
             created.isoformat(), created.isoformat()))

        shipment_data.append({"id": c.lastrowid, "status": status, "created": created,
                               "account_id": cust["account_id"], "cost": base_cost + insurance})

    # ===== SHIPMENT EVENTS =====
    status_flow = ["label_created","picked_up","in_transit","out_for_delivery","delivered"]
    for sh in shipment_data:
        if sh["status"] in status_flow:
            target_idx = status_flow.index(sh["status"])
        elif sh["status"] == "returned":
            target_idx = 3
        elif sh["status"] == "exception":
            target_idx = random.randint(1, 3)
        else:
            target_idx = 0

        t = sh["created"]
        for i in range(target_idx + 1):
            c.execute("INSERT INTO shipment_events (shipment_id, event_type, description, created_at) VALUES (?,?,?,?)",
                      (sh["id"], status_flow[i], f"Package {status_flow[i].replace('_',' ')}", t.isoformat()))
            t += timedelta(hours=random.randint(4, 36))

        if sh["status"] == "returned":
            c.execute("INSERT INTO shipment_events (shipment_id, event_type, description, created_at) VALUES (?,?,?,?)",
                      (sh["id"], "returned", "Package returned to sender", t.isoformat()))
        elif sh["status"] == "exception":
            c.execute("INSERT INTO shipment_events (shipment_id, event_type, description, created_at) VALUES (?,?,?,?)",
                      (sh["id"], "exception", random.choice(["Address not found","Recipient refused","Weather delay","Customs hold"]), t.isoformat()))

    # ===== CLAIMS =====
    problem_shipments = [s for s in shipment_data if s["status"] in ("delivered","returned","exception")]
    for sh in random.sample(problem_shipments, min(120, len(problem_shipments))):
        ctype = random.choice(CLAIM_TYPES)
        reason = random.choice(CLAIM_REASONS)
        amount = round(random.uniform(15, 500), 2)
        status = random.choices(["open","investigating","resolved","denied"], weights=[25,20,40,15])[0]
        created = sh["created"] + timedelta(days=random.randint(1, 14))
        resolved = (created + timedelta(days=random.randint(3, 30))).isoformat() if status in ("resolved","denied") else None
        c.execute("""INSERT INTO claims (shipment_id, account_id, type, reason, description, amount, status, created_at, resolved_at)
                     VALUES (?,?,?,?,?,?,?,?,?)""",
                  (sh["id"], sh["account_id"], ctype, reason, f"Claim for {ctype}: {reason}",
                   amount if status == "resolved" else 0, status, created.isoformat(), resolved))

    # ===== INVOICES =====
    for acct in accounts:
        acct_shipments = [s for s in shipment_data if s["account_id"] == acct["id"]]
        if not acct_shipments:
            continue

        # Group by month and create invoices
        by_month = {}
        for s in acct_shipments:
            key = s["created"].strftime("%Y-%m")
            by_month.setdefault(key, []).append(s)

        pm = c.execute("SELECT id FROM payment_methods WHERE account_id=? AND is_default=1 LIMIT 1", (acct["id"],)).fetchone()
        pm_id = pm[0] if pm else None

        for month_key, month_ships in by_month.items():
            year, mon = month_key.split("-")
            period_start = f"{month_key}-01"
            if int(mon) == 12:
                period_end = f"{int(year)+1}-01-01"
            else:
                period_end = f"{year}-{int(mon)+1:02d}-01"

            subtotal = round(sum(s["cost"] for s in month_ships), 2)
            tax = round(subtotal * 0.08, 2)
            total = round(subtotal + tax, 2)
            inv_num = f"INV-{year}{mon}-{acct['id']:04d}"
            due_date = (datetime.strptime(period_end, "%Y-%m-%d") + timedelta(days=15)).isoformat()
            created_inv = (datetime.strptime(period_end, "%Y-%m-%d") + timedelta(days=1)).isoformat()

            # Older invoices are paid, recent ones pending
            if datetime.strptime(period_end, "%Y-%m-%d") < (now - timedelta(days=30)).replace(tzinfo=None):
                inv_status = "paid"
                paid_at = (datetime.strptime(period_end, "%Y-%m-%d") + timedelta(days=random.randint(5, 14))).isoformat()
            else:
                inv_status = random.choices(["paid","pending"], weights=[60,40])[0]
                paid_at = (datetime.strptime(period_end, "%Y-%m-%d") + timedelta(days=random.randint(3, 10))).isoformat() if inv_status == "paid" else None

            c.execute("""INSERT INTO invoices (account_id, invoice_number, period_start, period_end,
                         subtotal, tax, total, status, payment_method_id, paid_at, due_date, created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (acct["id"], inv_num, period_start, period_end, subtotal, tax, total,
                       inv_status, pm_id if inv_status == "paid" else None, paid_at, due_date, created_inv))
            inv_id = c.lastrowid

            # Invoice line items
            c.execute("""INSERT INTO invoice_lines (invoice_id, description, quantity, unit_price, total)
                         VALUES (?,?,?,?,?)""",
                      (inv_id, f"Shipping charges - {len(month_ships)} shipments", len(month_ships),
                       round(subtotal / len(month_ships), 2), subtotal))
            if tax > 0:
                c.execute("""INSERT INTO invoice_lines (invoice_id, description, quantity, unit_price, total)
                             VALUES (?,?,?,?,?)""",
                          (inv_id, "Sales tax (8%)", 1, tax, tax))

    # ===== SAVED ADDRESSES =====
    for acct in accounts:
        for _ in range(random.randint(1, 4)):
            region = random.choice(list(REGIONS.keys()))
            rdata = REGIONS[region]
            c.execute("""INSERT INTO saved_addresses (account_id, label, name, address, city, state, zip, phone, is_default, created_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (acct["id"], random.choice(["Home","Office","Warehouse","Store","HQ"]),
                       f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                       f"{random.randint(100,9999)} {random.choice(['Main','Oak','Elm','Pine','Maple'])} St",
                       random.choice(rdata["cities"]), random.choice(rdata["states"]),
                       random.choice(rdata["zips"]), f"555-{random.randint(1000,9999)}",
                       0, (now - timedelta(days=random.randint(1,60))).isoformat()))

    # ===== DEMO USE CASES & PLATFORMS (for demo account only) =====
    demo_use_cases = ["domestic_shipping", "international_shipping", "ecommerce", "marketplace", "wholesale_b2b"]
    for uc in demo_use_cases:
        c.execute("INSERT OR IGNORE INTO account_use_cases (account_id, use_case) VALUES (?,?)", (demo_account_id, uc))

    demo_platforms = [
        ("shopify", "Shopify"), ("amazon", "Amazon Seller"), ("stripe", "Stripe"),
        ("quickbooks", "QuickBooks"), ("slack", "Slack"), ("google_analytics", "Google Analytics")
    ]
    for pkey, pname in demo_platforms:
        c.execute("""INSERT OR IGNORE INTO connected_platforms (account_id, platform_key, platform_name, status, connected_at)
                     VALUES (?,?,?,?,?)""", (demo_account_id, pkey, pname, "connected", (now - timedelta(days=60)).isoformat()))

    # ===== NOTIFICATIONS (rich, contextual) =====

    # Gather real data to reference
    all_shipments_for_notifs = c.execute("""
        SELECT s.id, s.tracking_number, s.status, s.destination_city, s.destination_state,
               s.shipping_cost, s.weight_lbs, s.service_level, s.actual_days, s.quoted_days,
               s.account_id, s.carrier_id, ca.name as carrier_name, cu.name as customer_name
        FROM shipments s
        JOIN carriers ca ON s.carrier_id = ca.id
        JOIN customers cu ON s.customer_id = cu.id
        ORDER BY RANDOM() LIMIT 500
    """).fetchall()
    shipments_by_acct = {}
    for row in all_shipments_for_notifs:
        shipments_by_acct.setdefault(row[10], []).append(row)

    all_invoices_for_notifs = c.execute("SELECT * FROM invoices ORDER BY RANDOM() LIMIT 200").fetchall()
    invoices_by_acct = {}
    for row in all_invoices_for_notifs:
        invoices_by_acct.setdefault(row[1], []).append(row)

    all_claims_for_notifs = c.execute("""
        SELECT cl.*, s.tracking_number FROM claims cl
        JOIN shipments s ON cl.shipment_id = s.id ORDER BY RANDOM() LIMIT 100
    """).fetchall()
    claims_by_acct = {}
    for row in all_claims_for_notifs:
        claims_by_acct.setdefault(row[2], []).append(row)

    carrier_names_map = {r[0]: r[1] for r in c.execute("SELECT id, name FROM carriers").fetchall()}

    for acct in accounts:
        aid = acct["id"]
        acct_ships = shipments_by_acct.get(aid, [])
        acct_invs = invoices_by_acct.get(aid, [])
        acct_claims = claims_by_acct.get(aid, [])

        # -- Welcome notification (always) --
        welcome_time = now - timedelta(days=random.randint(60, 110))
        c.execute("""INSERT INTO notifications
            (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
             action_label, action_link, read, starred, archived, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, "system", "normal",
             "Welcome to ShipFlow!",
             "Your account is ready - here's how to get started",
             "Your ShipFlow account has been created and is ready to use.",
             """Welcome to ShipFlow! We're excited to have you on board.

Here's a quick guide to get you started:

1. ADD A PAYMENT METHOD
   Head to Payment Methods to link your bank account, credit card, or PayPal. This is required before you can create shipments.

2. SET UP YOUR ADDRESSES
   Save your frequent shipping destinations in Settings > Saved Addresses for faster shipment creation.

3. CREATE YOUR FIRST SHIPMENT
   Go to Create Shipment, fill in the recipient details, choose a carrier and service level, and you're good to go.

4. EXPLORE THE DASHBOARD
   Your Dashboard shows real-time analytics: shipment volume, revenue, delivery performance, and more.

5. GET YOUR API KEY
   Need to integrate ShipFlow with your systems? Grab your API key from My Account and check our API docs.

If you have any questions, our support team is available 24/7.

Happy shipping!
The ShipFlow Team""",
             "ShipFlow Onboarding", "account", aid,
             "Go to Dashboard", "/dashboard",
             1, 0, 0, welcome_time.isoformat()))

        # -- Shipment-related notifications --
        for sh in acct_ships[:8]:
            s_id, tracking, status, dest_city, dest_state = sh[0], sh[1], sh[2], sh[3], sh[4]
            cost, weight, svc, actual_d, quoted_d = sh[5], sh[6], sh[7], sh[8], sh[9]
            carrier_name, cust_name = sh[12], sh[13]
            created = now - timedelta(days=random.randint(0, 40), hours=random.randint(0, 23))

            if status == "delivered":
                on_time = actual_d and quoted_d and actual_d <= quoted_d
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "shipping", "normal",
                     f"Shipment Delivered - {tracking}",
                     f"Package to {dest_city}, {dest_state} has been delivered",
                     f"Your shipment {tracking} to {cust_name} in {dest_city}, {dest_state} has been delivered.",
                     f"""DELIVERY CONFIRMATION
---

Tracking Number:  {tracking}
Recipient:        {cust_name}
Destination:      {dest_city}, {dest_state}
Carrier:          {carrier_name}
Service Level:    {svc}

DELIVERY DETAILS
---
Status:           Delivered {"(On Time)" if on_time else "(Late)"}
Quoted Transit:   {quoted_d} business days
Actual Transit:   {actual_d} business days
Package Weight:   {weight} lbs
Shipping Cost:    ${cost:.2f}

{"Your package arrived on schedule. Great choice of carrier!" if on_time else f"This delivery was {actual_d - quoted_d} day(s) late. If this is unacceptable, you can file a delay claim from the Claims page."}

Thank you for shipping with ShipFlow.
---
This is an automated delivery confirmation from ShipFlow tracking systems.""",
                     f"{carrier_name} via ShipFlow", "shipment", s_id,
                     "Track Shipment", f"/tracking",
                     random.choice([0, 0, 1]), 0, 0, created.isoformat()))

            elif status == "in_transit":
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "shipping", "normal",
                     f"Package In Transit - {tracking}",
                     f"Shipment to {dest_city}, {dest_state} is on the move",
                     f"Your shipment {tracking} is in transit via {carrier_name}.",
                     f"""TRANSIT UPDATE
---

Tracking Number:  {tracking}
Recipient:        {cust_name}
Destination:      {dest_city}, {dest_state}
Carrier:          {carrier_name}
Service Level:    {svc}

SHIPMENT DETAILS
---
Current Status:   In Transit
Package Weight:   {weight} lbs
Shipping Cost:    ${cost:.2f}
Estimated:        {quoted_d} business day{"s" if quoted_d != 1 else ""}

Your package has been picked up by {carrier_name} and is currently in transit to {dest_city}, {dest_state}. You will receive another notification when the package is out for delivery.

You can track this shipment in real-time using the tracking number above.
---
ShipFlow Tracking System""",
                     f"{carrier_name} via ShipFlow", "shipment", s_id,
                     "Track Shipment", f"/tracking",
                     random.choice([0, 1]), 0, 0, created.isoformat()))

            elif status == "exception":
                reasons = ["Address verification failed - unable to locate recipient address",
                           "Weather delay - severe weather conditions in delivery area",
                           "Customs hold - package requires additional documentation",
                           "Recipient not available - delivery attempted, no one present"]
                reason = random.choice(reasons)
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "alert", "high",
                     f"DELIVERY EXCEPTION - {tracking}",
                     f"Action required: Shipment to {dest_city}, {dest_state} has an exception",
                     f"Shipment {tracking} has encountered a delivery exception and requires your attention.",
                     f"""URGENT: DELIVERY EXCEPTION
---

Tracking Number:  {tracking}
Recipient:        {cust_name}
Destination:      {dest_city}, {dest_state}
Carrier:          {carrier_name}

EXCEPTION DETAILS
---
Status:           Exception
Reason:           {reason}
Package Weight:   {weight} lbs
Service Level:    {svc}

WHAT TO DO NEXT
---
1. Verify the shipping address is correct
2. Contact the recipient to confirm availability
3. If the issue persists, you can:
   - Request a re-delivery attempt
   - Redirect the package to a new address
   - File a claim for service failure

If no action is taken within 5 business days, the package will be returned to the origin warehouse.

Need help? Contact ShipFlow support or file a claim from the Claims page.
---
ShipFlow Exception Alert System""",
                     "ShipFlow Alerts", "shipment", s_id,
                     "View Exception", f"/tracking",
                     random.choice([0, 0]), 1, 0, created.isoformat()))

            elif status == "returned":
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "alert", "high",
                     f"Package Returned - {tracking}",
                     f"Shipment to {dest_city}, {dest_state} is being returned",
                     f"Shipment {tracking} is being returned to sender.",
                     f"""RETURN NOTIFICATION
---

Tracking Number:  {tracking}
Recipient:        {cust_name}
Destination:      {dest_city}, {dest_state}
Carrier:          {carrier_name}

RETURN DETAILS
---
Status:           Returned to Sender
Package Weight:   {weight} lbs
Original Cost:    ${cost:.2f}

The carrier was unable to complete delivery and the package is being returned to your origin warehouse. Common reasons include:
- Incorrect or incomplete address
- Recipient refused delivery
- Multiple failed delivery attempts
- Package damaged beyond deliverability

NEXT STEPS
---
1. Once the package arrives at the warehouse, you'll receive a confirmation
2. You can reship the package with corrected information
3. If the return was due to carrier error, file a claim for a refund

Return shipping charges may apply depending on your plan and carrier agreement.
---
ShipFlow Returns System""",
                     "ShipFlow Returns", "shipment", s_id,
                     "File Claim", "/claims",
                     random.choice([0, 0, 1]), 0, 0, created.isoformat()))

        # -- Invoice notifications --
        for inv in acct_invs[:3]:
            inv_id, inv_num = inv[0], inv[2]
            period_start, period_end = inv[3], inv[4]
            subtotal, tax, total = inv[5], inv[6], inv[7]
            inv_status = inv[8]
            created = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 12))

            if inv_status == "paid":
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "billing", "normal",
                     f"Payment Confirmed - {inv_num}",
                     f"Payment of ${total:.2f} for invoice {inv_num} has been processed",
                     f"Your payment for invoice {inv_num} has been processed successfully.",
                     f"""PAYMENT RECEIPT
---

Invoice Number:   {inv_num}
Billing Period:   {period_start} to {period_end}

CHARGES
---
Shipping charges:    ${subtotal:.2f}
Tax:                 ${tax:.2f}
                     --------
Total Paid:          ${total:.2f}

Payment has been charged to your default payment method on file. This payment covers all shipping charges incurred during the billing period above.

You can view the full invoice breakdown in Billing > Invoices.

Thank you for your prompt payment!
---
ShipFlow Billing Department""",
                     "ShipFlow Billing", "invoice", inv_id,
                     "View Invoice", "/billing",
                     1, 0, 0, created.isoformat()))
            else:
                due = inv[11]
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "billing", "high",
                     f"Invoice Ready - {inv_num}",
                     f"Your invoice for ${total:.2f} is ready for payment",
                     f"Invoice {inv_num} for ${total:.2f} is due by {due}.",
                     f"""INVOICE NOTIFICATION
---

Invoice Number:   {inv_num}
Billing Period:   {period_start} to {period_end}
Due Date:         {due}

SUMMARY
---
Shipping charges:    ${subtotal:.2f}
Tax (8%):            ${tax:.2f}
                     --------
Total Due:           ${total:.2f}

PAYMENT OPTIONS
---
1. Pay now via the Billing page using your default payment method
2. Pay via bank transfer using the details in your account settings
3. Contact billing@shipflow.com for custom payment arrangements

Please ensure payment is made by the due date to avoid late fees. Accounts with invoices overdue by more than 30 days may have shipping services temporarily suspended.
---
ShipFlow Billing Department""",
                     "ShipFlow Billing", "invoice", inv_id,
                     "Pay Now", "/billing",
                     random.choice([0, 0]), 0, 0, created.isoformat()))

        # -- Claim notifications --
        for cl in acct_claims[:2]:
            cl_id, cl_ship_id = cl[0], cl[1]
            cl_type, cl_reason = cl[3], cl[4]
            cl_amount, cl_status = cl[6], cl[7]
            cl_tracking = cl[9]
            created = now - timedelta(days=random.randint(0, 20), hours=random.randint(0, 12))

            if cl_status == "resolved":
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "alert", "normal",
                     f"Claim Resolved - #{cl_id}",
                     f"Your {cl_type} claim for shipment {cl_tracking} has been resolved",
                     f"Claim #{cl_id} has been resolved. A refund of ${cl_amount:.2f} has been issued.",
                     f"""CLAIM RESOLUTION
---

Claim ID:         #{cl_id}
Tracking Number:  {cl_tracking}
Claim Type:       {cl_type.title()}
Original Reason:  {cl_reason}

RESOLUTION
---
Status:           Resolved
Refund Amount:    ${cl_amount:.2f}

Your claim has been reviewed and approved. A refund of ${cl_amount:.2f} will be credited to your default payment method within 5-7 business days.

If you have questions about this resolution, please contact our claims department at claims@shipflow.com with your claim ID.
---
ShipFlow Claims Department""",
                     "ShipFlow Claims", "claim", cl_id,
                     "View Claims", "/claims",
                     random.choice([0, 1]), 0, 0, created.isoformat()))
            elif cl_status == "investigating":
                c.execute("""INSERT INTO notifications
                    (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
                     action_label, action_link, read, starred, archived, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (aid, "alert", "normal",
                     f"Claim Under Review - #{cl_id}",
                     f"We're investigating your {cl_type} claim for {cl_tracking}",
                     f"Claim #{cl_id} is under investigation by our team.",
                     f"""CLAIM STATUS UPDATE
---

Claim ID:         #{cl_id}
Tracking Number:  {cl_tracking}
Claim Type:       {cl_type.title()}
Reason Filed:     {cl_reason}

STATUS
---
Current Status:   Under Investigation

Our claims team is actively reviewing your case. This process typically takes 3-5 business days and may involve:

1. Reviewing carrier scan data and delivery records
2. Contacting the carrier for additional information
3. Reviewing package insurance coverage
4. Verifying declared value documentation

You will be notified once a decision has been made. No further action is required from you at this time.

If you have additional evidence or information to support your claim, you can reply to this notification or email claims@shipflow.com.
---
ShipFlow Claims Department""",
                     "ShipFlow Claims", "claim", cl_id,
                     "View Claims", "/claims",
                     random.choice([0, 0]), 0, 0, created.isoformat()))

        # -- System notifications --
        # Weekly summary
        total_ships = len(acct_ships)
        total_cost = sum(s[5] for s in acct_ships)
        delivered_count = sum(1 for s in acct_ships if s[2] == "delivered")
        c.execute("""INSERT INTO notifications
            (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
             action_label, action_link, read, starred, archived, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, "system", "normal",
             "Weekly Shipping Summary",
             f"Your shipping activity for the week of {(now - timedelta(days=7)).strftime('%b %d')}",
             f"Here's your weekly shipping summary: {total_ships} shipments, ${total_cost:.2f} total.",
             f"""WEEKLY SHIPPING SUMMARY
---
Period: {(now - timedelta(days=7)).strftime('%B %d')} - {now.strftime('%B %d, %Y')}

OVERVIEW
---
Total Shipments:     {total_ships}
Delivered:           {delivered_count}
Total Shipping Cost: ${total_cost:.2f}
Avg Cost/Shipment:   ${total_cost/max(total_ships,1):.2f}

TOP CARRIERS USED
---
{chr(10).join(f"  - {name}: {sum(1 for s in acct_ships if s[12]==name)} shipments" for name in set(s[12] for s in acct_ships[:5]))}

DELIVERY PERFORMANCE
---
On-Time Rate:     {round(sum(1 for s in acct_ships if s[2]=="delivered" and s[8] and s[9] and s[8]<=s[9]) / max(delivered_count,1) * 100)}%
Exceptions:       {sum(1 for s in acct_ships if s[2]=="exception")}
Returns:          {sum(1 for s in acct_ships if s[2]=="returned")}

View your full analytics dashboard for detailed breakdowns and trends.
---
ShipFlow Weekly Reports""",
             "ShipFlow Analytics", None, None,
             "View Dashboard", "/dashboard",
             random.choice([0, 1]), 0, 0, (now - timedelta(days=random.randint(0, 3))).isoformat()))

        # Security notification
        c.execute("""INSERT INTO notifications
            (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
             action_label, action_link, read, starred, archived, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, "system", "low",
             "Security: New Login Detected",
             "New sign-in to your ShipFlow account",
             "A new login to your account was detected.",
             f"""SECURITY NOTIFICATION
---

A new sign-in to your ShipFlow account was detected:

Device:     Web Browser
Location:   United States
IP Address: 192.168.1.{random.randint(1,254)}
Time:       {(now - timedelta(hours=random.randint(1, 48))).strftime('%B %d, %Y at %I:%M %p UTC')}

If this was you, no action is needed.

If you did NOT sign in, please:
1. Change your password immediately
2. Regenerate your API key from Account Settings
3. Review recent activity in your Activity Log
4. Contact security@shipflow.com

We take the security of your account seriously. Enable two-factor authentication in Settings for additional protection.
---
ShipFlow Security Team""",
             "ShipFlow Security", "account", aid,
             "Review Activity", "/account",
             random.choice([0, 1, 1]), 0, 0, (now - timedelta(hours=random.randint(1, 72))).isoformat()))

    # ===== ACTIVITY LOG =====
    actions = ["login","shipment_created","payment_method_added","invoice_paid","profile_updated","api_key_regenerated","address_added"]
    for acct in accounts:
        for _ in range(random.randint(8, 25)):
            action = random.choice(actions)
            created = now - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
            c.execute("INSERT INTO activity_log (account_id, action, details, created_at) VALUES (?,?,?,?)",
                      (acct["id"], action, f"User performed: {action.replace('_',' ')}", created.isoformat()))

    conn.commit()
    conn.close()

    # Summary
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tables = ["accounts","payment_methods","invoices","invoice_lines","shipping_rates",
              "carriers","warehouses","customers","shipments","shipment_events","claims",
              "saved_addresses","notifications","activity_log"]
    print()
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {c.fetchone()[0]}")
    conn.close()
    print("\n  Seed complete!")
    print(f"  Demo login: admin@shipflow.com / admin123\n")


if __name__ == "__main__":
    seed()

"""Generate realistic shipping analytics data with accounts, payments, billing."""
import sqlite3
import random
import os
import re
import json
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
    # Ensure tables exist before seeding
    from app import init_db
    init_db()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for t in ["email_review_queue","shipment_items","products","customer_addresses",
              "meeting_requests","enterprise_questionnaires","team_members","connected_platforms",
              "account_use_cases","pricing_tiers","activity_log","notifications","invoice_lines",
              "inbox_messages","connected_emails",
              "invoices","shipping_rates","saved_addresses","payment_methods","shipment_events",
              "claims","shipments","customers","warehouses","carriers","accounts"]:
        c.execute(f"DELETE FROM {t}")

    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=120)

    # ===== ACCOUNTS =====
    accounts = []

    # Admin/demo account — all seed data is tied to this account
    salt = secrets.token_hex(16)
    api_key = "pb_" + secrets.token_hex(24)
    c.execute("""INSERT INTO accounts (email, password_hash, salt, name, company, phone, role, plan, account_type, api_key, status, onboarding_complete, created_at, last_login, clerk_user_id)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              ("admin@packetbase.com", hash_pw("admin123", salt), salt, "Julian Grossman", "PacketBase Inc",
               "555-0100", "admin", "enterprise", "enterprise", api_key, "active", 1, (now - timedelta(days=120)).isoformat(), now.isoformat(), None))
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
        c.execute("""INSERT INTO accounts (email, password_hash, salt, name, company, phone, role, plan, account_type, api_key, status, onboarding_complete, created_at, last_login, clerk_user_id)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (f"{first.lower()}.{last.lower()}{i}@example.com", hash_pw("password123", salt), salt,
                   f"{first} {last}", random.choice([co for co in COMPANIES if co]),
                   f"555-{random.randint(1000,9999)}", "user", plan, acct_type, "pb_" + secrets.token_hex(24),
                   "active", 1, created.isoformat(), (now - timedelta(days=random.randint(0,7))).isoformat(), None))
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
        cust_id = c.lastrowid
        customer_data.append({"id": cust_id, "region": region, "tier": tier, "created": created, "account_id": acct["id"]})
        # Add primary address for every customer
        c.execute("""INSERT INTO customer_addresses (customer_id, label, address, city, state, zip, is_default, created_at)
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (cust_id, "primary", f"{random.randint(100,9999)} {random.choice(['Main','Oak','Elm','Pine','Cedar'])} St",
                   city, state, random.choice(rdata["zips"]), 1, created.isoformat()))
        # Some customers have a second address
        if random.random() < 0.3:
            alt_region = random.choice(list(REGIONS.keys()))
            alt_rdata = REGIONS[alt_region]
            c.execute("""INSERT INTO customer_addresses (customer_id, label, address, city, state, zip, is_default, created_at)
                         VALUES (?,?,?,?,?,?,?,?)""",
                      (cust_id, random.choice(["warehouse","office","alternate"]),
                       f"{random.randint(100,9999)} {random.choice(['Broadway','Market','Lake','River','Hill'])} Ave",
                       random.choice(alt_rdata["cities"]), random.choice(alt_rdata["states"]),
                       random.choice(alt_rdata["zips"]), 0, created.isoformat()))

    # ===== PRODUCTS (demo account) =====
    product_categories = ["electronics","clothing","food","furniture","books","toys","health","sports","office","auto"]
    demo_products = [
        ("Wireless Bluetooth Headphones", "WBH-001", 0.8, 8, 6, 4, 49.99, "electronics", 1),
        ("Premium Cotton T-Shirt (M)", "PCT-M01", 0.4, 12, 10, 1, 24.99, "clothing", 0),
        ("Organic Coffee Beans (2lb)", "OCB-002", 2.1, 8, 4, 10, 18.99, "food", 0),
        ("Standing Desk Frame", "SDF-100", 45.0, 48, 30, 6, 299.99, "furniture", 0),
        ("Hardcover Novel Collection", "HNC-050", 3.2, 10, 7, 5, 39.99, "books", 0),
        ("Kids Building Block Set", "KBB-200", 1.5, 14, 10, 4, 29.99, "toys", 0),
        ("Vitamin D Supplements (90ct)", "VDS-090", 0.3, 4, 2, 2, 14.99, "health", 0),
        ("Yoga Mat (6mm)", "YGM-006", 2.8, 26, 6, 6, 34.99, "sports", 0),
        ("Mechanical Keyboard", "MKB-075", 2.0, 18, 6, 2, 89.99, "electronics", 1),
        ("Ceramic Coffee Mug Set (4)", "CCM-004", 3.5, 12, 12, 6, 32.99, "electronics", 1),
        ("Running Shoes (Size 10)", "RSH-010", 1.8, 13, 8, 5, 119.99, "sports", 0),
        ("Laptop Sleeve (15\")", "LSV-015", 0.5, 16, 11, 1, 22.99, "electronics", 0),
        ("Stainless Steel Water Bottle", "SWB-032", 0.9, 10, 3, 3, 24.99, "health", 0),
        ("Desk Organizer Set", "DOS-001", 1.2, 12, 8, 4, 19.99, "office", 0),
        ("Car Phone Mount", "CPM-001", 0.3, 6, 4, 3, 15.99, "auto", 0),
    ]
    product_ids = []
    for name, sku, weight, l, w, h, value, cat, fragile in demo_products:
        c.execute("""INSERT INTO products (account_id, name, sku, weight_lbs, length_in, width_in, height_in, declared_value, category, is_fragile, created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (demo_account_id, name, sku, weight, l, w, h, value, cat, fragile, (now - timedelta(days=random.randint(10,60))).isoformat()))
        product_ids.append(c.lastrowid)

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

    # ===== SHIPMENT ITEMS (for demo account shipments) =====
    demo_shipments = c.execute("SELECT id FROM shipments WHERE account_id=? LIMIT 50", (demo_account_id,)).fetchall()
    for sh_row in demo_shipments:
        sh_id = sh_row[0]
        num_items = random.choices([1,2,3], weights=[60,30,10])[0]
        for _ in range(num_items):
            prod_idx = random.randint(0, len(product_ids)-1)
            prod = demo_products[prod_idx]
            qty = random.randint(1, 3)
            c.execute("""INSERT INTO shipment_items (shipment_id, product_id, product_name, quantity, weight_lbs, declared_value)
                         VALUES (?,?,?,?,?,?)""",
                      (sh_id, product_ids[prod_idx], prod[0], qty, prod[2], prod[6]))

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
             "Welcome to PacketBase!",
             "Your account is ready - here's how to get started",
             "Your PacketBase account has been created and is ready to use.",
             """Welcome to PacketBase! We're excited to have you on board.

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
   Need to integrate PacketBase with your systems? Grab your API key from My Account and check our API docs.

If you have any questions, our support team is available 24/7.

Happy shipping!
The PacketBase Team""",
             "PacketBase Onboarding", "account", aid,
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

Thank you for shipping with PacketBase.
---
This is an automated delivery confirmation from PacketBase tracking systems.""",
                     f"{carrier_name} via PacketBase", "shipment", s_id,
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
PacketBase Tracking System""",
                     f"{carrier_name} via PacketBase", "shipment", s_id,
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

Need help? Contact PacketBase support or file a claim from the Claims page.
---
PacketBase Exception Alert System""",
                     "PacketBase Alerts", "shipment", s_id,
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
PacketBase Returns System""",
                     "PacketBase Returns", "shipment", s_id,
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
PacketBase Billing Department""",
                     "PacketBase Billing", "invoice", inv_id,
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
3. Contact billing@packetbase.com for custom payment arrangements

Please ensure payment is made by the due date to avoid late fees. Accounts with invoices overdue by more than 30 days may have shipping services temporarily suspended.
---
PacketBase Billing Department""",
                     "PacketBase Billing", "invoice", inv_id,
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

If you have questions about this resolution, please contact our claims department at claims@packetbase.com with your claim ID.
---
PacketBase Claims Department""",
                     "PacketBase Claims", "claim", cl_id,
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

If you have additional evidence or information to support your claim, you can reply to this notification or email claims@packetbase.com.
---
PacketBase Claims Department""",
                     "PacketBase Claims", "claim", cl_id,
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
PacketBase Weekly Reports""",
             "PacketBase Analytics", None, None,
             "View Dashboard", "/dashboard",
             random.choice([0, 1]), 0, 0, (now - timedelta(days=random.randint(0, 3))).isoformat()))

        # Security notification
        c.execute("""INSERT INTO notifications
            (account_id, type, priority, title, subject, message, body, sender, entity_type, entity_id,
             action_label, action_link, read, starred, archived, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (aid, "system", "low",
             "Security: New Login Detected",
             "New sign-in to your PacketBase account",
             "A new login to your account was detected.",
             f"""SECURITY NOTIFICATION
---

A new sign-in to your PacketBase account was detected:

Device:     Web Browser
Location:   United States
IP Address: 192.168.1.{random.randint(1,254)}
Time:       {(now - timedelta(hours=random.randint(1, 48))).strftime('%B %d, %Y at %I:%M %p UTC')}

If this was you, no action is needed.

If you did NOT sign in, please:
1. Change your password immediately
2. Regenerate your API key from Account Settings
3. Review recent activity in your Activity Log
4. Contact security@packetbase.com

We take the security of your account seriously. Enable two-factor authentication in Settings for additional protection.
---
PacketBase Security Team""",
             "PacketBase Security", "account", aid,
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

    # ===== CONNECTED EMAILS (demo account) =====
    email_labels = [
        ("admin@packetbase.com", "general", "gmail", 1),
        ("claims@packetbase.com", "claims", "gmail", 0),
        ("billing@packetbase.com", "billing", "outlook", 0),
        ("julian.personal@gmail.com", "personal", "gmail", 0),
    ]
    email_ids = {}
    for addr, label, provider, is_primary in email_labels:
        created = (now - timedelta(days=random.randint(30, 90))).isoformat()
        c.execute("INSERT INTO connected_emails (account_id, email_address, label, provider, is_primary, connected_at) VALUES (?,?,?,?,?,?)",
                  (demo_account_id, addr, label, provider, is_primary, created))
        email_ids[addr] = c.lastrowid

    # Get some claim IDs for linking
    claim_rows = c.execute("SELECT id FROM claims WHERE account_id=? LIMIT 20", (demo_account_id,)).fetchall()

    # ===== INBOX MESSAGES =====
    # Claims-related emails (sent to claims@ inbox)
    claims_email_id = email_ids["claims@packetbase.com"]
    claim_senders = [
        ("Sarah Johnson", "sarah.j@acmecorp.com"),
        ("Mike Chen", "mike.chen@globalgoods.com"),
        ("Emily Rodriguez", "e.rodriguez@nextstep.io"),
        ("James Wilson", "jwilson@primeship.com"),
        ("Lisa Park", "lisa.park@vendorplus.com"),
        ("Tom Anderson", "t.anderson@retailmax.com"),
        ("Amy Foster", "amy.f@logisticspro.com"),
    ]

    claim_subjects = [
        ("Package arrived damaged - Order #{}", "claim"),
        ("Missing items in shipment #{}", "claim"),
        ("Delivery delay complaint - Tracking #{}", "issue"),
        ("Wrong address delivery - Need reroute #{}", "issue"),
        ("Request for refund - Damaged goods #{}", "claim"),
        ("Late delivery - SLA violation #{}", "issue"),
        ("Package lost in transit #{}", "claim"),
    ]

    for i, (subj_template, cat) in enumerate(claim_subjects):
        order_num = random.randint(10000, 99999)
        sender_name, sender_email = claim_senders[i % len(claim_senders)]
        subj = subj_template.format(order_num)
        claim_id = claim_rows[i][0] if i < len(claim_rows) else None
        body = f"""Hi PacketBase Team,

I'm writing regarding order #{order_num}. {random.choice([
            "The package arrived with visible damage to the outer box and the contents were broken.",
            "We received the shipment but several items from the order were missing.",
            "This delivery was significantly delayed beyond the promised delivery window.",
            "The package was delivered to the wrong address and we need it rerouted immediately.",
            "The goods arrived in unacceptable condition and we are requesting a full refund.",
            "This shipment missed the SLA by over 5 business days, causing issues with our customer.",
            "We have been waiting for this package for over 2 weeks and tracking shows no updates.",
        ])}

Please investigate and let us know the resolution.

Best regards,
{sender_name}"""
        received = (now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).isoformat()
        preview = body[:100].replace("\n", " ").strip()
        c.execute("""INSERT INTO inbox_messages (account_id, connected_email_id, from_address, from_name, to_address, subject, body, preview, category, is_read, is_starred, claim_id, received_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (demo_account_id, claims_email_id, sender_email, sender_name, "claims@packetbase.com",
                   subj, body, preview, cat, random.choice([0,0,0,1]), random.choice([0,0,1]), claim_id, received))

    # Billing-related emails (sent to billing@ inbox)
    billing_email_id = email_ids["billing@packetbase.com"]
    billing_messages = [
        ("PacketBase Billing", "noreply@packetbase.com", "Invoice #INV-2026-0042 - Payment Received",
         "Your payment of $1,247.50 for invoice INV-2026-0042 has been successfully processed. Thank you for your prompt payment.", "billing"),
        ("Stripe", "receipts@stripe.com", "Payment Receipt - PacketBase Subscription",
         "Your subscription payment of $49.00/month has been processed. Next billing date: May 1, 2026. View your receipt at dashboard.stripe.com.", "billing"),
        ("PacketBase Billing", "noreply@packetbase.com", "Invoice #INV-2026-0041 - Due in 5 Days",
         "This is a reminder that invoice INV-2026-0041 for $892.30 is due on April 15, 2026. Please ensure payment is made by the due date to avoid late fees.", "billing"),
        ("FedEx Billing", "billing@fedex.com", "Your FedEx Account Statement - March 2026",
         "Your monthly statement for March 2026 is now available. Total charges: $3,421.89. View and pay your statement at fedex.com/billing.", "billing"),
        ("PayPal", "service@paypal.com", "You've received a refund of $156.00",
         "A refund of $156.00 has been issued to your PayPal account for claim #CLM-8847. The funds will appear in your balance within 3-5 business days.", "billing"),
    ]
    for sender_name, sender_email, subj, body, cat in billing_messages:
        received = (now - timedelta(days=random.randint(0, 20), hours=random.randint(0, 23))).isoformat()
        c.execute("""INSERT INTO inbox_messages (account_id, connected_email_id, from_address, from_name, to_address, subject, body, preview, category, is_read, received_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (demo_account_id, billing_email_id, sender_email, sender_name, "billing@packetbase.com",
                   subj, body, body[:100], cat, random.choice([0,1]), received))

    # General business emails (sent to admin@ inbox)
    general_email_id = email_ids["admin@packetbase.com"]
    general_messages = [
        ("UPS Account Manager", "account.manager@ups.com", "Your UPS Contract Renewal - Action Required",
         "Dear Valued Customer,\n\nYour UPS shipping contract is up for renewal on May 1, 2026. We'd like to schedule a call to discuss your volume discounts and new service options.\n\nPlease reply to schedule a time that works for you.\n\nBest,\nKevin Wright\nUPS Enterprise Solutions", "general"),
        ("DHL Express", "notifications@dhl.com", "New DHL Express Rates Effective April 2026",
         "Please be advised that updated DHL Express rates are now in effect as of April 1, 2026. Key changes include a 3.2% general rate increase and updated fuel surcharges. View the full rate card at dhl.com/rates.", "general"),
        ("PacketBase System", "system@packetbase.com", "Weekly Analytics Report - Week of March 31",
         "Your weekly shipping analytics summary:\n\n- Total Shipments: 847\n- On-Time Rate: 94.2%\n- Average Cost: $14.32/shipment\n- Exceptions: 12\n- Returns: 23\n\nView full report in your dashboard.", "general"),
        ("FedEx", "alerts@fedex.com", "Service Alert: Weather Delays in Southeast Region",
         "Due to severe weather conditions in the Southeast region, shipments to FL, GA, NC, and SC may experience delays of 1-2 business days. We are monitoring the situation and will provide updates. Affected tracking numbers will show updated ETAs.", "alert"),
        ("PacketBase System", "system@packetbase.com", "API Usage Alert - 80% of Monthly Limit",
         "Your API usage has reached 80% of your monthly limit (8,000 of 10,000 calls). Consider upgrading your plan or optimizing your API calls to avoid interruptions.", "alert"),
        ("USPS Business Solutions", "business@usps.com", "New USPS Ground Advantage Pricing",
         "We're excited to announce updated pricing for USPS Ground Advantage, effective immediately. Businesses shipping 500+ packages/month qualify for additional volume discounts. Contact your account rep for details.", "general"),
        ("Warehouse Team", "warehouse@packetbase.com", "Inventory Alert: Low Stock in Newark Warehouse",
         "The Newark warehouse is approaching capacity limits. Current utilization: 92%. Recommend scheduling overflow routing to the Philadelphia facility. Please review and approve the transfer request.", "alert"),
        ("PacketBase Security", "security@packetbase.com", "New Login from Unrecognized Device",
         "A new sign-in to your PacketBase account was detected from Chrome on macOS in New York, NY. If this was you, no action is needed. If not, please change your password immediately.", "system"),
    ]
    for sender_name, sender_email, subj, body, cat in general_messages:
        received = (now - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))).isoformat()
        c.execute("""INSERT INTO inbox_messages (account_id, connected_email_id, from_address, from_name, to_address, subject, body, preview, category, is_read, is_starred, received_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (demo_account_id, general_email_id, sender_email, sender_name, "admin@packetbase.com",
                   subj, body, body[:100].replace("\n"," "), cat, random.choice([0,0,1]), random.choice([0,0,0,1]), received))

    # Personal emails (sent to personal inbox)
    personal_email_id = email_ids["julian.personal@gmail.com"]
    personal_messages = [
        ("Amazon", "shipment-tracking@amazon.com", "Your Amazon order has shipped!",
         "Your order #114-3948271-8823947 has shipped and is on its way! Estimated delivery: April 12, 2026. Track your package at amazon.com/orders.", "personal"),
        ("LinkedIn", "notifications@linkedin.com", "You have 5 new connection requests",
         "You have 5 pending connection requests on LinkedIn. Sarah Chen, VP of Logistics at GlobalFreight, and 4 others want to connect with you.", "personal"),
        ("Google Workspace", "no-reply@accounts.google.com", "Security alert for your Google Account",
         "We noticed a new sign-in to your Google Account on a Windows device. If this was you, you can disregard this email. If not, please review your account activity.", "personal"),
        ("Newsletter", "digest@techcrunch.com", "TechCrunch Daily: Logistics AI Startups Raise $2B in Q1",
         "Today's top stories: AI-powered logistics startups raised a record $2 billion in Q1 2026, led by route optimization and predictive analytics companies. Read more...", "personal"),
    ]
    for sender_name, sender_email, subj, body, cat in personal_messages:
        received = (now - timedelta(days=random.randint(0, 7), hours=random.randint(0, 23))).isoformat()
        c.execute("""INSERT INTO inbox_messages (account_id, connected_email_id, from_address, from_name, to_address, subject, body, preview, category, is_read, received_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (demo_account_id, personal_email_id, sender_email, sender_name, "julian.personal@gmail.com",
                   subj, body, body[:100], cat, random.choice([0,1]), received))

    # ===== EMAIL REVIEW QUEUE (classify inbox messages for demo account) =====
    inbox_rows = c.execute("""SELECT id, subject, body, from_address FROM inbox_messages
                              WHERE account_id=? ORDER BY received_at DESC""", (demo_account_id,)).fetchall()
    for row in inbox_rows:
        msg_id, subj, body, from_addr = row
        text = (subj + " " + body).lower()
        extracted = {}
        issues = []

        # Extract order numbers
        order_match = re.search(r'(?:order|ord)[#:\s]*([A-Z0-9\-]{4,})', subj + " " + body, re.IGNORECASE)
        if order_match:
            extracted["order_number"] = order_match.group(1)
        # Extract invoice numbers
        inv_match = re.search(r'(?:invoice|inv)[#:\s]*([A-Z0-9\-]{4,})', subj + " " + body, re.IGNORECASE)
        if inv_match:
            extracted["invoice_number"] = inv_match.group(1)
        # Extract amounts
        amount_match = re.search(r'\$([0-9,]+\.?\d{0,2})', subj + " " + body)
        if amount_match:
            extracted["amount"] = amount_match.group(1).replace(",", "")
        # Extract claim IDs
        claim_match = re.search(r'(?:claim|clm)[#:\s]*([A-Z0-9\-]{3,})', subj + " " + body, re.IGNORECASE)
        if claim_match:
            extracted["claim_id"] = claim_match.group(1)

        # Classify
        category = "general"
        if any(k in text for k in ["damage","broken","lost","missing","claim","refund","compensation"]):
            category = "claim"
        elif any(k in text for k in ["delay","late","wrong address","reroute","complaint","sla violation"]):
            category = "issue"
        elif any(k in text for k in ["invoice","payment","receipt","billing","charge","statement","subscription"]):
            category = "billing"
        elif any(k in text for k in ["alert","warning","urgent","action required","security"]):
            category = "alert"
        elif any(k in text for k in ["shipped","delivered","tracking","transit"]):
            category = "shipping"
        extracted["category"] = category

        # Issues
        if category in ("claim", "issue") and "tracking_number" not in extracted:
            issues.append({"field": "tracking_number", "message": "Could not find a tracking number in this email"})
        if category == "billing" and "amount" not in extracted and "invoice_number" not in extracted:
            issues.append({"field": "amount", "message": "No invoice number or amount found"})

        status = "pending" if issues else "saved"
        # Some resolved ones for variety
        resolved_at = None
        linked_type = None
        linked_id = None
        auto_created = 0
        if status == "saved" and random.random() < 0.4:
            status = "resolved"
            resolved_at = (now - timedelta(days=random.randint(0, 5))).isoformat()
            if category == "claim" and claim_rows:
                linked_type = "claim"
                linked_id = random.choice(claim_rows)[0]
                auto_created = 1

        c.execute("""INSERT INTO email_review_queue (account_id, inbox_message_id, extracted_data, issues, status, created_at, resolved_at, linked_entity_type, linked_entity_id, auto_created)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (demo_account_id, msg_id, json.dumps(extracted), json.dumps(issues), status,
                   (now - timedelta(days=random.randint(0, 10))).isoformat(), resolved_at, linked_type, linked_id, auto_created))

    conn.commit()
    conn.close()

    # Summary
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tables = ["accounts","payment_methods","invoices","invoice_lines","shipping_rates",
              "carriers","warehouses","customers","customer_addresses","products","shipments","shipment_items",
              "shipment_events","claims","saved_addresses","notifications","activity_log",
              "connected_emails","inbox_messages","email_review_queue"]
    print()
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t}: {c.fetchone()[0]}")
    conn.close()
    print("\n  Seed complete!")
    print(f"  Demo login: admin@packetbase.com / admin123\n")


if __name__ == "__main__":
    seed()

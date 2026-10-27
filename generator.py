import os
import sys
import random
from datetime import datetime, timedelta
import sqlite3
import pandas as pd
import numpy as np

def run_pipeline(scale_sessions=1000):
    FIXED_SEED = 20261022
    random.seed(FIXED_SEED)
    np.random.seed(FIXED_SEED)
    
    # Safely clean up old database file if locked by another program
    if os.path.exists("journey_pipeline.db"):
        try:
            os.remove("journey_pipeline.db")
        except PermissionError:
            print("[!] Warning: 'journey_pipeline.db' is locked by another program. Please close DB Browser or VS Code tab and re-run.")
            sys.exit(1)
        
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("data/ground_truth", exist_ok=True)
    os.makedirs("web/data", exist_ok=True)
    
    print(f"[*] Initializing Synthetic Generation Engine (Scale Sessions: {scale_sessions}, Seed: {FIXED_SEED})...")

    # 1. Master Data Generation
    num_customers = max(100, scale_sessions // 5)
    customers = []
    for i in range(1, num_customers + 1):
        cus_id = f"CUS-{i:06d}"
        created_at = (datetime(2026, 1, 1) + timedelta(days=random.randint(0, 30))).isoformat()
        channel = random.choice(['web', 'app', 'support'])
        consent = random.choices([0, 1], weights=[0.3, 0.7])[0]
        customers.append({"customer_id": cus_id, "created_at": created_at, "signup_channel": channel, "consent_status": consent})
    
    # Add dummy customer for invalid identity stitching anomaly test case
    customers.append({
        "customer_id": "CUS-999999", 
        "created_at": "2026-01-01T00:00:00", 
        "signup_channel": "web", 
        "consent_status": 0
    })
    
    df_customers = pd.DataFrame(customers)

    pages = [
        {"page_id": "PAGE-001", "page_path": "/", "page_category": "home"},
        {"page_id": "PAGE-002", "page_path": "/shop", "page_category": "catalog"},
        {"page_id": "PAGE-003", "page_path": "/product", "page_category": "product"},
        {"page_id": "PAGE-004", "page_path": "/cart", "page_category": "checkout"},
        {"page_id": "PAGE-005", "page_path": "/checkout", "page_category": "checkout"},
        {"page_id": "PAGE-006", "page_path": "/support", "page_category": "support"}
    ]
    df_pages = pd.DataFrame(pages)

    products = [
        {"product_id": "PROD-001", "product_name": "CloudSync Pro", "category": "SaaS", "price": 49.99},
        {"product_id": "PROD-002", "product_name": "DataFlow API Gateway", "category": "Infrastructure", "price": 199.00},
        {"product_id": "PROD-003", "product_name": "SecureVault Storage", "category": "Security", "price": 29.99}
    ]
    df_products = pd.DataFrame(products)

    experiments = [
        {"experiment_id": "EXP-A", "experiment_name": "Checkout Redesign v1", "variant": "control"},
        {"experiment_id": "EXP-B", "experiment_name": "Checkout Redesign v1", "variant": "treatment"}
    ]
    df_experiments = pd.DataFrame(experiments)

    # 2. Transactional & Event Generation
    sessions = []
    events = []
    carts = []
    orders = []
    tickets = []
    outcomes = []
    ground_truth = []

    channels = ['web', 'app', 'support']
    device_types = ['desktop', 'mobile', 'tablet']
    
    for s_idx in range(1, scale_sessions + 1):
        session_id = f"SES-{s_idx:08d}"
        customer_id = random.choice(customers)["customer_id"] if random.random() > 0.1 else None
        channel = random.choice(channels)
        device = random.choice(device_types)
        start_time = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 59), seconds=random.randint(0, 86400))
        
        sessions.append({
            "session_id": session_id,
            "customer_id": customer_id,
            "channel": channel,
            "device_type": device,
            "session_start": start_time.isoformat()
        })

        # Simulate 2 to 6 journey events per session
        num_events = random.randint(2, 6)
        current_time = start_time
        has_converted = False
        
        for e_idx in range(1, num_events + 1):
            event_id = f"EVT-{s_idx:08d}-{e_idx:02d}"
            page = random.choice(pages)
            event_type = random.choice(['page_view', 'click', 'add_to_cart', 'purchase', 'support_interaction'])
            
            # Inject anomalies for specific test scenarios
            if s_idx % 500 == 0 and e_idx == 1:
                ground_truth.append({
                    "session_id": session_id,
                    "anomaly_type": "bot_loop",
                    "description": "High-frequency rapid events indicating automated bot traffic."
                })
            elif s_idx % 700 == 0 and e_idx == 2:
                customer_id = "CUS-999999"
                ground_truth.append({
                    "session_id": session_id,
                    "anomaly_type": "invalid_identity_stitching",
                    "description": "Session linked to non-existent customer ID CUS-999999."
                })

            current_time += timedelta(seconds=random.randint(5, 300))
            events.append({
                "event_id": event_id,
                "session_id": session_id,
                "page_id": page["page_id"],
                "event_type": event_type,
                "timestamp": current_time.isoformat()
            })

            if event_type == 'add_to_cart':
                carts.append({
                    "cart_id": f"CRT-{event_id}",
                    "session_id": session_id,
                    "product_id": random.choice(products)["product_id"],
                    "quantity": random.randint(1, 3),
                    "added_at": current_time.isoformat()
                })
            elif event_type == 'purchase' and not has_converted:
                has_converted = True
                prod = random.choice(products)
                orders.append({
                    "order_id": f"ORD-{session_id}",
                    "session_id": session_id,
                    "product_id": prod["product_id"],
                    "amount": prod["price"],
                    "purchased_at": current_time.isoformat()
                })
            elif event_type == 'support_interaction':
                tickets.append({
                    "ticket_id": f"TKT-{event_id}",
                    "session_id": session_id,
                    "issue_category": random.choice(['billing', 'technical', 'shipping']),
                    "created_at": current_time.isoformat()
                })

        # Determine session outcome
        if has_converted:
            outcome_status = "converted"
        elif tickets:
            outcome_status = "support_friction"
        else:
            outcome_status = "abandoned"

        outcomes.append({
            "outcome_id": f"OUT-{session_id}",
            "session_id": session_id,
            "outcome_status": outcome_status,
            "recorded_at": current_time.isoformat()
        })

    # Save to CSV files
    df_sessions = pd.DataFrame(sessions)
    df_events = pd.DataFrame(events)
    df_carts = pd.DataFrame(carts)
    df_orders = pd.DataFrame(orders)
    df_tickets = pd.DataFrame(tickets)
    df_outcomes = pd.DataFrame(outcomes)
    df_ground_truth = pd.DataFrame(ground_truth)

    df_customers.to_csv("data/raw/customer.csv", index=False)
    df_sessions.to_csv("data/raw/session.csv", index=False)
    df_events.to_csv("data/raw/journey_event.csv", index=False)
    df_carts.to_csv("data/raw/cart.csv", index=False)
    df_orders.to_csv("data/raw/order.csv", index=False)
    df_tickets.to_csv("data/raw/support_ticket.csv", index=False)
    df_outcomes.to_csv("data/raw/journey_outcome.csv", index=False)
    df_ground_truth.to_csv("data/ground_truth/ground_truth.csv", index=False)

    print("[*] Data generation complete. All CSV artifacts exported to data/raw/ and data/ground_truth/.")

    # Export Frontend JSON Datasets for HTML/JS Dashboard
    df_ground_truth.to_json("web/data/ground_truth.json", orient="records", indent=2)
    
    df_merged_outcomes = df_outcomes.merge(df_sessions, on="session_id")
    df_merged_outcomes.head(500).to_json("web/data/sessions.json", orient="records", indent=2)
    
    funnel_stats = df_merged_outcomes.groupby(["channel", "outcome_status"]).size().reset_index(name="count")
    funnel_stats.to_json("web/data/funnel_summary.json", orient="records", indent=2)
    print("[*] Frontend JSON datasets exported to web/data/ successfully!")

    # Load into SQLite Database
    conn = sqlite3.connect("journey_pipeline.db")
    with open("schema.sql", "r") as f:
        conn.executescript(f.read())
    
    df_customers.to_sql("Customer", conn, if_exists="append", index=False)
    df_pages.to_sql("Page", conn, if_exists="append", index=False)
    df_products.to_sql("Product", conn, if_exists="append", index=False)
    df_experiments.to_sql("Experiment", conn, if_exists="append", index=False)
    df_sessions.to_sql("Session", conn, if_exists="append", index=False)
    df_events.to_sql("JourneyEvent", conn, if_exists="append", index=False)
    df_carts.to_sql("Cart", conn, if_exists="append", index=False)
    df_orders.to_sql("Order", conn, if_exists="append", index=False)
    df_tickets.to_sql("SupportTicket", conn, if_exists="append", index=False)
    df_outcomes.to_sql("JourneyOutcome", conn, if_exists="append", index=False)
    conn.close()
    print("[*] SQLite database 'journey_pipeline.db' successfully initialized and seeded.")

if __name__ == "__main__":
    sessions_scale = 1000
    if len(sys.argv) > 1:
        try:
            sessions_scale = int(sys.argv[1])
        except ValueError:
            print("[!] Invalid scale argument provided. Using default 1000 sessions.")
            
    run_pipeline(scale_sessions=sessions_scale)
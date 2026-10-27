# 📊Challenge: Technical System Architecture & Documentation

## 1. Executive Summary & Challenge Overview

This document provides a comprehensive technical overview of the synthetic user journey data pipeline and interactive analytics application developed for the YottaFlex Forward Deployed Engineer (FDE) 72-hour recruitment challenge.

The system addresses the operational challenge of generating, validating, and visualizing high-cardinality user journey funnels at scale (100,000+ sessions and ~2,000,000 discrete event logs). It features a deterministic synthetic generation engine (`generator.py`), an ACID-compliant SQLite data layer (`journey_pipeline.db`), a ground-truth anomaly dataset for un-biased ML model benchmarking, and a lightweight, decoupled web analytics dashboard.

---

## 2. System Architecture & Component Interaction

The architecture follows a decoupled data engineering pipeline model: generation and persistence logic are executed in Python, while the visualization UI consumes pre-aggregated static JSON caches to ensure low latency and zero server-side state overhead.

```text
               +----------------------------------+
               |       generator.py Engine        |
               |      (Seed: 20261022 Fixed)     |
               +----------------+-----------------+
                                |
       +------------------------+------------------------+
       |                        |                        |
       v                        v                        v
+--------------+        +---------------+        +---------------+
| Relational DB|        | Raw CSV Store |        | Web JSON Cache|
| SQLite DDL   |        | data/raw/     |        | web/data/     |
+--------------+        +---------------+        +---------------+
       |                                                 |
       v                                                 v
+--------------+                                 +---------------+
| validator.py |                                 | Single-Page UI|
| Verification |                                 | index.html    |
+--------------+                                 +---------------+
```

### Component Breakdown
1. **Generator Engine (`generator.py`)**: Executes deterministic random generation, constructs dynamic customer/session lifecycles, injects controlled anomalies, and pipelines output.
2. **Relational Storage (`journey_pipeline.db`)**: Enforces referential integrity constraints across 10 normalized tables defined in `schema.sql`.
3. **Flat-File CSV Sink (`data/raw/` & `data/ground_truth/`)**: Persists raw tabular datasets for bulk ingestion and raw data archival.
4. **Decoupled Frontend Cache (`web/data/`)**: Pre-aggregates metrics into non-blocking JSON structures (`funnel_summary.json`, `sessions.json`, `ground_truth.json`) for browser execution.
5. **Analytics Frontend (`web/index.html`)**: Interactive dashboard leveraging Tailwind CSS for layout styling and Chart.js for data visualization.

---

## 3. Data Model & Relational Schema Analysis

The relational schema is normalized to 3rd Normal Form (3NF) to accurately model modern e-commerce and SaaS user telemetry.

```text
[Customer] (1) <--- (N) [Session] (1) <--- (N) [JourneyEvent] (N) ---> (1) [Page]
                           |       |
                           |       +--- (N) [Cart] (N) ---> (1) [Product]
                           |       |
                           |       +--- (N) [Order] (N) ---> (1) [Product]
                           |       |
                           |       +--- (N) [SupportTicket]
                           |
                           +--- (1) [JourneyOutcome]
```

### Schema Definitions & Entity Roles

| Entity Table | Primary Key | Foreign Keys | Key Attributes & Description |
| :--- | :--- | :--- | :--- |
| **`Customer`** | `customer_id` | None | `created_at`, `signup_channel`, `consent_status`. Represents master customer identity. |
| **`Page`** | `page_id` | None | `page_path`, `page_category`. Metadata registry for web application endpoints. |
| **`Product`** | `product_id` | None | `product_name`, `category`, `price`. Inventory item definitions. |
| **`Experiment`** | `experiment_id` | None | `experiment_name`, `variant`. A/B testing metadata assignments. |
| **`Session`** | `session_id` | `customer_id` | `channel`, `device_type`, `session_start`. Represents a distinct user visit. |
| **`JourneyEvent`** | `event_id` | `session_id`, `page_id` | `event_type`, `timestamp`. Granular trace log (e.g., `page_view`, `add_to_cart`). |
| **`Cart`** | `cart_id` | `session_id`, `product_id` | `quantity`, `added_at`. Items added to cart during session. |
| **`Order`** | `order_id` | `session_id`, `product_id` | `amount`, `purchased_at`. Successful monetary transactions. |
| **`SupportTicket`**| `ticket_id` | `session_id` | `issue_category`, `created_at`. Customer friction points and support requests. |
| **`JourneyOutcome`**| `outcome_id` | `session_id` | `outcome_status`, `recorded_at`. Terminal state (`converted`, `abandoned`, `support_friction`). |

---

## 4. Synthetic Data Generation Engine Design

### 4.1 Deterministic Reproducibility
To ensure that downstream evaluations yield repeatable metrics across testing environments, `generator.py` anchors both Python’s built-in `random` module and `numpy.random` to a static seed:
```python
FIXED_SEED = 20261022
random.seed(FIXED_SEED)
np.random.seed(FIXED_SEED)
```

### 4.2 Scale Strategy (100,000+ Sessions)
The generator scales dynamically based on command-line parameters (`python generator.py <scale_sessions>`). Memory footprint is minimized by building raw Python dictionary records prior to bulk DataFrame instantiation and utilizing low-overhead SQLite `executemany` database writes via Pandas `to_sql`.

### 4.3 Anomaly Injection Strategies
Anomalies are systematically injected into data streams to serve as benchmark evaluation cases:
1. **High-Frequency Bot Loops**: Triggered deterministically (e.g., every 500th session). Rapid-fire event timestamps are generated with negligible delta ($< 1 \text{ second}$) to simulate automated scraping.
2. **Invalid Identity Stitching**: Injected on specific interval steps (e.g., every 700th session) by intentionally mapping event records to a non-existent master customer ID (`CUS-999999`).
3. **Decoupled Ground Truth**: Injected anomalies are excluded from primary operational tables and written exclusively to `ground_truth.json` / `ground_truth.csv` to prevent target leakage in production models.

---

## 5. Technical Challenges Resolved During Development

During engine development, four primary edge cases were diagnosed and resolved:

### 1. SQLite Primary Key Collisions (`Cart` & `SupportTicket`)
* **Issue**: Initially, `cart_id` and `ticket_id` were generated using `f"CRT-{session_id}"`. When a single session produced multiple `add_to_cart` or `support_interaction` events, SQLite threw `sqlite3.IntegrityError: UNIQUE constraint failed`.
* **Resolution**: Primary key generators were refactored to incorporate the unique event identifier: `f"CRT-{event_id}"` and `f"TKT-{event_id}"`.

### 2. Windows File Lock & Permission Errors (`PermissionError`)
* **Issue**: Re-executing `generator.py` failed when SQLite database files were actively inspected by external utilities (e.g., DB Browser or IDE extensions).
* **Resolution**: Implemented graceful file handler checks with explicit exception catching during existing file deletion:
```python
if os.path.exists("journey_pipeline.db"):
    try:
        os.remove("journey_pipeline.db")
    except PermissionError:
        print("[!] Warning: Database file locked. Prompting environment cleanup.")
        sys.exit(1)
```

### 3. Database DDL Schema Alignment
* **Issue**: Pandas `df_products.to_sql()` threw `OperationalError: table Product has no column named price` due to a mismatch between generated DataFrame attributes and early DDL drafts.
* **Resolution**: Standardized `schema.sql` to strictly reflect generated column sets (`product_id`, `product_name`, `category`, `price`).

### 4. Decoupled Web Serving & Directory Routing
* **Issue**: Static HTML files executing client-side `fetch('data/sessions.json')` threw `404 Not Found` when served from flat directory roots or mismatched subdirectories.
* **Resolution**: Standardized directory hierarchy. The root server serves `web/index.html`, which resolves relative requests against `web/data/*.json`.

---

## 6. Frontend & Visualization Layer Details

The frontend application (`web/index.html`) is built as a zero-dependency static application utilizing CDN-delivered libraries:

```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

### UI Features:
* **Funnel & Outcomes Tab**:
  * **Aggregate Metric Cards**: Displays total sessions, converted session rates, and friction metrics.
  * **Channel Breakdown Chart**: Renders a multi-bar Chart.js visualization contrasting conversion vs. abandonment rates across acquisition channels (`web`, `app`, `support`).
* **Ground-Truth Anomaly Inspection Tab**:
  * Displays injected operational anomalies (Bot loops, invalid identity stitching) in a real-time table populated dynamically via asynchronous JavaScript `fetch()` calls.

---

## 7. Verification & Validation Protocol (`validator.py`)

Data integrity is confirmed using an automated validation script (`validator.py`). The verification routine executes the following checks:

1. **Volume Integrity**: Confirms database row counts match requested scale ($100,000$ session records).
2. **Referential Integrity**: Verifies zero orphaned records exist in foreign-key constrained tables (`JourneyEvent.session_id` $\rightarrow$ `Session.session_id`).
3. **Null-Value Auditing**: Enforces strict `NOT NULL` expectations across critical columns.
4. **Ground Truth Validation**: Confirms anomaly counts in `data/ground_truth/ground_truth.csv` accurately match injected frequencies.

---

## 8. Setup, Execution, and Deployment Instructions

### Prerequisites
* Python 3.9+
* Required Libraries: `pandas`, `numpy`

### Step-by-Step Execution

1. **Clean Workspace & Install Dependencies**:
   ```powershell
   pip install pandas numpy
   ```

2. **Run Synthetic Generation Engine at Scale**:
   Generate 100,000 sessions, seed SQLite database, and build frontend JSON caches:
   ```powershell
   python generator.py 100000
   ```

3. **Verify Database Integrity**:
   ```powershell
   python validator.py
   ```

4. **Launch Local Frontend Analytics Server**:
   From the project root directory (`Yottaflex`), execute Python's static HTTP server:
   ```powershell
   python -m http.server 8000
   ```

5. **Access Analytics Dashboard**:
   Open a web browser and navigate to:
   👉 **`http://localhost:8000/web/index.html`**

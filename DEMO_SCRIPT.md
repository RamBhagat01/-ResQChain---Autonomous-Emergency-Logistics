# ResQChain Swarm - Hackathon Presenter Demo Script

> **Elevator Pitch:**  
> *"ResQChain Swarm is an autonomous emergency logistics engine. When climate or supply disruptions strike, a coordinated swarm of specialized AI agents continuously monitors weather and fleet telemetry, queries regional supplier inventory, dynamically calculates safe transit routes around hazard zones, and dispatches automated relief orders end-to-end."*

---

## ⏱️ The 2-Minute Live Demo (8 Clear Steps)

### Step 1: Open the Control Center
- **Action:** Open `http://localhost:5173` in full-screen browser.
- **Say:** *"Welcome to ResQChain Swarm. On screen is our live operations command center covering the Odisha Disaster Management Corridor — 3 regional supply hubs in Bhubaneswar, Cuttack, and Berhampur, 3 coastal shelters, and 6 active fleet trucks."*

### Step 2: Show Initial Baseline
- **Point to:**
  - KPI cards at the top (0 active danger zones, 0 open demands, all 6 trucks IDLE).
  - Top bar status: *"Autonomous Swarm Loop is running in the background every 10 seconds."*

### Step 3: Trigger Disaster Scenario
- **Action:** In the Control Center panel at bottom-left:
  1. Click **"📍 Mahanadi Basin"** (or **"📍 Paradeep Delta"**) preset button.
  2. Click **"Simulate Flood"**.
- **Say:** *"A flash flood warning has been declared along the Mahanadi delta with Severity Level 4. A 4 km danger zone is rendered immediately on the map."*

### Step 4: Swarm Sensing & Risk Assessment
- **Point to:**
  - The live **Agent Activity Log** on the right.
  - Show `[risk]` alert: *"Risk Agent identified Kendrapara / Paradeep shelter within the hazard perimeter and generated prioritized emergency supply demands: food kits, water, and medical kits."*

### Step 5: Intelligent Supplier Selection (Gemini LLM)
- **Point to:**
  - The **Active Relief Orders** table.
  - Click **"Reason"** on Order #1.
  - **Say:** *"Notice the AI reasoning: The coastal camp required 240 food kits. Even though Cuttack was closer, Cuttack only had 120 kits in stock. The agent intelligently selected Bhubaneswar Central Hub, which had 350 kits available and a 95% reliability rating."*

### Step 6: Hazard-Avoiding Route Calculation
- **Point to:**
  - The blue path drawn on the map connecting Bhubaneswar to the shelter.
- **Say:** *"Our Routing Agent computed a transit corridor that avoids the flooded perimeter completely using OSRM routing with vector detour stitching."*

### Step 7: Dispatch & Fleet Movement
- **Action:** Click **"Accept"** on Order #1 (or toggle the **Auto-Dispatch** switch).
- **Say:** *"Once authorized, the order status transitions to IN_TRANSIT. Truck Alpha begins moving along the safe corridor toward the coastal shelter in real-time."*

### Step 8: Dynamic Obstacle Re-Routing (The Wow Factor!)
- **Action:** Click **"Grow Zone (+2km)"** in the control panel.
- **Point to:**
  - The danger zone expands on the map.
  - The truck's route instantly morphs into a **purple dashed detour line**!
  - Point to the `[routing] (alert)` entry in the activity log showing the reroute count and updated ETA.
- **Say:** *"The flood expanded while the truck was on the road. The swarm immediately detected that the existing route was obstructed, dynamically rerouted the truck around the expanding hazard, and updated the driver's ETA without any human intervention."*

---

## 🛡️ 3 Bulletproof Backup Plans (Never Fails)

| Failure Scenario | Built-in Autonomous Protection | Presenter Action |
|---|---|---|
| **Backup Plan 1: Internet Down / No Gemini Key** | Deterministic mathematical scoring takes over (`stock * 0.5 + reliability * 0.3 - distance * 0.2`) and outputs clean explanations. | Show the top-right badge: *"Fallback Heuristics Mode"* and highlight that the system is 100% offline-safe. |
| **Backup Plan 2: Routing API (ORS) Rate Limited / Error** | Deterministic geometric detour router pushes perpendicular waypoints around hazard circles. | Routes continue drawing seamlessly with `approximate_route=True`. |
| **Backup Plan 3: Accidental Double Click / State Glitch** | Instantaneous seed reset endpoint. | Click **"Reset Demo"** in the control panel. State resets in 0.5s without restarting servers. |

---

## 💡 Strong Closing Pitch Lines

1. *"A swarm of specialised AI agents, not one bloated chatbot: each agent owns one job and the orchestrator coordinates them."*
2. *"Fully autonomous loop: sense, decide, route, dispatch, re-route, with a human-approval switch for safety."*
3. *"Hybrid design: deterministic code for geometry and safety, LLM for reasoning and explanation, so every decision is auditable."*
4. *"Works offline-safe: every external service has a fallback."*


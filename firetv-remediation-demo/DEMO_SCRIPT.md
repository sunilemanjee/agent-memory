# Fire TV Support Memory Demo Script

**Audience:** Elastic customers evaluating AI agent capabilities
**Time:** 10–15 minutes
**URL:** http://localhost:5003
**Core message:** Elasticsearch natively powers agent memory — including a 4th layer, remediation memory, that stops an agent from ever asking a customer to repeat a troubleshooting step they've already tried.

---

## Before You Start

```bash
# Terminal — Flask app
cd /Users/sunilemanjee/Documents/GitHub/agent-memory-sunman/firetv-remediation-demo
source variables.env && python3 app.py

# Verify it's alive
open http://localhost:5003
```

You should see 9 tabs: **🏗️ Architecture | 💬 Live Chat | 📅 Episodic Memory | 🧠 Semantic Memory | ⚙️ Procedural Memory | 🛠️ Remediation Tracker | 🔍 Memory Search | 🔎 Memory Recall | 🧪 Memory Demo**

---

## Act 1 — The Problem (30 seconds, no UI yet)

**Say to customer:**

> "Everyone here has had this experience: you call support about a broken device, try what they suggest, it doesn't work, you call back — and the agent has no memory of any of it. You re-explain everything from scratch. Eventually you've tried every troubleshooting step that exists, and nobody tells you that. This demo is built around exactly that failure — Amazon Fire TV support, which is where I personally lived this. I'll show you an agent that remembers every step a customer already tried, and knows the moment there's nothing left to try but a fallback offer."

---

## Act 2 — Have a Conversation (2 minutes)

**Click the Live Chat tab.** Jordan Price is selected by default.

Click the suggested chip: **"I already tried everything you told me — power cycling, factory reset, and a new adapter. It still won't turn on."**

The agent responds live via Agent Builder.

**Say:**

> "This is a real conversation in Elastic Agent Builder. Notice the agent doesn't yet know this is the fourth time Jordan has said this — that's what memory fixes."

---

## Act 3 — Save to Agent Memory (2 minutes)

Click **"⚡ Save to Agent Memory"**. Workflow execution links appear — episodic, then semantic, procedural, and remediation workflows fire.

**Explain:**

> "One button fires 4 Kibana Workflows. Episodic captures what happened. Semantic distills standing knowledge. Procedural extracts Jordan's personalized playbook. And the new one — remediation — reads Jordan's full episode history against the canonical troubleshooting ladder for a power-failure issue, checks the warranty expiration date, and figures out: has every step been tried? Is the device still covered?"

Switch to **Episodic Memory** tab after ~25s to show the new card appear.

---

## Act 4 — Browse Episodic / Semantic / Procedural (3 minutes)

Quickly tour these three tabs as in the original demo — cards, topic tags, confidence scores, personalized procedure playbooks (`PROCEDURE_NAME` / `TRIGGER` / `STEPS`).

**Say:**

> "Episodic answers what happened. Semantic answers what's true. Procedural answers how to act. Same three-layer pattern as any agent memory system. Now here's the layer that's specific to this use case."

---

## Act 5 — Remediation Tracker: The Payoff (3 minutes)

**Click the 🛠️ Remediation Tracker tab.**

Find **Jordan Price's** card:

- Device: Amazon Fire TV, issue: power failure
- Warranty badge: **Expired**
- Ladder checklist: ✅ power cycle, ✅ factory reset, ✅ different power adapter/outlet — all three checked off
- A highlighted banner: **"🎁 Offer 10% off your next Amazon Fire TV purchase — all troubleshooting steps exhausted and unit is out of warranty."**

**Say:**

> "This is the ladder — the fixed, canonical set of troubleshooting steps for a power failure. Jordan has tried all three, and they all failed. The device is out of warranty. There is officially nothing left to troubleshoot. Instead of the agent asking Jordan to try something they've already tried — which is exactly what happened to me — it surfaces the one thing left: a 10% discount on the next purchase."

Show **Morgan Lee's** card for contrast — mid-ladder, warranty active, no offer yet. Show **Priya Nair's** card — resolved early, happy path.

> "Not every case ends in an offer. Morgan's still mid-ladder. Priya's issue resolved on the first suggested step. The remediation memory just reflects the true state of each case."

---

## Act 6 — Memory Search & Recall (2 minutes)

Tour **Memory Search** and **Memory Recall** as in the original demo, but note the Recall tab now shows **4 columns**: episodic, semantic, procedural, and remediation — each scored by kNN similarity.

> "At the start of any new conversation, one API call retrieves the most relevant memory across all four layers — including exactly where a customer stands on their troubleshooting ladder."

---

## Act 7 — Memory Comparison: The "Aha" Moment (3 minutes)

**Click the 🧪 Memory Demo tab.** Jordan Price is pre-selected. The question is pre-filled:

> **"I already tried everything you told me — it still doesn't work. What now?"**

Click **⚡ Run Comparison**.

| Left panel: 🚫 Without Memory | Right panel: 🧠 With Memory |
|---|---|
| No idea what Jordan already tried. Suggests power cycling — a step already exhausted. | Recognizes the ladder is exhausted and warranty expired. Cites the exact 3 prior steps by name. Proactively offers 10% off. |

**Say:**

> "Left side: the agent has no memory. It suggests power cycling the device — the very first thing Jordan tried, four conversations ago. This is the actual bad experience I had with Fire TV support.
>
> Right side: before the question was even asked, we pulled Jordan's remediation memory — semantic and remediation context both injected. The agent knows the ladder is exhausted, knows the warranty expired, and leads with the offer instead of more troubleshooting."

Point out the **Injected Memory Context** pills under the right panel — 🛠️ remediation pill shows the issue + warranty status directly.

---

## Closing (1 minute)

> "Four memory layers, four Kibana Workflows, four Elasticsearch indices — all `semantic_text`, no external vector DB, no ingest pipelines. The remediation layer is the one most directly tied to a real business outcome: it turns 'the agent remembers' into 'the agent knows exactly when to stop troubleshooting and make the right offer.' That's the difference between a chatbot and a support agent people actually trust."

---

## Common Customer Questions

**Q: Is the ladder hardcoded or can the agent adapt it?**
A: The ladder itself is canonical/fixed per issue type (a support org's SOP). The AI reasons over *where the customer is* on that fixed ladder — that's the dynamic part.

**Q: What if warranty status changes mid-conversation?**
A: The remediation workflow re-evaluates warranty status against current date every time it runs, so it's always current.

**Q: Does this replace human escalation?**
A: No — "escalate to hardware replacement" is itself the final ladder step for issues where no discount fallback applies. The 10% offer is specific to out-of-warranty cases with no functional fix remaining.

**Q: Can remediation memory work for other industries?**
A: Yes — any support flow with a fixed troubleshooting/eligibility ladder and a defined fallback (refund, credit, replacement, discount) fits this same pattern.

---

## Reset / Re-run Demo

```bash
source variables.env
python3 reset_demo.py                     # reset all users
python3 reset_demo.py --user jordan_price # reset one user
```

Or use the **↺ Reset Demo** button in the UI header (select a user, or leave "All Users" to reset everyone).

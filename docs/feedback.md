# Peer Review & Knowledge Sharing Feedback

> **Session:** Fall 2026 Complex Software Systems Knowledge Sharing  
> **Date:** Monday, November 9, 2026  
> **Participants:** Ivan Bodnar, Ernestas Bogdan, Vladyslav Luzianin, Martin Simeonov  
> **Formal Evidence & Reflection:** [LO5: Peer Knowledge Sharing & Technical Feedback Reflection](evidences/lo5/peer-knowledge-sharing/lo5-peer-feedback-and-reflection.md)

---

## 1. Peer Feedback & Validation

- Cool that the project is made from scratch (no boilerplates or pre-made saga orchestrators).
- Good that the project is the visualization of the process being experimented with.
- Great approach in modularity of the systems (independent microservices and isolated databases).
- Nice UI and visual state machine transitions.

---

## 2. Peer Ideas & Observations

- **Resource Monitoring:** Use Grafana for resource monitoring — Temporal always takes 2 services running (server cluster + worker process), whereas the naive orchestrator is just a single Python process.

---

## 3. Formal Academic Reflection & Steering

The architectural analysis of the Temporal two-service overhead vs. in-memory naive coordinator, the trade-off evaluation under Bloom Level 5, and steering decisions for Cycle 5 are documented in full in:  
👉 **[`docs/evidences/lo5/peer-knowledge-sharing/lo5-peer-feedback-and-reflection.md`](evidences/lo5/peer-knowledge-sharing/lo5-peer-feedback-and-reflection.md)**


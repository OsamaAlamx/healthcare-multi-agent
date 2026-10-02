# Multi-Agent Healthcare AI System

> Plain-language problem → working agent that reasons and acts. Built with Python, LangGraph, MCP tools, Groq API, Chroma RAG, Streamlit.

**Demo:** https://www.loom.com/share/66953d6d7a75463c840303861e983e62 — walkthrough (patient books appointment, asks symptoms, uploads PDF, doctor sees summary).

## The messy problem

Patients repeat history on every visit, receptionists retype bookings, doctors get PDFs with no summary. I broke it into steps:
1. Simple automation: booking, record lookup, PDF text extract
2. AI step: triage classification, OTC guidance, clinical summarization
3. Full agent: router that picks receptionist / reasoning / memory / prescriber and calls tools itself

## How it works

```
Streamlit (patient + doctor) → input guardrails → LangGraph router → 4 ReAct agents
→ MCP tools (scheduling, clinical, medical_records, drug) → Groq LLM API
→ output guardrails → SQLite + Chroma + episodic memory
```

* `src/agent_router.py` — intent classifier + safety-forced routing, per-agent history
* `src/agents/agent_factory.py` — Groq ReAct agents with patient context injection
* `src/mcp_client.py` — direct + stdio modes, persistent background event loop
* `src/mcp_servers/` — 4 tool servers
* `src/rag/` — drug + record vector indexes
* `src/guardrails/` — prompt-injection block, PII redact, restricted-substance block, emergency override, audit log
* `src/evaluation/test_cases.py` — triage, router, guardrail, RAG, E2E golden sets
* `src/views/` — patient chat by agent tab, doctor appointments + summaries + lookup

## Run it

```bash
cd src
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY
python groq_model_setup.py
streamlit run app.py
```

## Safety

Educational demo, not medical advice. Prescriber is OTC-only with disclaimer, emergencies are forced to Reasoning with urgent-care guidance.

## What I'd automate next

Port intake → triage → follow-up to n8n + webhooks + Clay enrichment, same router logic, so a small team can run outreach without manual copy-paste.

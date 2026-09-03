# 🏦 FedLens: Monetary Policy Intelligence System

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.13-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/PostgreSQL-pgvector-blue.svg" alt="Database">
  <img src="https://img.shields.io/badge/FastAPI-Backend-green.svg" alt="Backend">
  <img src="https://img.shields.io/badge/OpenAI-gpt--4o--mini-black.svg" alt="AI Model">
</div>

<br>

**FedLens** is an evidence-grounded monetary-policy intelligence system. It combines Federal Open Market Committee (FOMC) communications with real-time economic data to detect changes in policy stance, grade the economy, and identify contradictions between Fed rhetoric and actual economic indicators.

---

## ✨ Features

- **Automated Ingestion**: Automatically scrapes FOMC press releases, statements, and minutes.
- **Economic Data Tracking**: Integrates with the FRED API to pull Core PCE, CPI, Unemployment Rate, and Treasury yields.
- **AI Policy Grading**: Uses strict, structured LLM extraction (Instructor + Pydantic) to assign "improving", "deteriorating", or "stable" grades to 6 dimensions of the economy based *only* on the Fed's words.
- **Temporal Integrity**: Tracks release dates of economic indicators to ensure historical accuracy without look-ahead bias.

## 🏗 Architecture

- **Language**: Python 3.13
- **Database**: PostgreSQL with `pgvector` (via Docker)
- **Migrations**: Alembic
- **AI/LLM**: OpenAI / Anthropic (via Instructor for structured extraction)
- **Web API**: FastAPI (Upcoming)

## 🚀 Quick Start

### 1. Prerequisites
- Docker Desktop (must be running)
- Python 3.10+ and `uv` package manager

### 2. Installation
Clone the repo and install dependencies:
```bash
uv sync
```

### 3. Database Setup
Start the PostgreSQL database and run migrations:
```bash
docker compose up -d
uv run alembic upgrade head
```

### 4. Configuration
Create a `.env` file in the root directory:
```text
FRED_API_KEY="your_key_here"
OPENAI_API_KEY="your_key_here"
LLM_MODEL="gpt-4o-mini"
```

### 5. Running the Pipeline
To download the most recent FOMC statement, grade it using the AI, and save it to the database, run:
```bash
uv run python -m app.analysis.pipeline
```

You can view the results using the built-in helper script:
```bash
uv run python -m scripts.view_db
```

---
*Disclaimer: This is a portfolio project and should not be used for actual financial trading or investment advice.*

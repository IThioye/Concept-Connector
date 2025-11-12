## 🧠 Interdisciplinary Concept Connector 

A local multi-agent AI system that discovers and explains connections between concepts across different disciplines — built with **Flask**, **Ollama**, and a lightweight front‑end using **HTML/CSS/JS**.

---

## 🚀 Features

### 💬 Multi-Agent Workflow

| Agent                  | Role        | Description                                              |
| ---------------------- | ----------- | -------------------------------------------------------- |
| 🧩 Orchestrator        | Coordinator | Handles queries, manages memory, and synthesizes outputs |
| 🔗 Connection Finder   | Discovery   | Finds conceptual links between two ideas using the LLM   |
| 📘 Explanation Builder | Education   | Generates detailed, level‑adapted explanations           |
| 🎨 Analogy Generator   | Creativity  | Creates intuitive analogies from everyday contexts       |
| ⚖️ Bias Monitor        | Fairness    | Detects and flags bias or cultural imbalance in results  |

---

## 🏗️ Architecture Overview

### Backend (Flask)

* REST API with routes under `/api/` for concept connection, feedback, and profile.
* SQLite database for storing conversations, user preferences, and feedback.
* Modular agent classes and centralized prompt templates.

### Frontend (Vanilla JS)

* Responsive **two-column layout**: concept input on the left, results on the right.
* Dynamic visualization using **D3.js** to draw concept graphs.
* Sections for explanations, analogies, and bias review with styled Markdown output.

### Local LLM Integration

* Uses **Ollama** for local inference (default: `gemma3:4b`).
* Prompts optimized for reasoning and clarity.

---

## 🧩 Project Structure

```
project/
├── app.py
├── agents/
│   ├── orchestrator.py
│   ├── connection_finder.py
│   ├── explanation_builder.py
│   ├── analogy_generator.py
│   └── bias_monitor.py
├── services/
│   ├── ollama_service.py
│   ├── memory_service.py
│   ├── profile_service.py
│   └── text_formatter.py
├── prompts/templates.py
├── static/
│   ├── css/style.css
│   └── js/main.js
├── templates/
│   ├── base.html
│   └── index.html
├── database/
│   ├── app.db
│   └── schema.sql
├── notebooks/
│   └── fairness_metrics.ipynb
└── requirements.txt
```

---

## ⚙️ Installation

### 1. Clone and Set Up Environment

```bash
git clone https://github.com/IThioye/Concept-Connector.git
cd Concept-Connector
python -m venv .venv
.venv\Scripts\activate   # or source .venv/bin/activate on Linux
pip install -r requirements.txt
```

### 2. Start Ollama

Install and run [Ollama](https://ollama.ai):

```bash
ollama pull gemma3:4b
ollama serve
```

### 3. Run the Flask App

```bash
python app.py
```

Then open **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## 🖥️ Usage

1. Enter two concepts and select a knowledge level (beginner/intermediate/advanced).
2. The system will:

   * Find connections.
   * Build explanations.
   * Generate analogies.
   * Check for bias.
3. View:

   * A D3 graph of conceptual links.
   * Cleanly formatted explanations and analogies.
   * Bias review results.

---

## 🎨 Frontend Layout

```
+-----------------------------------------------------------+
|  Concepts (Left)       |  Results (Right)                 |
|-------------------------|---------------------------------|
|  [Concept A]            |  Connection Graph (D3)          |
|  [Concept B]            |  Explanations (Markdown → HTML) |
|  [Level Dropdown]       |  Analogies (HTML Lists)         |
|  [Submit Button]        |  Bias Review                   |
+-----------------------------------------------------------+
```

---

## 🧠 Customization

* Change the LLM model in `services/ollama_service.py`.
* Modify prompt templates in `prompts/templates.py`.
* Adjust UI colors and layout in `static/css/style.css`.


---

## 🧪 Example Query

**Concept A:** Photosynthesis
**Concept B:** Solar Panels
**Knowledge Level:** Intermediate

Produces:

* Connection graph (Biology → Energy Conversion → Engineering)
* Step‑by‑step explanation
* 2–3 analogies rendered as HTML
* Bias review feedback

---

## 🧰 Requirements

```
flask==3.0.0
requests==2.31.0
chromadb==0.4.18
pandas
matplotlib
textstat
```

---

## 🧩 Limitations & Future Work

* Sequential agent calls (can be optimized with async).
* Limited bias detection (expand with external datasets).
* Basic readability heuristics (can integrate text complexity models).
* No authentication or multi-user separation (planned).

---


**Created as part of the *Future of AI – Concept Connector* project.**

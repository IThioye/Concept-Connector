from flask import Flask, render_template, request, jsonify
from agents.orchestrator import Orchestrator
from services.memory_service import MemoryService
from services.profile_service import ProfileService


app = Flask(__name__)
mem = MemoryService(db_path="database/app.db")
profiles = ProfileService(db_path="database/app.db")
orchestrator = Orchestrator(memory=mem, profiles=profiles)


@app.route("/")
def home():
    return render_template("index.html")


@app.post("/api/connect")
def api_connect():
    data = request.get_json(force=True)
    concept_a = data.get("concept_a", "").strip()
    concept_b = data.get("concept_b", "").strip()
    level = data.get("knowledge_level", "intermediate").lower()
    session_id = data.get("session_id")


    result = orchestrator.process_query(concept_a, concept_b, level, session_id=session_id)
    return jsonify(result)


@app.get("/api/profile")
def get_profile():
    session_id = request.args.get("session_id")
    return jsonify(profiles.get_profile(session_id))


@app.post("/api/profile")
def set_profile():
    data = request.get_json(force=True)
    profiles.upsert_profile(data)
    return jsonify({"ok": True})


@app.post("/api/feedback")
def feedback():
    data = request.get_json(force=True)
    mem.save_feedback(**data)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
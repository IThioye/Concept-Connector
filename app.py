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
    return render_template("index.html", active_page="home")


@app.route("/fairness")
def fairness_page():
    return render_template("fairness.html", active_page="fairness")


@app.post("/api/connect")
def api_connect():
    data = request.get_json(force=True)
    concept_a = data.get("concept_a", "").strip()
    concept_b = data.get("concept_b", "").strip()
    level = data.get("knowledge_level", "intermediate").lower()
    session_id = data.get("session_id")


    def _parse_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    profile_data = {
        "session_id": session_id,
        "knowledge_level": level,
        "education_level": data.get("education_level"),
        "education_system": data.get("education_system"),
        "concept_a_knowledge": _parse_int(data.get("concept_a_knowledge")),
        "concept_b_knowledge": _parse_int(data.get("concept_b_knowledge")),
    }

    if session_id:
        profiles.upsert_profile(profile_data)

    profile_overrides = {k: v for k, v in profile_data.items() if k != "session_id"}

    result = orchestrator.process_query(
        concept_a,
        concept_b,
        level,
        session_id=session_id,
        profile_overrides=profile_overrides,
    )
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


@app.get("/api/fairness")
def get_fairness():
    session_id = request.args.get("session_id")
    limit = int(request.args.get("limit", 5))
    items = mem.recent_results(session_id, limit)

    overalls = [
        entry.get("fairness", {}).get("overall")
        for entry in items
        if isinstance(entry.get("fairness", {}).get("overall"), (int, float))
    ]
    aggregate = {
        "avg_overall": round(sum(overalls) / len(overalls), 2) if overalls else None,
        "runs": len(items),
        "bias_flags": sum(1 for entry in items if entry.get("bias_flag")),
    }

    return jsonify({"items": items, "aggregate": aggregate})


if __name__ == "__main__":
    app.run(debug=True)
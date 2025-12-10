# Add these routes to your app.py

from flask import Flask, render_template, request, jsonify
from agents.orchestrator import Orchestrator
from services.memory_service import MemoryService
from services.profile_service import ProfileService
from functools import wraps
from datetime import datetime, timedelta


app = Flask(__name__)
mem = MemoryService(db_path="database/app.db")
profiles = ProfileService(db_path="database/app.db")
orchestrator = Orchestrator(memory=mem, profiles=profiles, enable_metrics=True)


# Simple authentication decorator (replace with proper auth in production)
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In production, check actual authentication
        # For now, just check for a simple header
        auth_token = request.headers.get('X-Admin-Token')
        if auth_token != 'your-secret-token':  # Replace with secure token
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function


# Existing routes...
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


# NEW ROUTES FOR METRICS AND ADMIN

@app.route("/admin")
@require_admin
def admin_dashboard():
    """Admin dashboard showing system metrics."""
    return render_template("admin.html", active_page="admin")


@app.route("/api/metrics")
@require_admin
def get_metrics():
    """Get operational metrics from the orchestrator."""
    metrics = orchestrator.get_metrics_summary()
    
    # Add database-level metrics
    # Get total interactions and sessions
    with mem._get_connection() as conn:
        cur = conn.cursor()
        
        # Total queries
        cur.execute("SELECT COUNT(*) FROM conversations")
        total_queries = cur.fetchone()[0]
        
        # Unique sessions
        cur.execute("SELECT COUNT(DISTINCT session_id) FROM conversations WHERE session_id IS NOT NULL")
        unique_sessions = cur.fetchone()[0]
        
        # Recent activity (last 24 hours)
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        cur.execute("SELECT COUNT(*) FROM conversations WHERE timestamp > ?", (yesterday,))
        queries_24h = cur.fetchone()[0]
        
        # Average feedback rating
        cur.execute("SELECT AVG(rating) FROM feedback WHERE rating IS NOT NULL")
        avg_rating = cur.fetchone()[0]
        
        # Bias flags
        cur.execute("SELECT result_json FROM conversations WHERE result_json IS NOT NULL")
        rows = cur.fetchall()
        bias_count = 0
        mitigation_count = 0
        for row in rows:
            try:
                import json
                result = json.loads(row[0])
                if result.get('bias_flag'):
                    bias_count += 1
                if result.get('mitigated'):
                    mitigation_count += 1
            except:
                pass
    
    metrics.update({
        'database': {
            'total_queries': total_queries,
            'unique_sessions': unique_sessions,
            'queries_last_24h': queries_24h,
            'bias_flags': bias_count,
            'mitigations_triggered': mitigation_count,
            'avg_user_rating': round(avg_rating, 2) if avg_rating else None,
        }
    })
    
    return jsonify(metrics)


@app.route("/api/metrics/sessions")
@require_admin
def get_session_metrics():
    """Get per-session metrics."""
    limit = int(request.args.get('limit', 20))
    
    with mem._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                session_id,
                COUNT(*) as query_count,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen
            FROM conversations
            WHERE session_id IS NOT NULL
            GROUP BY session_id
            ORDER BY last_seen DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        sessions = []
        
        for row in rows:
            session_id = row[0]
            stats = mem.get_session_stats(session_id)
            sessions.append({
                'session_id': session_id,
                'query_count': row[1],
                'first_seen': row[2],
                'last_seen': row[3],
                'feedback_count': stats['feedback_count'],
                'avg_rating': stats['avg_rating'],
            })
    
    return jsonify({'sessions': sessions})


@app.route("/api/metrics/popular-concepts")
@require_admin
def get_popular_concepts():
    """Get most frequently queried concepts."""
    limit = int(request.args.get('limit', 10))
    
    with mem._get_connection() as conn:
        cur = conn.cursor()
        
        # Most common concept_a
        cur.execute("""
            SELECT concept_a, COUNT(*) as count
            FROM conversations
            GROUP BY LOWER(concept_a)
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        concept_a_popular = [{'concept': row[0], 'count': row[1]} for row in cur.fetchall()]
        
        # Most common concept_b
        cur.execute("""
            SELECT concept_b, COUNT(*) as count
            FROM conversations
            GROUP BY LOWER(concept_b)
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        concept_b_popular = [{'concept': row[0], 'count': row[1]} for row in cur.fetchall()]
        
        # Most common pairs
        cur.execute("""
            SELECT concept_a, concept_b, COUNT(*) as count
            FROM conversations
            GROUP BY LOWER(concept_a), LOWER(concept_b)
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        pairs_popular = [
            {'concept_a': row[0], 'concept_b': row[1], 'count': row[2]} 
            for row in cur.fetchall()
        ]
    
    return jsonify({
        'concept_a': concept_a_popular,
        'concept_b': concept_b_popular,
        'pairs': pairs_popular,
    })


@app.route("/api/metrics/performance")
@require_admin
def get_performance_metrics():
    """Get performance metrics over time."""
    days = int(request.args.get('days', 7))
    
    with mem._get_connection() as conn:
        cur = conn.cursor()
        
        # Daily query counts
        cur.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM conversations
            WHERE timestamp > datetime('now', '-' || ? || ' days')
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, (days,))
        
        daily_queries = [
            {'date': row[0], 'count': row[1]} 
            for row in cur.fetchall()
        ]
        
        # Average duration by stage (from result_json)
        cur.execute("""
            SELECT result_json
            FROM conversations
            WHERE timestamp > datetime('now', '-' || ? || ' days')
            AND result_json IS NOT NULL
        """, (days,))
        
        stage_durations = {}
        rows = cur.fetchall()
        
        for row in rows:
            try:
                import json
                result = json.loads(row[0])
                progress = result.get('progress', [])
                for stage in progress:
                    stage_name = stage.get('stage')
                    duration = stage.get('duration', 0)
                    if stage_name:
                        if stage_name not in stage_durations:
                            stage_durations[stage_name] = []
                        stage_durations[stage_name].append(duration)
            except:
                pass
        
        avg_durations = {
            stage: round(sum(durations) / len(durations), 3)
            for stage, durations in stage_durations.items()
            if durations
        }
    
    return jsonify({
        'daily_queries': daily_queries,
        'avg_stage_durations': avg_durations,
    })


@app.route("/api/admin/cleanup")
@require_admin
def cleanup_old_data():
    """Clean up old session data."""
    days = int(request.args.get('days', 90))
    deleted_count = mem.cleanup_old_sessions(days_old=days)
    
    return jsonify({
        'deleted_count': deleted_count,
        'cutoff_days': days,
    })


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
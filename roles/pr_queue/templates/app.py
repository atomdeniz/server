import json
import sqlite3
import os
from flask import Flask, request, jsonify, g

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "/app/data/pr_queue.db")

MEMBERS = {{ pr_queue_members | to_json }}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS pointers (
            member TEXT PRIMARY KEY,
            current_index INTEGER NOT NULL DEFAULT 0
        )
    """)
    for m in MEMBERS:
        db.execute("INSERT OR IGNORE INTO pointers (member, current_index) VALUES (?, 0)", (m,))
    db.commit()
    db.close()


def get_reviewers(member):
    idx = MEMBERS.index(member)
    others = MEMBERS[idx + 1:] + MEMBERS[:idx]
    return others


init_db()


@app.route("/")
def index():
    return HTML


@app.route("/api/state")
def get_state():
    member = request.args.get("member", "")
    if member not in MEMBERS:
        return jsonify({"error": "Invalid member"}), 400

    db = get_db()
    row = db.execute("SELECT current_index FROM pointers WHERE member=?", (member,)).fetchone()
    current_index = row["current_index"]

    reviewers = get_reviewers(member)
    current = reviewers[current_index % len(reviewers)]

    return jsonify({"current": current, "reviewers": reviewers, "index": current_index % len(reviewers)})


@app.route("/api/next", methods=["POST"])
def next_reviewer():
    member = request.args.get("member", "")
    if member not in MEMBERS:
        return jsonify({"error": "Invalid member"}), 400

    db = get_db()
    reviewers = get_reviewers(member)
    row = db.execute("SELECT current_index FROM pointers WHERE member=?", (member,)).fetchone()
    new_index = (row["current_index"] + 1) % len(reviewers)
    db.execute("UPDATE pointers SET current_index=? WHERE member=?", (new_index, member))
    db.commit()

    return jsonify({"current": reviewers[new_index], "reviewers": reviewers, "index": new_index})


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PR Review Queue</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; min-height: 100vh;
         display: flex; justify-content: center; align-items: center; padding: 2rem; }
  .container { max-width: 480px; width: 100%; }
  h1 { text-align: center; font-size: 1.5rem; margin-bottom: 2rem; color: #94a3b8; }

  .pick-screen { text-align: center; }
  .pick-screen p { color: #94a3b8; margin-bottom: 1.5rem; font-size: 1.1rem; }
  .pick-grid { display: flex; flex-direction: column; gap: 0.75rem; }
  .pick-btn { background: #1e293b; border: 2px solid #334155; border-radius: 12px;
    padding: 1rem; font-size: 1.1rem; color: #e2e8f0; cursor: pointer;
    transition: all 0.2s; font-weight: 500; }
  .pick-btn:hover { border-color: #3b82f6; background: #1e3a5f; }

  .queue-screen { display: none; }
  .who-am-i { text-align: center; color: #64748b; font-size: 0.85rem; margin-bottom: 1.5rem; }
  .who-am-i span { color: #94a3b8; font-weight: 600; }
  .who-am-i button { background: none; border: none; color: #64748b; cursor: pointer;
    text-decoration: underline; font-size: 0.85rem; margin-left: 0.5rem; }
  .who-am-i button:hover { color: #94a3b8; }

  .current-reviewer { background: #1e293b; border: 2px solid #3b82f6;
    border-radius: 16px; padding: 2rem; text-align: center; margin-bottom: 2rem; }
  .current-reviewer .label { font-size: 0.85rem; color: #64748b;
    text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; }
  .current-reviewer .name { font-size: 2.5rem; font-weight: 700; color: #3b82f6;
    word-break: break-word; }

  .btn { border: none; border-radius: 10px; padding: 0.75rem 1.5rem;
    font-size: 1rem; cursor: pointer; transition: all 0.2s; font-weight: 600; width: 100%; }
  .btn-next { background: #3b82f6; color: white; margin-bottom: 2rem; font-size: 1.1rem;
    padding: 1rem; }
  .btn-next:hover { background: #2563eb; }

  .reviewers { list-style: none; }
  .reviewers li { display: flex; align-items: center; padding: 0.75rem 1rem;
    background: #1e293b; border-radius: 10px; margin-bottom: 0.5rem; }
  .reviewers li.active { border-left: 4px solid #3b82f6; background: #1e3a5f; }
  .reviewers li .pos { color: #64748b; font-size: 0.85rem; margin-right: 0.75rem;
    min-width: 1.5rem; text-align: center; }
  .reviewers li .rname { flex: 1; }
</style>
</head>
<body>
<div class="container">
  <h1>PR Review Queue</h1>

  <div class="pick-screen" id="pick-screen">
    <p>Sen kimsin?</p>
    <div class="pick-grid" id="pick-grid"></div>
  </div>

  <div class="queue-screen" id="queue-screen">
    <div class="who-am-i">
      <span id="my-name"></span> olarak giris yaptin
      <button onclick="forget()">Degistir</button>
    </div>
    <div class="current-reviewer">
      <div class="label">Siradaki Reviewer</div>
      <div class="name" id="reviewer-name"></div>
    </div>
    <button class="btn btn-next" onclick="next()">Next</button>
    <ul class="reviewers" id="reviewers-list"></ul>
  </div>
</div>
<script>
const ME_KEY = 'pr_queue_member';

function init() {
  const me = localStorage.getItem(ME_KEY);
  if (me) { showQueue(me); }
  else { showPick(); }
}

function showPick() {
  document.getElementById('pick-screen').style.display = 'block';
  document.getElementById('queue-screen').style.display = 'none';
  const grid = document.getElementById('pick-grid');
  grid.innerHTML = '';
  const members = MEMBERS_LIST;
  members.forEach(m => {
    const btn = document.createElement('button');
    btn.className = 'pick-btn';
    btn.textContent = m;
    btn.onclick = () => { localStorage.setItem(ME_KEY, m); showQueue(m); };
    grid.appendChild(btn);
  });
}

function showQueue(me) {
  document.getElementById('pick-screen').style.display = 'none';
  document.getElementById('queue-screen').style.display = 'block';
  document.getElementById('my-name').textContent = me;
  load(me);
}

function forget() {
  localStorage.removeItem(ME_KEY);
  showPick();
}

async function load(me) {
  const res = await fetch('/api/state?member=' + encodeURIComponent(me));
  const data = await res.json();
  document.getElementById('reviewer-name').textContent = data.current;
  const list = document.getElementById('reviewers-list');
  list.innerHTML = '';
  data.reviewers.forEach((r, i) => {
    const li = document.createElement('li');
    if (i === data.index) li.className = 'active';
    li.innerHTML = '<span class="pos">' + (i+1) + '</span><span class="rname">' + esc(r) + '</span>';
    list.appendChild(li);
  });
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function next() {
  const me = localStorage.getItem(ME_KEY);
  if (!me) return;
  await fetch('/api/next?member=' + encodeURIComponent(me), { method: 'POST' });
  load(me);
}

const MEMBERS_LIST = """ + json.dumps(MEMBERS, ensure_ascii=False) + """;

init();
</script>
</body>
</html>"""

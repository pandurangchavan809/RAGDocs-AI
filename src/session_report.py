"""
session_report.py -- accumulate chat turns and export them as a standalone HTML report.

A SessionReport collects (question, answer, sources) per turn. `sources` is the list
of dicts that retrieve.py returns (each has score, text, pages, kind, source_file, ...).
Call render_html() for a self-contained HTML string, or save(path) to write it to disk.

Wiring into the Flask app (3 lines + 1 route):

    from flask import Response
    from session_report import SessionReport
    report = SessionReport()                       # one per process / session

    # after a chat turn finishes (you already have all three here):
    report.add_turn(question, answer, sources)     # sources = retrieve(...) output

    @app.route("/save_report")
    def save_report():
        return Response(
            report.render_html(),
            mimetype="text/html",
            headers={"Content-Disposition": "attachment; filename=session_report.html"},
        )

Frontend button:  <a href="/save_report" download>Save Report</a>
"""
import html
from datetime import datetime


class SessionReport:
    def __init__(self):
        self.turns = []
        self.started = datetime.now()

    def add_turn(self, question, answer, sources=None):
        self.turns.append({
            "question": question or "",
            "answer": answer or "",
            "sources": list(sources or []),
            "time": datetime.now(),
        })

    def clear(self):
        """Reset for a new session."""
        self.turns = []
        self.started = datetime.now()

    # ---- rendering ----

    def _source_block(self, src):
        sf    = html.escape(str(src.get("source_file", src.get("source", "?"))))
        pages = html.escape(str(src.get("pages", "?")))
        kind  = html.escape(str(src.get("kind", "")))
        score = src.get("score")
        score = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
        text  = html.escape(str(src.get("text", "")))
        return f"""        <details class="src" open>
          <summary><span class="sf">{sf}</span>
            <span class="meta">p{pages} &middot; {kind} &middot; score {score}</span>
          </summary>
          <pre>{text}</pre>
        </details>"""

    def _turn_block(self, i, turn):
        q = html.escape(turn["question"])
        a = html.escape(turn["answer"]).replace("\n", "<br>")
        t = turn["time"].strftime("%H:%M:%S")
        srcs = turn["sources"]
        if srcs:
            inner = "\n".join(self._source_block(s) for s in srcs)
            src_section = f'<div class="sources"><h4>Sources ({len(srcs)})</h4>\n{inner}\n      </div>'
        else:
            src_section = '<div class="sources"><h4>Sources (0)</h4><p class="none">No sources.</p></div>'
        return f"""    <article class="turn">
      <div class="q"><span class="badge">Q{i}</span><span class="qtime">{t}</span>
        <div class="qtext">{q}</div>
      </div>
      <div class="a">{a}</div>
      {src_section}
    </article>"""

    def render_html(self):
        ts = self.started.strftime("%Y-%m-%d %H:%M")
        if self.turns:
            body = "\n".join(self._turn_block(i + 1, t) for i, t in enumerate(self.turns))
        else:
            body = '<p class="none">No questions in this session yet.</p>'
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RAG Session Report &middot; {ts}</title>
<style>
  :root {{ --ink:#2b2622; --muted:#857a6e; --line:#e7e0d6; --amber:#c8860d; --bg:#fffdf9; --card:#fff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font-family:"Inter",-apple-system,"Segoe UI",Roboto,sans-serif; line-height:1.55; }}
  header {{ padding:28px 32px; border-bottom:1px solid var(--line); }}
  header h1 {{ margin:0 0 4px; font-size:20px; font-weight:600; }}
  header .sub {{ color:var(--muted); font-size:13px; }}
  main {{ max-width:900px; margin:0 auto; padding:24px 32px 64px; }}
  .turn {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
           padding:18px 20px; margin:18px 0; }}
  .q {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
  .badge {{ background:var(--amber); color:#fff; font-size:11px; font-weight:700;
            padding:2px 8px; border-radius:20px; letter-spacing:.04em; }}
  .qtime {{ color:var(--muted); font-size:12px; font-family:"IBM Plex Mono",monospace; }}
  .qtext {{ flex-basis:100%; font-weight:600; font-size:16px; margin-top:4px; }}
  .a {{ margin:12px 0 4px; }}
  .sources {{ margin-top:14px; border-top:1px dashed var(--line); padding-top:10px; }}
  .sources h4 {{ margin:0 0 8px; font-size:12px; color:var(--muted);
                 text-transform:uppercase; letter-spacing:.06em; }}
  details.src {{ border:1px solid var(--line); border-radius:6px; margin:6px 0;
                 padding:6px 10px; background:#fffaf2; }}
  details.src summary {{ cursor:pointer; display:flex; justify-content:space-between;
                         gap:12px; flex-wrap:wrap; }}
  .sf {{ font-weight:600; font-family:"IBM Plex Mono",monospace; font-size:13px; }}
  .meta {{ color:var(--muted); font-size:12px; font-family:"IBM Plex Mono",monospace; white-space:nowrap; }}
  details.src pre {{ white-space:pre-wrap; word-break:break-word; font-size:12.5px;
                     color:#4a423a; margin:8px 0 2px; font-family:"IBM Plex Mono",monospace; }}
  .none {{ color:var(--muted); font-style:italic; }}
  @media print {{ body {{ background:#fff; }} .turn {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<header>
  <h1>RAG Session Report</h1>
  <div class="sub">{len(self.turns)} question(s) &middot; session started {ts}</div>
</header>
<main>
{body}
</main>
</body>
</html>"""

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.render_html())
        return path

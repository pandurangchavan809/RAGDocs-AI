"""
feedback_report.py -- render the persisted feedback.json (like/dislike turns)
as a standalone HTML report. Structure/styling mirrors session_report.py.

Run directly to write feedback_report.html next to feedback.json:

    python -m src.feedback_report        # from the project root
    (or)  python feedback_report.py      # from inside src/

Wired into app.py as a download route:

    from src.feedback_report import render_html
    @app.route("/save_feedback_report")
    def save_feedback_report():
        return Response(render_html(), mimetype="text/html",
                         headers={"Content-Disposition": "attachment; filename=feedback_report.html"})
"""
import html
from datetime import datetime

try:
    from src.feedback import all_feedback           # package-style import (matches app.py)
except ImportError:
    from feedback import all_feedback                # fallback: run standalone from src/


def _source_block(src):
    doc   = html.escape(str(src.get("doc_id", "?")))
    pages = html.escape(str(src.get("pages", "?")))
    kind  = html.escape(str(src.get("kind", "")))
    score = src.get("score")
    score = f"{score:.3f}" if isinstance(score, (int, float)) else "-"
    text  = html.escape(str(src.get("text", "")))
    return f"""        <details class="src" open>
          <summary><span class="sf">{doc}</span>
            <span class="meta">p{pages} &middot; {kind} &middot; score {score}</span>
          </summary>
          <pre>{text}</pre>
        </details>"""


def _entry_block(i, entry):
    q  = html.escape(entry.get("question", ""))
    a  = html.escape(entry.get("answer", "")).replace("\n", "<br>")
    fb = entry.get("feedback", "like")
    cls  = "like" if fb == "like" else "dislike"
    text = "LIKED" if fb == "like" else "DISLIKED"
    when = f"{entry.get('date', '')} {entry.get('time', '')}".strip()
    srcs = entry.get("sources") or []
    if srcs:
        inner = "\n".join(_source_block(s) for s in srcs)
        src_section = f'<div class="sources"><h4>Retrieved Chunks ({len(srcs)})</h4>\n{inner}\n      </div>'
    else:
        src_section = '<div class="sources"><h4>Retrieved Chunks (0)</h4><p class="none">No chunks recorded.</p></div>'
    return f"""    <article class="turn {cls}">
      <div class="q"><span class="badge {cls}">{text}</span><span class="qtime">{when}</span>
        <div class="qtext">{q}</div>
      </div>
      <div class="a">{a}</div>
      {src_section}
    </article>"""


def render_html():
    entries = all_feedback()
    n_like = sum(1 for e in entries if e.get("feedback") == "like")
    n_dislike = sum(1 for e in entries if e.get("feedback") == "dislike")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    if entries:
        body = "\n".join(_entry_block(i + 1, e) for i, e in enumerate(entries))
    else:
        body = '<p class="none">No feedback recorded yet.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Feedback Report &middot; {ts}</title>
<style>
  :root {{ --ink:#2b2622; --muted:#857a6e; --line:#e7e0d6; --bg:#fffdf9; --card:#fff;
           --ok:#1a8a4a; --okbg:#eafaf0; --bad:#c0392b; --badbg:#fdecea; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font-family:"Inter",-apple-system,"Segoe UI",Roboto,sans-serif; line-height:1.55; }}
  header {{ padding:28px 32px; border-bottom:1px solid var(--line); }}
  header h1 {{ margin:0 0 4px; font-size:20px; font-weight:600; }}
  header .sub {{ color:var(--muted); font-size:13px; }}
  main {{ max-width:900px; margin:0 auto; padding:24px 32px 64px; }}
  .turn {{ background:var(--card); border:1px solid var(--line); border-left:4px solid var(--line);
           border-radius:10px; padding:18px 20px; margin:18px 0; }}
  .turn.like {{ border-left-color:var(--ok); }}
  .turn.dislike {{ border-left-color:var(--bad); }}
  .q {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
  .badge {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:20px; letter-spacing:.04em; }}
  .badge.like {{ background:var(--okbg); color:var(--ok); }}
  .badge.dislike {{ background:var(--badbg); color:var(--bad); }}
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
  <h1>Feedback Report</h1>
  <div class="sub">{len(entries)} total &middot; {n_like} liked &middot; {n_dislike} disliked &middot; generated {ts}</div>
</header>
<main>
{body}
</main>
</body>
</html>"""


def save(path="feedback_report.html"):
    out = render_html()
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    return path


if __name__ == "__main__":
    p = save()
    print(f"Wrote {p}")

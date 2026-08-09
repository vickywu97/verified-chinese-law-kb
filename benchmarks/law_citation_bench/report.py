#!/usr/bin/env python3
"""report.py — render the law-citation-bench leaderboard as Markdown + HTML.

Reads a ``leaderboard.json`` payload (produced by run.py) and emits two
human-readable, portfolio-ready reports:

  * leaderboard.md   — flat tables, easy to paste into a README / Notion.
  * leaderboard.html — styled single-page report (light theme, self-contained).

Offline, stdlib only. No templates engine, no network.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TASKS = ("T1", "T2", "T3")
DIFFS = ("easy", "medium", "hard")
TASK_TITLE = {
    "T1": "T1 引用接地",
    "T2": "T2 条文检索",
    "T3": "T3 幻觉识别",
}
DIFF_TITLE = {"easy": "易", "medium": "中", "hard": "难"}


def _mean(d, key):
    return d.get(key, {}).get("mean", 0.0)


def _f(x):
    return "%.4f" % x


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------
def render_markdown(payload):
    L = []
    L.append("# law-citation-bench · 跑分榜 (Leaderboard)")
    L.append("")
    L.append("- 数据集：`%s`" % payload.get("dataset", "?"))
    L.append("- 题量：%d" % payload.get("n_questions", 0))
    L.append("- 生成时间：%s" % payload.get("generated_at", "?"))
    dd = payload.get("difficulty_distribution", {})
    L.append("- 难度分布：易 %d / 中 %d / 难 %d" % (
        dd.get("easy", 0), dd.get("medium", 0), dd.get("hard", 0)))
    L.append("")
    L.append("## 综合跑分")
    L.append("")
    L.append("| 模型 | n | Overall | T1 接地 | T2 检索 | T2@5 | T3 识别 | T3-macroF1 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m in payload.get("models", []):
        t = m.get("tasks", {})
        L.append("| %s | %d | %s | %s | %s | %s | %s | %s |" % (
            m.get("model", "?"), m.get("n", 0), _f(m.get("overall", 0.0)),
            _f(_mean(t, "T1")), _f(_mean(t, "T2")),
            _f(t.get("T2", {}).get("recall@5", 0.0)),
            _f(_mean(t, "T3")),
            _f(t.get("T3", {}).get("macro_f1", 0.0))))
    L.append("")
    L.append("## 难度分层（Overall by 难度）")
    L.append("")
    L.append("| 模型 | 易 | 中 | 难 |")
    L.append("|---|---|---|---|")
    for m in payload.get("models", []):
        d = m.get("difficulty", {})
        L.append("| %s | %s | %s | %s |" % (
            m.get("model", "?"), _f(_mean(d, "easy")),
            _f(_mean(d, "medium")), _f(_mean(d, "hard"))))
    L.append("")
    L.append("## 任务 × 难度 矩阵（Overall）")
    L.append("")
    L.append("| 模型 | 任务 | 易 | 中 | 难 |")
    L.append("|---|---|---|---|---|")
    for m in payload.get("models", []):
        txd = m.get("task_x_diff", {})
        for task in TASKS:
            d = txd.get(task, {})
            L.append("| %s | %s | %s | %s | %s |" % (
                m.get("model", "?"), TASK_TITLE.get(task, task),
                _f(_mean(d, "easy")), _f(_mean(d, "medium")), _f(_mean(d, "hard"))))
    L.append("")
    L.append("> 评分说明：T1 = 0.7×法条精确匹配 + 0.3×关键句字符级 F1；"
             "T2 = Recall@5（MRR 另列）；T3 = Accuracy，macro-F1 为三类平均。"
             "哑基线用于校准，证明基准能区分好坏模型。")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# HTML (self-contained, light theme)
# --------------------------------------------------------------------------
def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_html(payload):
    models = payload.get("models", [])
    dd = payload.get("difficulty_distribution", {})

    # summary rows
    sum_rows = []
    for m in models:
        t = m.get("tasks", {})
        sum_rows.append(
            "<tr><td>%s</td><td>%d</td><td>%.4f</td><td>%.4f</td>"
            "<td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%.4f</td></tr>" % (
                _esc(m.get("model", "?")), m.get("n", 0), m.get("overall", 0.0),
                _mean(t, "T1"), _mean(t, "T2"),
                t.get("T2", {}).get("recall@5", 0.0),
                _mean(t, "T3"), t.get("T3", {}).get("macro_f1", 0.0)))

    # difficulty rows
    diff_rows = []
    for m in models:
        d = m.get("difficulty", {})
        diff_rows.append("<tr><td>%s</td><td>%.4f</td><td>%.4f</td><td>%.4f</td></tr>" % (
            _esc(m.get("model", "?")), _mean(d, "easy"),
            _mean(d, "medium"), _mean(d, "hard")))

    # task x diff rows
    txd_rows = []
    for m in models:
        txd = m.get("task_x_diff", {})
        for task in TASKS:
            d = txd.get(task, {})
            txd_rows.append(
                "<tr><td>%s</td><td>%s</td><td>%.4f</td><td>%.4f</td><td>%.4f</td></tr>" % (
                    _esc(m.get("model", "?")), _esc(TASK_TITLE.get(task, task)),
                    _mean(d, "easy"), _mean(d, "medium"), _mean(d, "hard")))

    html = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>law-citation-bench Leaderboard</title>
<style>
  :root { --bg:#f7f8fa; --card:#ffffff; --ink:#1a1a1a; --muted:#666;
          --line:#e3e6ea; --accent:#2f6df6; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
          font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",
          "Hiragino Sans GB","Microsoft YaHei",sans-serif; line-height:1.5; }
  .wrap { max-width:960px; margin:0 auto; padding:32px 20px 64px; }
  h1 { font-size:24px; margin:0 0 4px; }
  .meta { color:var(--muted); font-size:13px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
           padding:18px 20px; margin-bottom:20px; box-shadow:0 1px 2px rgba(0,0,0,.04); }
  h2 { font-size:17px; margin:0 0 12px; }
  table { width:100%%; border-collapse:collapse; font-size:13.5px; }
  th,td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:600; }
  tbody tr:hover { background:#f0f4ff; }
  .note { color:var(--muted); font-size:12.5px; margin-top:10px; }
</style></head>
<body><div class="wrap">
<h1>law-citation-bench · 跑分榜</h1>
<div class="meta">数据集 %s · 题量 %d · 生成时间 %s · 难度分布 易 %d / 中 %d / 难 %d</div>

<div class="card"><h2>综合跑分</h2>
<table><thead><tr><th>模型</th><th>n</th><th>Overall</th><th>T1 接地</th>
<th>T2 检索</th><th>T2@5</th><th>T3 识别</th><th>T3-macroF1</th></tr></thead>
<tbody>%s</tbody></table></div>

<div class="card"><h2>难度分层（Overall by 难度）</h2>
<table><thead><tr><th>模型</th><th>易</th><th>中</th><th>难</th></tr></thead>
<tbody>%s</tbody></table></div>

<div class="card"><h2>任务 × 难度 矩阵（Overall）</h2>
<table><thead><tr><th>模型</th><th>任务</th><th>易</th><th>中</th><th>难</th></tr></thead>
<tbody>%s</tbody></table>
<div class="note">T1 = 0.7×法条精确匹配 + 0.3×关键句字符级 F1；T2 = Recall@5；
T3 = Accuracy，macro-F1 为三类平均。哑基线用于校准，证明基准能区分好坏模型。</div>
</div>
</div></body></html>
""" % (
        _esc(payload.get("dataset", "?")), payload.get("n_questions", 0),
        _esc(payload.get("generated_at", "?")),
        dd.get("easy", 0), dd.get("medium", 0), dd.get("hard", 0),
        "".join(sum_rows), "".join(diff_rows), "".join(txd_rows))
    return html


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Render leaderboard.md / leaderboard.html from leaderboard.json")
    ap.add_argument("--json", default=os.path.join(HERE, "leaderboard.json"))
    ap.add_argument("--outdir", default=HERE)
    args = ap.parse_args()
    with open(args.json, encoding="utf-8") as fh:
        payload = json.load(fh)
    os.makedirs(args.outdir, exist_ok=True)
    md = render_markdown(payload)
    html = render_html(payload)
    md_path = os.path.join(args.outdir, "leaderboard.md")
    html_path = os.path.join(args.outdir, "leaderboard.html")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote %s" % md_path)
    print("wrote %s" % html_path)


if __name__ == "__main__":
    main()

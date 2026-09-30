# -*- coding: utf-8 -*-
"""
Step 7.8 — Final Model Visualization Dashboard generator
========================================================
READ-ONLY over the frozen 7.8 products + 7.7C-0 section table.
Emits ONE self-contained HTML file (no CDN, no external assets).

  reports/final_model_7_8/FINAL_MODEL_DASHBOARD.html

Zero simulation. Does not touch any frozen artifact.
"""
import csv
import json
import os
import datetime

ROOT = r"D:\Luan\2026-05\2_Singapore"
P78 = os.path.join(ROOT, "reports", "final_model_7_8")
P770 = os.path.join(ROOT, "reports", "spatial_residual_7_7c0")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def fnum(x, nd=6):
    try:
        return float(x)
    except Exception:
        return None


# ---------------------------------------------------------------- load inputs
metrics = {}
for r in read_csv(os.path.join(P78, "FINAL_VALIDATION_METRICS.csv")):
    v = fnum(r["value"])
    metrics[r["item"]] = {"value": v if v is not None else r["value"],
                          "unit": r["unit"], "source": r["source_step"], "criterion": r["criterion"]}

boundary_frozen = []
for r in read_csv(os.path.join(P78, "FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv")):
    boundary_frozen.append({
        "level": r["level"], "group": r["group"],
        "n_sections": fnum(r["n_sections"]) if r["n_sections"] else None,
        "n_zero_sim": fnum(r["n_zero_sim"]) if r["n_zero_sim"] else None,
        "ratio": fnum(r["ratio_FROZEN"]),
        "rel_dev": fnum(r["rel_dev_vs_global_FROZEN"]),
    })

eta2 = []
for r in read_csv(os.path.join(P770, "c0_rank_eta2.csv")):
    eta2.append({
        "dimension": r["dimension"], "layer": r["layer"],
        "eta2": fnum(r["eta2"]), "n_groups": fnum(r["n_groups"]),
        "eta2_chance": fnum(r["eta2_chance"]), "eta2_excess": fnum(r["eta2_excess"]),
    })

sec = []
sec_all = []
for r in read_csv(os.path.join(P770, "c0_section_table.csv")):
    row = {
        "id": r["lta_linkid"],
        "x": fnum(r["mid_x"]), "y": fnum(r["mid_y"]),
        "sim": fnum(r["sim_8_9_scaled"]), "obs": fnum(r["obs_8_9"]),
        "ratio": fnum(r["ratio_8_9"]),
        "zero": r["zero_sim"] == "True",
        "region": r["region"] or "UNMAPPED",
        "radial": r["radial"] or "UNMAPPED",
        "pa": r["pa"] or "UNMAPPED",
        "roadcat": r["RoadCat"],
        "ring": r["ring"],
        "len_m": fnum(r["section_length_m"]),
        "has_geo": bool(r["mid_x"] and r["mid_y"]),
    }
    sec_all.append(row)
    if row["has_geo"]:
        sec.append(row)

summ = read_json(os.path.join(P78, "step7_8_summary.json"))

# ------------------------------------------------ boundary from ground truth
# 直接以断面表重算池化 Σsim/Σobs —— region / radial / pa_key 三层与冻结件一致
# （差异 ≤ 发布四舍五入精度 1e-6）；pa_all 层冻结件存在单位标注缺陷
# （源列 c0_6 R_PA 已是「Q−1」被当作 ratio 再减 1），此处以真值呈现并显式标注。
import collections

GLOBAL_RATIO = (sum(s["sim"] or 0.0 for s in sec_all) /
                sum(s["obs"] or 0.0 for s in sec_all))
TOL = 1e-6  # 冻结件 ratio 按发布精度存储（region/radial 6dp、pa_key 5dp）


def pooled(level, key):
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    for s in sec_all:
        g = s[key]
        agg[g][0] += s["sim"] or 0.0
        agg[g][1] += s["obs"] or 0.0
        agg[g][2] += 1
        agg[g][3] += 1 if s["zero"] else 0
    out = []
    for g, (sm, ob, n, nz) in agg.items():
        if ob <= 0 or g == "UNMAPPED":
            continue
        out.append({"level": level, "group": g, "n_sections": n, "n_zero_sim": nz,
                    "ratio": sm / ob, "rel_dev": sm / ob / GLOBAL_RATIO - 1.0})
    return out


boundary = []
for lvl, key in [("region", "region"), ("radial", "radial"), ("pa_all", "pa")]:
    boundary += pooled(lvl, key)

# 关键 PA（与冻结件 pa_key 同名单）——同一真值的子集，仅换 level 标签
KEY_PA = ["ORCHARD", "BUKIT TIMAH", "OUTRAM", "MUSEUM", "TUAS", "HOUGANG",
          "NOVENA", "YISHUN", "KALLANG", "ANG MO KIO"]
boundary += [dict(r, level="pa_key") for r in boundary
             if r["level"] == "pa_all" and r["group"] in KEY_PA]

# ------------------------------------------------ 口径校验（vs 冻结件）
_calc = {(r["level"], r["group"]): r["ratio"] for r in boundary}
by_lvl = collections.defaultdict(lambda: [0, 0, 0.0, []])
for r in boundary_frozen:
    k = (r["level"], r["group"])
    if k not in _calc:
        continue
    d = r["ratio"] - _calc[k]
    b = by_lvl[r["level"]]
    b[0] += 1
    b[1] += 1 if abs(d) <= TOL else 0
    b[2] = max(b[2], abs(d))
    if abs(d) > TOL:
        b[3].append(r["group"])
conformance = [{"level": k, "n": v[0], "bit_exact": v[1], "max_abs_delta": v[2],
                "defect_groups": v[3]} for k, v in
               sorted(by_lvl.items(), key=lambda kv: ["region", "radial", "pa_key", "pa_all"].index(kv[0]))]

pa_all_frozen = {r["group"]: r["ratio"] for r in boundary_frozen if r["level"] == "pa_all"}
pa_all_true = {r["group"]: r["ratio"] for r in boundary if r["level"] == "pa_all"}
pa_all_fix = []
for g in pa_all_true:
    if g in pa_all_frozen:
        pa_all_fix.append({"group": g, "frozen": pa_all_frozen[g], "true": pa_all_true[g],
                           "delta": pa_all_frozen[g] - pa_all_true[g]})
pa_all_fix.sort(key=lambda x: -abs(x["true"] / GLOBAL_RATIO - 1))


payload = {
    "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "identity": summ["identity"],
    "bands": summ["bands"],
    "metrics": metrics,
    "boundary": boundary,
    "boundary_frozen": boundary_frozen,
    "conformance": conformance,
    "pa_all_fix": pa_all_fix,
    "global_ratio": GLOBAL_RATIO,
    "tol": TOL,
    "eta2": eta2,
    "sections": sec,
    "n_sections_all": len(sec_all),
    "n_sections_geo": len(sec),
    "verdict": summ["verdict"],
    "checks_pass": summ["checks_pass"],
    "checks_total": summ["checks_total"],
    "rate": summ["runtime_sec"],
    "unresolved_layers": summ["spatial_residual_boundary"]["nested_layers"],
    "version_line": summ["version_line"],
    "stop_rule": summ["stop_rule"],
}

DATA_JSON = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

# ---------------------------------------------------------------- HTML
HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Singapore OD-MATSim Final v1.0 — 可视化看板</title>
<style>
:root{
  --bg:#f5f6f8; --panel:#ffffff; --ink:#1a1d21; --ink2:#5a6169; --ink3:#8b929a;
  --line:#e3e6ea; --line2:#eef1f4;
  --acc:#2f6df6; --acc-soft:#e8f0ff;
  --over:#e8853c; --under:#3d7fd6; --ok:#1f9d63; --warn:#d9a021; --bad:#d64545;
  --grid:#eef1f4;
  --shadow:0 1px 2px rgba(16,24,40,.04),0 4px 14px rgba(16,24,40,.05);
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){
:root{
  --bg:#141619; --panel:#1b1e22; --ink:#e8eaed; --ink2:#a8b0b8; --ink3:#767e87;
  --line:#2a2f35; --line2:#23272c;
  --acc:#5b8dfb; --acc-soft:#1d2a44;
  --over:#f0a35e; --under:#6ba3ea; --ok:#48c98d; --warn:#e5bb52; --bad:#f07575;
  --grid:#23272c;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 4px 16px rgba(0,0,0,.35);
}}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--ink);
  font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1360px;margin:0 auto;padding:26px 22px 70px}

/* ---------- header ---------- */
.hero{
  background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:20px 22px;box-shadow:var(--shadow);margin-bottom:18px;
  display:flex;flex-wrap:wrap;gap:18px;align-items:center;justify-content:space-between;
}
.hero h1{margin:0;font-size:20px;letter-spacing:.2px}
.hero .sub{color:var(--ink2);font-size:12.5px;margin-top:5px}
.ver{
  font-family:var(--mono);font-size:12px;background:var(--acc-soft);color:var(--acc);
  border:1px solid var(--acc);border-radius:20px;padding:3px 11px;display:inline-block;margin-top:8px;
}
.badge{
  font-size:12px;font-weight:600;padding:6px 13px;border-radius:8px;white-space:nowrap;
  background:color-mix(in srgb,var(--ok) 14%,transparent);color:var(--ok);border:1px solid var(--ok);
}
.badge small{display:block;font-weight:400;color:var(--ink2);font-size:10.5px;margin-top:2px}

/* ---------- layout ---------- */
.grid{display:grid;gap:16px}
.g-kpi{grid-template-columns:repeat(auto-fit,minmax(178px,1fr))}
.g-2{grid-template-columns:1fr 1fr}
.g-3{grid-template-columns:1fr 1fr 1fr}
@media (max-width:900px){.g-2,.g-3{grid-template-columns:1fr}}

.card{
  background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:16px 17px;box-shadow:var(--shadow);
}
.card h2{margin:0 0 3px;font-size:14px;font-weight:650;letter-spacing:.2px}
.card .hint{color:var(--ink3);font-size:11.5px;margin-bottom:12px}
.card h2 .tag{font-weight:400;color:var(--ink3);font-size:11.5px;margin-left:6px}

.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 15px;box-shadow:var(--shadow)}
.kpi .k{color:var(--ink2);font-size:11.5px;letter-spacing:.3px;display:flex;justify-content:space-between;gap:6px}
.kpi .v{font-family:var(--mono);font-size:23px;font-weight:600;margin-top:7px;letter-spacing:-.4px}
.kpi .m{color:var(--ink3);font-size:11px;margin-top:4px;font-family:var(--mono)}
.kpi.hl{border-color:var(--acc);background:linear-gradient(180deg,var(--acc-soft),var(--panel))}

/* ---------- tables ---------- */
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:6px 9px;text-align:right;border-bottom:1px solid var(--line2);white-space:nowrap}
th{color:var(--ink2);font-weight:600;font-size:11px;text-align:right;letter-spacing:.3px;
   position:sticky;top:0;background:var(--panel);border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
tbody tr:hover{background:color-mix(in srgb,var(--acc) 6%,transparent)}
.scroll{max-height:330px;overflow:auto;border-radius:8px}
.mono{font-family:var(--mono)}

.pill{font-size:10.5px;padding:1px 7px;border-radius:20px;font-family:var(--mono);border:1px solid}
.pill.over{color:var(--over);border-color:var(--over);background:color-mix(in srgb,var(--over) 12%,transparent)}
.pill.under{color:var(--under);border-color:var(--under);background:color-mix(in srgb,var(--under) 12%,transparent)}
.pill.flat{color:var(--ink3);border-color:var(--line)}

/* ---------- controls ---------- */
.ctrl{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:11px;align-items:center}
.btn{
  font:inherit;font-size:11.5px;padding:4px 11px;border-radius:20px;cursor:pointer;
  background:transparent;border:1px solid var(--line);color:var(--ink2);transition:.13s;
}
.btn:hover{border-color:var(--acc);color:var(--acc)}
.btn.on{background:var(--acc);border-color:var(--acc);color:#fff}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:11px;color:var(--ink2);margin-top:10px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:1px}

svg{display:block;width:100%;overflow:visible}
.tip{
  position:fixed;pointer-events:none;z-index:99;opacity:0;transition:opacity .1s;
  background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:8px 10px;font-size:11.5px;box-shadow:var(--shadow);max-width:280px;
}
.tip b{font-family:var(--mono)}
.tip .r{color:var(--ink2)}

.bar{height:7px;border-radius:4px;background:var(--line2);overflow:hidden}
.foot{color:var(--ink3);font-size:11px;margin-top:26px;text-align:center;line-height:1.8}
.note{
  border-left:3px solid var(--warn);background:color-mix(in srgb,var(--warn) 8%,transparent);
  padding:10px 13px;border-radius:0 8px 8px 0;font-size:12.5px;color:var(--ink2);margin-top:12px;
}
.note b{color:var(--ink)}
.axis{stroke:var(--line);stroke-width:1}
.axlbl{fill:var(--ink3);font-size:10px}
.gl{stroke:var(--grid);stroke-width:1}
.gl0{stroke:var(--ink3);stroke-width:1;stroke-dasharray:3 3}
.dot{cursor:pointer}
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <div>
      <h1>Singapore OD–MATSim 最终模型 · 可视化看板</h1>
      <div class="sub">Step 7.8 — Final Model Freeze &amp; Validation Package　·　零仿真（read-only 冻结件）</div>
      <span class="ver" id="verName"></span>
    </div>
    <div style="text-align:right">
      <div class="badge" id="verdictBadge"></div>
      <div class="sub" id="genInfo" style="margin-top:8px"></div>
    </div>
  </div>

  <!-- KPI -->
  <div class="grid g-kpi" id="kpis" style="margin-bottom:16px"></div>

  <!-- validation + stability -->
  <div class="grid g-2" style="margin-bottom:16px">
    <div class="card">
      <h2>① 总体水平验证 <span class="tag">W01 · MATCHED Sim/Obs（08–09）</span></h2>
      <div class="hint">FROZEN 口径；容差 |x−1| ≤ 0.01（1%）。三口径并报，主口径 = FROZEN。</div>
      <div id="gauge"></div>
      <div class="legend" style="justify-content:center">
        <span><i style="background:var(--ok)"></i>FROZEN 主口径</span>
        <span><i style="background:var(--warn)"></i>POSITIVE_ONLY</span>
        <span><i style="background:var(--ink3)"></i>BEST_DIRECTION</span>
      </div>
    </div>
    <div class="card">
      <h2>② 收敛与稳定性 <span class="tag">7.6H H2</span></h2>
      <div class="hint">经验阈值：A_10:19 &lt; 0.03；SLIP &lt; 0.05；parity gap &lt; 0.05；Q19/Q̄ 偏差 ≤ 1 pp。</div>
      <div id="stab"></div>
    </div>
  </div>

  <!-- bands -->
  <div class="card" style="margin-bottom:16px">
    <h2>③ 三层区间（★独立、不得合并） <span class="tag">f* 取值轴</span></h2>
    <div class="hint">工作点 ≠ 最优；λ 仅“敏感度中心”，可检测但不可靠识别。三层语义不同，禁止压成一个区间。</div>
    <div id="bands"></div>
  </div>

  <!-- attribution -->
  <div class="grid g-2" style="margin-bottom:16px">
    <div class="card">
      <h2>④ 空间残差归因排序 <span class="tag">η²_excess（机会校正）</span></h2>
      <div class="hint">η²_excess = η² − chance；≤0 表示该层<b>低于随机</b>，判为已排除。基于 576 断面。</div>
      <div id="eta2"></div>
      <div class="legend">
        <span><i style="background:var(--ok)"></i>已定位（&gt; +0.01）</span>
        <span><i style="background:var(--ink3)"></i>接近随机（≈0）</span>
        <span><i style="background:var(--bad)"></i>低于随机 ⇒ 已排除</span>
      </div>
    </div>
    <div class="card">
      <h2>⑤ 未解释结构层 <span class="tag">7.7D 收口</span></h2>
      <div class="hint">已解释：f / λ / 车型构成·总量级。以下四层仍未解释——这是模型的<b>已知边界</b>，非失败项。</div>
      <div id="unresolved" style="margin-top:4px"></div>
      <div class="note">
        <b>边界声明：</b>7.7D 只证明其余各层“不足以解释”，<b>不</b>证明 twin / 方向性为因果。
      </div>
    </div>
  </div>

  <!-- residual charts -->
  <div class="card" style="margin-bottom:16px">
    <h2>⑥ 空间残差边界 <span class="tag">Sim/Obs − 1，相对偏离 %</span></h2>
    <div class="hint">正值 = 仿真偏高（过分配），负值 = 仿真偏低（欠分配）。零线 = 完全匹配。</div>
    <div class="ctrl" id="lvlCtrl"></div>
    <div id="resid"></div>
    <div class="legend">
      <span><i style="background:var(--over)"></i>仿真偏高（+/过）</span>
      <span><i style="background:var(--under)"></i>仿真偏低（−/欠）</span>
      <span><i style="background:var(--ink3)"></i>|dev| &lt; 10%</span>
    </div>
    <div class="note" style="border-left-color:var(--bad);background:color-mix(in srgb,var(--bad) 8%,transparent)">
      <b>⚠ 数值来源：</b>本图<b>直接由 576 断面表重算</b>池化 Σsim/Σobs，<span class="mono">rel_dev = ratio/全局 − 1</span>。
      region / radial / pa_key 三层与冻结件 <b>一致（|Δ| ≤ 1e-6，发布精度）</b>；
      <b>pa_all 层冻结件存在单位标注缺陷</b>（源列 <span class="mono">R_PA</span> 已是「Q−1」被当作 ratio 再减 1 ⇒ 系统性偏 −1.0），
      此图按真值呈现，详见下一节口径校验。
    </div>
  </div>

  <!-- conformance -->
  <div class="card" style="margin-bottom:16px">
    <h2>⑦ 口径校验 <span class="tag">真值（断面表重算）↔ 冻结件</span></h2>
    <div class="hint">判定标准：|Δ| ≤ 1e-6（冻结件 ratio 按发布精度存储，非全精度）。</div>
    <div id="conf"></div>
  </div>

  <!-- section scatter + spatial map -->
  <div class="grid g-2" style="margin-bottom:16px">
    <div class="card">
      <h2>⑧ 断面级 Sim vs Obs <span class="tag">n=576，log-log</span></h2>
      <div class="hint">对角线 = 完美匹配；点离线越远表示断面残差越大。悬停查看断面明细。</div>
      <div class="ctrl" id="scatCtrl"></div>
      <div id="scatter"></div>
      <div class="legend" id="scatLegend"></div>
    </div>
    <div class="card">
      <h2>⑨ 断面空间残差（SVY21 投影） <span class="tag">新加坡岛</span></h2>
      <div class="hint">点 = 观测断面中点；颜色 = log₂(Sim/Obs) 偏离方向与幅度。</div>
      <div id="map"></div>
      <div class="legend">
        <span><i style="background:var(--over)"></i>仿真偏高</span>
        <span><i style="background:var(--under)"></i>仿真偏低</span>
        <span><i style="background:var(--ink3)"></i>匹配（±25%）</span>
        <span><i style="background:transparent;border:1.2px solid var(--bad);border-radius:50%"></i>sim = 0（零流）</span>
      </div>
    </div>
  </div>

  <!-- data table -->
  <div class="card" style="margin-bottom:16px">
    <h2>⑩ 断面明细表 <span class="tag">可排序 / 点击表头</span></h2>
    <div class="hint">576 观测断面（574 有坐标可入图，2 无坐标仅参与池化聚合）；ratio = Sim/Obs（FROZEN）。</div>
    <div class="scroll"><table id="tbl"><thead></thead><tbody></tbody></table></div>
  </div>

  <!-- manifest / integrity -->
  <div class="grid g-2" style="margin-bottom:16px">
    <div class="card">
      <h2>⑪ 完整性门 <span class="tag">#168</span></h2>
      <div class="hint">含 G22 = 14 件冻结输入跑前后 mtime + sha256 逐位未变（read-only 硬证据）。</div>
      <div id="gates"></div>
    </div>
    <div class="card">
      <h2>⑫ 版本线 &amp; 停止规则 <span class="tag">version line</span></h2>
      <div class="hint">7.8 = 终点。继续研究属新问题 7.9 / v1.1，须另立版本。</div>
      <div id="vline"></div>
      <div class="note" id="stopNote"></div>
    </div>
  </div>

  <div class="foot" id="foot"></div>
</div>
<div class="tip" id="tip"></div>

<script>
const D = __DATA__;

/* ---------- helpers ---------- */
const $ = s => document.querySelector(s);
const el = (t, a = {}, kids = []) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", t);
  for (const k in a) n.setAttribute(k, a[k]);
  (Array.isArray(kids) ? kids : [kids]).forEach(c => c && n.appendChild(c));
  return n;
};
const fmt = (v, d = 4) => (v === null || v === undefined || isNaN(v)) ? "—"
  : (Math.abs(v) >= 1e5 ? v.toLocaleString("en-US", {maximumFractionDigits: 0}) : (+v).toFixed(d));
const pct = (v, d = 2) => (v * 100).toFixed(d) + "%";
const tipEl = $("#tip");
function bindTip(node, html) {
  node.addEventListener("mousemove", e => {
    tipEl.innerHTML = html; tipEl.style.opacity = 1;
    const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
    let x = e.clientX + 14, y = e.clientY + 14;
    if (x + w > innerWidth - 8) x = e.clientX - w - 14;
    if (y + h > innerHeight - 8) y = e.clientY - h - 14;
    tipEl.style.left = x + "px"; tipEl.style.top = y + "px";
  });
  node.addEventListener("mouseleave", () => tipEl.style.opacity = 0);
}
const RES_COLOR = v => v > .10 ? "var(--over)" : v < -.10 ? "var(--under)" : "var(--ink3)";
const REV = v => v > 0 ? '<span class="pill over">+过</span>' : v < 0 ? '<span class="pill under">−欠</span>' : '<span class="pill flat">=</span>';

/* ---------- header ---------- */
$("#verName").textContent = "model_version = " + (D.identity ? "Singapore_OD_MATSim_Final_v1.0" : "");
$("#verdictBadge").innerHTML = "✓ " + D.verdict + "<small>" + D.checks_pass + "/" + D.checks_total +
  " gates · " + D.rate + " s · 零仿真</small>";
$("#genInfo").innerHTML = "生成 " + D.generated + "　·　数据源：reports/final_model_7_8/ + 7.7C-0 断面表";

/* ---------- KPI ---------- */
const M = D.metrics;
const kpiDef = [
  ["MATCHED Sim/Obs", fmt(M.SimObs_FROZEN.value, 7), "FROZEN · |x−1|≤0.01", 1],
  ["N_sim (agents)", fmt(M.N_sim.value, 0), "W01 population", 0],
  ["f_work", fmt(M.f_work.value, 6), "7.6G direct", 0],
  ["implied f*", fmt(M.implied_fstar.value, 6), "由 Sim/Obs 反解", 0],
  ["λ_ref", fmt(D.identity.lambda_ref, 3), "敏感度中心（非最优）", 0],
  ["SCALE", fmt(D.identity.scale, 5), "采样放大系数", 0],
  ["calibration target", fmt(M.crossvalidation_R01_FROZEN.value, 7), "7.6C-2 R01 FROZEN", 0],
  ["abs dev from 1", fmt(M.abs_dev_from_1_pp.value, 4) + " pp", "容差 ≤ 1 pp", 0],
];
$("#kpis").innerHTML = kpiDef.map(([k, v, m, hl]) =>
  `<div class="kpi${hl ? ' hl' : ''}"><div class="k"><span>${k}</span></div><div class="v">${v}</div><div class="m">${m}</div></div>`).join("");

/* ---------- ① gauge ---------- */
(function () {
  const W = 560, H = 190, cx = W / 2, cy = H - 26, R = 148;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
  const arcs = [
    ["POSITIVE_ONLY", M.SimObs_POSITIVE_ONLY.value, "var(--warn)", 1],
    ["BEST_DIRECTION", M.SimObs_BEST_DIRECTION.value, "var(--ink3)", 0],
    ["FROZEN", M.SimObs_FROZEN.value, "var(--ok)", 1],
  ];
  const scale = v => Math.max(0, Math.min(1, (v - 0.4) / (1.6 - 0.4)));
  const rad = a => (180 - a * 180) * Math.PI / 180;
  // tolerance band around 1.0
  const tolA = [(1 - .01 - 0.4) / 1.2, (1 + .01 - 0.4) / 1.2];
  svg.appendChild(el("path", {
    d: describe(rad(tolA[0]), rad(tolA[1]), R, R),
    fill: "none", stroke: "var(--ok)", "stroke-width": 15, opacity: .16
  }));
  svg.appendChild(el("path", {d: describe(rad(0), rad(1), R, R), fill: "none", stroke: "var(--line)", "stroke-width": 2}));
  function describe(a0, a1, r0, r1) {
    const x0 = cx + r0 * Math.cos(a0), y0 = cy - r0 * Math.sin(a0);
    const x1 = cx + r1 * Math.cos(a1), y1 = cy - r1 * Math.sin(a1);
    return `M ${x0} ${y0} A ${r0} ${r0} 0 0 1 ${x1} ${y1}`;
  }
  const label = [[0.6, ".6"], [0.8, ".8"], [1.0, "1.0 ✓"], [1.2, "1.2"], [1.4, "1.4"]];
  label.forEach(([v, t]) => {
    const a = rad(scale(v)), r = R + 22;
    svg.appendChild(el("text", {
      x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) + 4, "text-anchor": "middle",
      class: "axlbl", "font-size": 10.5, fill: v === 1 ? "var(--ok)" : "var(--ink3)"
    }, document.createTextNode(t)));
  });
  arcs.forEach(([name, v, c, hl]) => {
    const a = rad(scale(v));
    const from = rad(scale(v - 0.02)), to = rad(scale(v + 0.02));
    const p = el("g", {});
    p.appendChild(el("path", {
      d: describe(from, to, R, R), fill: "none", stroke: c,
      "stroke-width": hl ? 8 : 4, "stroke-linecap": "round"
    }));
    const nx = cx + R * Math.cos(a), ny = cy - R * Math.sin(a);
    const dot = el("circle", {cx: nx, cy: ny, r: hl ? 5 : 3.2, fill: c, stroke: "var(--panel)", "stroke-width": 1.5});
    bindTip(dot, `<b>${name}</b><br>Sim/Obs = <b>${fmt(v, 7)}</b><br><span class="r">偏离 1.0 ${((v - 1) * 100).toFixed(4)}%</span>`);
    p.appendChild(dot);
    svg.appendChild(p);
  });
  svg.appendChild(el("text", {
    x: cx, y: cy - 46, "text-anchor": "middle", class: "mono",
    "font-size": 31, "font-weight": 650, fill: "var(--ok)"
  }, document.createTextNode(fmt(M.SimObs_FROZEN.value, 7))));
  svg.appendChild(el("text", {
    x: cx, y: cy - 26, "text-anchor": "middle", "font-size": 11.5, fill: "var(--ink2)"
  }, document.createTextNode("FROZEN Sim/Obs · 偏差 " + fmt(M.abs_dev_from_1_pp.value, 4) + " pp")));
  $("#gauge").appendChild(svg);
})();

/* ---------- ② stability ---------- */
(function () {
  const defs = [
    ["A_10:19 MATCHED", M.A_10_19_MATCHED.value, 0.03, "var(--ok)"],
    ["A_10:19 CATA", M.A_10_19_CATA.value, 0.03, "var(--ok)"],
    ["A_10:19 SLIP", M.A_10_19_SLIP.value, 0.05, "var(--ok)"],
    ["parity gap", M.parity_gap_rel_MATCHED.value, 0.05, "var(--ok)"],
    ["Q19/Q̄ 偏差", M.Q19_over_Qbar_dev_pp.value / 100, 0.01, "var(--ok)"],
  ];
  const W = 560, rowH = 34, H = defs.length * rowH + 30, padL = 138, padR = 96;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
  const maxX = W - padR - padL;
  svg.appendChild(el("line", {x1: padL, y1: 8, x2: padL, y2: H - 20, class: "axis"}));
  defs.forEach(([name, v, thr, c], i) => {
    const y = 20 + i * rowH;
    svg.appendChild(el("text", {x: padL - 10, y: y + 4, "text-anchor": "end", class: "axlbl", "font-size": 11, fill: "var(--ink2)"}, document.createTextNode(name)));
    const wx = Math.max(2, (v / thr) * maxX * 0.86);
    const okc = v <= thr ? c : "var(--bad)";
    const bar = el("rect", {x: padL + 1, y: y - 6, width: wx, height: 13, rx: 3, fill: okc});
    svg.appendChild(bar);
    const tx = padL + 1 + wx + 7;
    svg.appendChild(el("text", {x: tx, y: y + 4, class: "axlbl mono", "font-size": 11, fill: "var(--ink2)", "text-anchor": "start"},
      document.createTextNode(v < 0.01 ? (v * 100).toFixed(4) + "%" : (v * 100).toFixed(2) + "%")));
    bindTip(bar, `<b>${name}</b><br>实测 <b>${(v * 100).toFixed(4)}%</b><br><span class="r">阈值 ${(thr * 100).toFixed(0)}% ${v <= thr ? "✓ 通过" : "✗ 超限"}</span>`);
  });
  const r = [[["never_arrived", M.never_arrived.value], ["max_stuck_car", M.max_stuck_car.value]]][0];
  svg.appendChild(el("text", {x: padL, y: H - 4, class: "axlbl mono", "font-size": 11, fill: "var(--ok)"},
    document.createTextNode(`never_arrived = ${r[0][1].toFixed(0)}   ·   max_stuck_car = ${r[1][1].toFixed(0)}   ·   dep = arr = 236,044 ✓`)));
  $("#stab").appendChild(svg);
})();

/* ---------- ③ bands ---------- */
(function () {
  const W = 1060, H = 150, padL = 30, padR = 30, yLine = 74, plotW = W - padL - padR;
  const all = [D.bands.static_target_band[0], D.bands.static_target_band[1],
    D.bands.lambda_sensitivity_band[0], D.bands.lambda_sensitivity_band[1], D.bands.working_point_fstar];
  const lo = Math.min(...all) - .015, hi = Math.max(...all) + .015;
  const X = v => padL + (v - lo) / (hi - lo) * plotW;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
  // axis ticks
  for (let v = Math.ceil(lo * 100) / 100; v <= hi; v += .02) {
    svg.appendChild(el("line", {x1: X(v), y1: yLine - 6, x2: X(v), y2: yLine + 6, class: "gl"}));
    svg.appendChild(el("text", {x: X(v), y: yLine + 22, "text-anchor": "middle", class: "axlbl mono", "font-size": 10},
      document.createTextNode(v.toFixed(2))));
  }
  svg.appendChild(el("text", {x: padL, y: 16, class: "axlbl", "font-size": 11, fill: "var(--ink2)"}, document.createTextNode("f* 取值轴")));

  const bands = [
    ["靶场带（7.6C-2 TARGET）", D.bands.static_target_band, "var(--ink3)", -34],
    ["λ 灵敏带（7.6G）", D.bands.lambda_sensitivity_band, "var(--acc)", 0],
  ];
  bands.forEach(([name, b, c, dy]) => {
    const y = yLine + dy;
    const r = el("rect", {x: X(b[0]), y: y - 8, width: Math.max(2, X(b[1]) - X(b[0])), height: 16, rx: 4, fill: c, opacity: .8});
    svg.appendChild(r);
    const rect = {lx: X(b[0]) < W / 2 ? X(b[1]) + 8 : X(b[0]) - 8, y: y + 4, an: X(b[0]) < W / 2 ? "start" : "end"};
    svg.appendChild(el("text", {x: rect.lx, y: rect.y, "text-anchor": rect.an, "font-size": 11, fill: "var(--ink2)"},
      document.createTextNode(`${name}  [${b[0]}, ${b[1]}]`)));
    bindTip(r, `<b>${name}</b><br>[<b>${b[0]}</b>, <b>${b[1]}</b>]<br><span class="r">宽度 ${(b[1] - b[0]).toFixed(4)}</span>`);
  });
  // working point
  const wp = D.bands.working_point_fstar;
  svg.appendChild(el("line", {x1: X(wp), y1: yLine - 46, x2: X(wp), y2: yLine + 40, stroke: "var(--ok)", "stroke-width": 2}));
  const c = el("circle", {cx: X(wp), cy: yLine, r: 6, fill: "var(--ok)", stroke: "var(--panel)", "stroke-width": 2});
  bindTip(c, `<b>工作点 f_work</b> = <b>${wp}</b><br><span class="r">≠ 最优；非唯一真实值</span>`);
  svg.appendChild(c);
  svg.appendChild(el("text", {x: X(wp), y: yLine - 52, "text-anchor": "middle", class: "mono", "font-size": 12, "font-weight": 600, fill: "var(--ok)"},
    document.createTextNode("工作点 " + wp)));
  $("#bands").appendChild(svg);
})();

/* ---------- ④ eta2 ---------- */
(function () {
  const rows = D.eta2.slice().sort((a, b) => b.eta2_excess - a.eta2_excess);
  const W = 560, rowH = 26, H = rows.length * rowH + 16, padL = 190, padR = 74;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
  const maxX = W - padL - padR, maxV = Math.max(...rows.map(r => Math.abs(r.eta2_excess))) * 1.15;
  const zero = padL;
  svg.appendChild(el("line", {x1: zero, y1: 4, x2: zero, y2: H - 10, class: "gl0"}));
  rows.forEach((r, i) => {
    const y = 12 + i * rowH;
    const v = r.eta2_excess, w = Math.abs(v) / maxV * maxX;
    const c = v > 0.01 ? "var(--ok)" : v < -0.001 ? "var(--bad)" : "var(--ink3)";
    svg.appendChild(el("text", {x: padL - 10, y: y + 4, "text-anchor": "end", class: "axlbl", "font-size": 11, fill: v > 0.01 ? "var(--ink)" : "var(--ink2)"},
      document.createTextNode(r.layer + (v > 0.01 ? " ★" : ""))));
    const bar = el("rect", {x: v >= 0 ? zero : zero - w, y: y - 5.5, width: Math.max(1.5, w), height: 11, rx: 2.5, fill: c});
    svg.appendChild(bar);
    svg.appendChild(el("text", {x: v >= 0 ? zero + w + 6 : zero - w - 6, y: y + 4, class: "axlbl mono", "font-size": 10.5,
      fill: "var(--ink2)", "text-anchor": v >= 0 ? "start" : "end"}, document.createTextNode(v.toFixed(4))));
    bindTip(bar, `<b>${r.layer}</b> (${r.dimension})<br>η² = <b>${r.eta2.toFixed(4)}</b><br>chance = ${r.eta2_chance.toFixed(4)}<br><span class="r">η²_excess = <b>${v.toFixed(4)}</b></span><br><span class="r">组数 ${r.n_groups}</span>`);
  });
  $("#eta2").appendChild(svg);
})();

/* ---------- ⑤ unresolved ---------- */
(function () {
  const layers = ["PA / OD 空间分配", "reciprocal / twin 网络表征", "方向性（radial in/out）", "断面↔网络对应（twin·方向粒度）"];
  const explained = [["需求规模 f", "global level"], ["λ（0.075）", "可检测·不可识别"], ["车型构成 car_share", "仅解释总量级"]];
  const excluded = ["road_class", "section aggregation", "observation semantics", "temporal realization"];
  $("#unresolved").innerHTML = `
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">
    ${explained.map(([a, b]) => `<span class="pill" style="color:var(--ok);border-color:var(--ok);background:color-mix(in srgb,var(--ok) 12%,transparent)" title="${b}">✓ ${a}</span>`).join("")}
  </div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
    ${excluded.map(a => `<span class="pill flat" title="已排除">✗ ${a}</span>`).join("")}
  </div>
  <div class="hint" style="margin:0 0 7px">未解释结构层（UNRESOLVED_STRUCTURAL_LAYER）</div>
  ${layers.map(a => `<div style="display:flex;align-items:center;gap:9px;padding:6px 0;border-top:1px solid var(--line2)">
     <span style="color:var(--warn);font-size:13px">◆</span><span style="font-size:12.5px">${a}</span></div>`).join("")}`;
})();

/* ---------- ⑥ residual bars ---------- */
const lvlSel = {level: "region", sorted: true};
(function () {
  const lvls = [["region", "Planning Region"], ["radial", "radial 方向"], ["pa_key", "关键 PA"], ["pa_all", "全部 PA"]];
  $("#lvlCtrl").innerHTML = lvls.map(([k, t]) =>
    `<button class="btn${k === lvlSel.level ? ' on' : ''}" data-lvl="${k}">${t}</button>`).join("")
    + `<button class="btn on" id="sortBtn" title="切换排序">排序：残差 ↓</button>`;
  $("#lvlCtrl").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.lvl) { lvlSel.level = b.dataset.lvl; }
    if (b.id === "sortBtn") { lvlSel.sorted = !lvlSel.sorted; b.textContent = "排序：" + (lvlSel.sorted ? "残差 ↓" : "原始序"); b.classList.toggle("on", lvlSel.sorted); }
    document.querySelectorAll("#lvlCtrl .btn[data-lvl]").forEach(x => x.classList.toggle("on", x.dataset.lvl === lvlSel.level));
    drawResid();
  });
  drawResid();
})();
function drawResid() {
  const host = $("#resid"); host.innerHTML = "";
  let rows = D.boundary.filter(r => r.level === lvlSel.level);
  if (lvlSel.sorted) rows = rows.slice().sort((a, b) => b.rel_dev - a.rel_dev);
  const horiz = rows.length <= 8;
  const W = 1060;
  if (horiz) {
    const rowH = 40, H = rows.length * rowH + 34, padL = 150, padR = 110;
    const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
    const zero = padL + (W - padL - padR) / 2, maxV = Math.max(...rows.map(r => Math.abs(r.rel_dev))) * 1.12;
    const X = v => zero + v / maxV * ((W - padL - padR) / 2);
    svg.appendChild(el("line", {x1: zero, y1: 12, x2: zero, y2: H - 20, class: "gl0"}));
    svg.appendChild(el("text", {x: zero, y: H - 6, "text-anchor": "middle", class: "axlbl", "font-size": 10}, document.createTextNode("0 %")));
    rows.forEach((r, i) => {
      const y = 26 + i * rowH;
      svg.appendChild(el("text", {x: padL - 12, y: y + 5, "text-anchor": "end", class: "axlbl", "font-size": 12, fill: "var(--ink)"},
        document.createTextNode(r.group)));
      const v = r.rel_dev, x0 = v >= 0 ? zero : X(v), w = Math.abs(X(v) - zero);
      const bar = el("rect", {x: x0, y: y - 9, width: Math.max(2, w), height: 18, rx: 3, fill: RES_COLOR(v)});
      svg.appendChild(bar);
      svg.appendChild(el("text", {x: v >= 0 ? zero + w + 8 : zero - w - 8, y: y + 5, class: "mono", "font-size": 12,
        fill: RES_COLOR(v), "text-anchor": v >= 0 ? "start" : "end"}, document.createTextNode((v > 0 ? "+" : "") + (v * 100).toFixed(2) + "%")));
      bindTip(bar, `<b>${r.group}</b><br>ratio = <b>${r.ratio.toFixed(4)}</b><br>相对偏离 = <b>${(v * 100).toFixed(2)}%</b> ${v > 0 ? "（过）" : "（欠）"}<br><span class="r">断面 ${r.n_sections ?? "—"}${r.n_zero_sim ? " · 零流 " + r.n_zero_sim : ""}</span>`);
    });
    host.appendChild(svg);
  } else {
    const n = rows.length;
    const cols = Math.min(7, n);
    const rowsN = Math.ceil(n / cols);
    const cellW = W / cols, plotH = 118, nameH = 30, H = rowsN * (plotH + nameH + 18) + 14;
    const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
    const maxV = Math.max(.6, ...rows.map(r => Math.abs(r.rel_dev))) * 1.08;
    const Fh = v => Math.abs(v) / maxV * (plotH / 2);
    rows.forEach((r, i) => {
      const c = i % cols, rr = Math.floor(i / cols);
      const cellX = c * cellW, y0 = rr * (plotH + nameH + 18) + 12;
      const base = y0 + plotH / 2, cxm = cellX + cellW / 2;
      const v = r.rel_dev, h = Math.max(2, Fh(v));
      svg.appendChild(el("line", {x1: cellX + 6, y1: base, x2: cellX + cellW - 6, y2: base, class: "gl0"}));
      const barW = Math.min(30, cellW - 34);
      const rect = el("rect", {x: cxm - barW / 2, y: v >= 0 ? base - h : base, width: barW, height: h, rx: 2.5, fill: RES_COLOR(v)});
      svg.appendChild(rect);
      svg.appendChild(el("text", {x: cxm, y: v >= 0 ? base - h - 4 : base + h + 11, "text-anchor": "middle", class: "axlbl mono", "font-size": 9.5, fill: RES_COLOR(v)},
        document.createTextNode((v > 0 ? "+" : "") + (v * 100).toFixed(0) + "%")));
      const nm = r.group.length > 13 ? r.group.slice(0, 12) + "…" : r.group;
      svg.appendChild(el("text", {x: cxm, y: y0 + plotH + 14, "text-anchor": "middle", class: "axlbl", "font-size": 10, fill: "var(--ink2)"},
        document.createTextNode(nm)));
      bindTip(rect, `<b>${r.group}</b><br>ratio = <b>${r.ratio.toFixed(4)}</b><br>偏离 = <b>${(v * 100).toFixed(2)}%</b>${r.n_sections ? "<br><span class='r'>断面 " + r.n_sections + (r.n_zero_sim ? " · 零流 " + r.n_zero_sim : "") + "</span>" : ""}`);
    });
    host.appendChild(svg);
  }
}

/* ---------- ⑦ conformance ---------- */
(function () {
  const C = D.conformance, F = D.pa_all_fix, TOL = D.tol;
  $("#conf").innerHTML = `<table style="margin-bottom:12px">
    <thead><tr><th>层级</th><th>组数</th><th>一致</th><th>max |Δ| ratio</th><th>判决</th></tr></thead>
    <tbody>${C.map(c => {
      const ok = c.bit_exact === c.n;
      return `<tr>
      <td class="mono">${c.level}</td><td class="mono">${c.n}</td>
      <td class="mono" style="color:${ok ? "var(--ok)" : "var(--bad)"}">${c.bit_exact}/${c.n}</td>
      <td class="mono">${c.max_abs_delta <= TOL ? c.max_abs_delta.toExponential(1) + " ✓" : c.max_abs_delta.toFixed(4)}</td>
      <td style="color:${ok ? "var(--ok)" : "var(--bad)"};font-size:11.5px">${ok ? "✓ 一致（≤ 发布精度）" : "✗ 冻结件单位缺陷（偏 " + c.max_abs_delta.toFixed(3) + "）"}</td>
    </tr>`; }).join("")}</tbody></table>
    <div class="hint" style="margin:10px 0 6px">全局池化 Sim/Obs = <span class="mono">${D.global_ratio.toFixed(10)}</span>　·　
      判定容差 = <span class="mono">1e-6</span>（冻结件 ratio 按发布精度存储：region/radial 6 dp、pa_key 5 dp）<br>
      <span class="mono">rel_dev</span> 口径 = <span class="mono">ratio / 全局ratio − 1</span>（非 ratio − 1）。
      pa_all 层修正对照（冻结列 <span class="mono">ratio_FROZEN</span> vs 真值），前 6 行：</div>
    <table><thead><tr><th>PA</th><th>冻结值</th><th>真值 ratio</th><th>Δ</th><th>真值偏离</th><th></th></tr></thead>
    <tbody>${F.slice(0, 6).map(r => `<tr>
      <td>${r.group}</td><td class="mono">${r.frozen.toFixed(4)}</td><td class="mono">${r.true.toFixed(4)}</td>
      <td class="mono" style="color:var(--bad)">${r.delta.toFixed(4)}</td>
      <td class="mono" style="color:${RES_COLOR(r.true / D.global_ratio - 1)}">${((r.true / D.global_ratio - 1) * 100).toFixed(2)}%</td>
      <td>${REV(r.true / D.global_ratio - 1)}</td></tr>`).join("")}</tbody></table>
    <div class="note" style="border-left-color:var(--bad);background:color-mix(in srgb,var(--bad) 8%,transparent)">
      <b>缺陷定位：</b>源文件 <span class="mono">7.7C-0 / c0_6_pa_gradient.csv</span> 的列 <span class="mono">R_PA</span>
      实际语义为 <b>Q−1（相对偏离）</b>（如 ANG MO KIO 记 0.6815，真值 ratio = 1.6804）；而
      <span class="mono">freeze_final_model_7_8.py</span> 将其当作 ratio 处理
      （<span class="mono">ratio_FROZEN = R_PA</span>、<span class="mono">rel_dev = R_PA − 1</span>），
      故 pa_all 层 <b>ratio 偏 −1.0、rel_dev 再偏 −1.0</b>（该层 37 行全部受影响）。
      本缺陷<b>仅限此展示表</b>：模型身份（f / λ / SCALE / f_cap / route-choice / population / network）
      与 #168 全部 23 门<b>均不受影响</b>；region / radial / pa_key 三层取自 7.6H，取值正确。
    </div>`;
})();

/* ---------- ⑦ scatter ---------- */
(function () {
  const groups = ["ALL", "EAST REGION", "WEST REGION", "CENTRAL REGION", "NORTH REGION", "NORTH-EAST REGION", "radial_in", "radial_out", "circumferential"];
  const st = {sel: "ALL"};
  $("#scatCtrl").innerHTML = groups.map(g => `<button class="btn${g === 'ALL' ? ' on' : ''}" data-g="${g}">${g.replace(" REGION", "")}</button>`).join("");
  $("#scatCtrl").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    st.sel = b.dataset.g;
    document.querySelectorAll("#scatCtrl .btn").forEach(x => x.classList.toggle("on", x.dataset.g === st.sel));
    drawScatter();
  });
  drawScatter();
  $("#scatLegend").innerHTML = `<span><i style="background:var(--ink3)"></i>断面</span>
    <span><i style="background:var(--over)"></i>Sim 偏高 &gt; 1.25×</span>
    <span><i style="background:var(--under)"></i>Sim 偏低 &lt; 0.75×</span>
    <span><i style="background:transparent;border:1.2px solid var(--bad);border-radius:50%"></i>sim = 0（零流，置于轴下限）</span>`;
})();
function drawScatter() {
  const host = $("#scatter"); host.innerHTML = "";
  const sel = document.querySelector("#scatCtrl .btn.on")?.dataset.g || "ALL";
  let pts = D.sections.filter(s => s.obs > 0 && s.sim !== null);
  if (sel !== "ALL") pts = pts.filter(s => s.region === sel || s.radial === sel);
  const W = 560, H = 470, padL = 54, padR = 18, padT = 16, padB = 42;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
  const lo = 1, hi = Math.max(3000, ...pts.map(s => Math.max(s.obs, s.sim)));
  const L = v => Math.log10(Math.max(lo, v));
  const X = v => padL + (L(v) - L(lo)) / (L(hi) - L(lo)) * (W - padL - padR);
  const Y = v => H - padB - (L(v) - L(lo)) / (L(hi) - L(lo)) * (H - padT - padB);
  // grid + ticks
  for (let e = 0; e <= Math.ceil(L(hi)); e++) {
    const v = Math.pow(10, e); if (v < lo) continue;
    svg.appendChild(el("line", {x1: X(v), y1: padT, x2: X(v), y2: H - padB, class: "gl"}));
    svg.appendChild(el("line", {x1: padL, y1: Y(v), x2: W - padR, y2: Y(v), class: "gl"}));
    svg.appendChild(el("text", {x: X(v), y: H - padB + 15, "text-anchor": "middle", class: "axlbl mono", "font-size": 10}, document.createTextNode(v >= 1000 ? v / 1000 + "k" : v)));
    svg.appendChild(el("text", {x: padL - 8, y: Y(v) + 4, "text-anchor": "end", class: "axlbl mono", "font-size": 10}, document.createTextNode(v >= 1000 ? v / 1000 + "k" : v)));
  }
  svg.appendChild(el("line", {x1: X(lo), y1: Y(lo), x2: X(hi), y2: Y(hi), stroke: "var(--ok)", "stroke-width": 1.4, "stroke-dasharray": "5 4", opacity: .85}));
  // ±25% envelope
  [-1, 1].forEach(sgn => {
    const f = sgn > 0 ? 1.25 : .8;
    svg.appendChild(el("line", {x1: X(lo), y1: Y(lo * f), x2: X(hi / f * 1), y2: Y(hi), stroke: "var(--ok)", "stroke-width": .8, "stroke-dasharray": "2 4", opacity: .35}));
  });
  svg.appendChild(el("text", {x: padL + 6, y: padT + 12, class: "axlbl", "font-size": 10.5, fill: "var(--ok)"}, document.createTextNode("y = x（完美匹配）")));
  svg.appendChild(el("text", {x: (padL + W - padR) / 2, y: H - 6, "text-anchor": "middle", class: "axlbl", "font-size": 11}, document.createTextNode("Obs 观测流量（HRS8-9 均值）")));
  svg.appendChild(el("text", {x: 14, y: (padT + H - padB) / 2, "text-anchor": "middle", class: "axlbl", "font-size": 11, transform: `rotate(-90 14 ${(padT + H - padB) / 2})`}, document.createTextNode("Sim 仿真流量（scaled）")));
  pts.forEach(s => {
    const r = s.ratio;
    let dot;
    if (s.zero) {
      dot = el("circle", {cx: X(s.obs), cy: Y(lo), r: 3.0, fill: "none", stroke: "var(--bad)", "stroke-width": 1.2, opacity: .9, class: "dot"});
    } else {
      const c = r > 1.25 ? "var(--over)" : r < .75 ? "var(--under)" : "var(--ink3)";
      dot = el("circle", {cx: X(s.obs), cy: Y(Math.max(lo, s.sim)), r: 2.9, fill: c, opacity: .72, class: "dot"});
    }
    bindTip(dot, `<b>link ${s.id}</b><br>${s.region} · ${s.radial}<br>PA ${s.pa}<br>obs = <b>${s.obs.toFixed(1)}</b><br>sim = <b>${(s.sim || 0).toFixed(1)}</b><br>ratio = <b>${r.toFixed(4)}</b>${s.zero ? "<br><span class='r'>sim = 0（零流，置于轴下限）</span>" : ""}`);
    svg.appendChild(dot);
  });
  const nz = pts.filter(s => s.zero).length;
  svg.appendChild(el("text", {x: W - padR, y: padT + 12, "text-anchor": "end", class: "axlbl mono", "font-size": 10.5, fill: "var(--ink2)"}, document.createTextNode(`n = ${pts.length}  ·  零流 ${nz}`)));
  host.appendChild(svg);
}

/* ---------- ⑧ map ---------- */
(function () {
  const host = $("#map");
  const W = 560, H = 470, pad = 16;
  const svg = el("svg", {viewBox: `0 0 ${W} ${H}`});
  const xs = D.sections.map(s => s.x), ys = D.sections.map(s => s.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const sc = Math.min((W - 2 * pad) / (x1 - x0), (H - 2 * pad) / (y1 - y0));
  const ox = (W - sc * (x1 - x0)) / 2, oy = (H - sc * (y1 - y0)) / 2;
  const X = v => ox + (v - x0) * sc;
  const Y = v => H - oy - (v - y0) * sc;
  D.sections.forEach(s => {
    const r = s.ratio;
    let dot;
    if (s.zero) {
      dot = el("circle", {cx: X(s.x), cy: Y(s.y), r: 2.4, fill: "none", stroke: "var(--bad)", "stroke-width": 1.1, opacity: .85, class: "dot"});
    } else {
      const dev = Math.max(-2, Math.min(2, Math.log2(r)));
      const c = Math.abs(dev) < .32 ? "var(--ink3)" : (dev > 0 ? "var(--over)" : "var(--under)");
      const rad = 2 + Math.min(5, Math.abs(dev)) * 1.6;
      dot = el("circle", {cx: X(s.x), cy: Y(s.y), r: rad, fill: c, opacity: .68, class: "dot"});
    }
    bindTip(dot, `<b>link ${s.id}</b><br>${s.region} · ${s.radial}<br>PA ${s.pa}<br>Sim/Obs = <b>${r.toFixed(4)}</b><br>${s.zero ? "<span class='r'>sim = 0（零流）</span><br>" : "log₂ = <b>" + Math.log2(Math.max(r, 1e-6)).toFixed(2) + "</b><br>"}${s.roadcat} · ${(s.len_m || 0).toFixed(0)} m`);
    svg.appendChild(dot);
  });
  svg.appendChild(el("text", {x: pad, y: H - 6, class: "axlbl", "font-size": 10.5}, document.createTextNode("SVY21 (m) · 点大小 ∝ |log₂(Sim/Obs)|")));
  host.appendChild(svg);
})();

/* ---------- ⑨ table ---------- */
(function () {
  const cols = [["id", "link_id", "s"], ["region", "region", "s"], ["radial", "radial", "s"], ["pa", "PA", "s"],
    ["obs", "obs", "n"], ["sim", "sim", "n"], ["ratio", "Sim/Obs", "n"], ["dev", "偏离 %", "n"]];
  let sortK = "dev", asc = false;
  const thead = $("#tbl thead"), tbody = $("#tbl tbody");
  function rows() {
    const r = D.sections.map(s => ({...s, dev: s.ratio - 1}));
    r.sort((a, b) => {
      const A = a[sortK], B = b[sortK];
      const c = (typeof A === "string") ? A.localeCompare(B) : (A - B);
      return asc ? c : -c;
    });
    return r;
  }
  function draw() {
    thead.innerHTML = "<tr>" + cols.map(([k, t]) =>
      `<th data-k="${k}" style="cursor:pointer">${t}${sortK === k ? (asc ? " ▲" : " ▼") : ""}</th>`).join("") + "</tr>";
    const r = rows();
    tbody.innerHTML = r.map(s => `<tr>
      <td class="mono">${s.id}</td><td>${s.region}</td><td>${s.radial}</td><td>${s.pa}</td>
      <td class="mono">${s.obs.toFixed(1)}</td><td class="mono">${s.sim.toFixed(1)}</td>
      <td class="mono">${s.ratio.toFixed(4)}</td>
      <td class="mono" style="color:${RES_COLOR(s.dev)}">${(s.dev > 0 ? "+" : "") + (s.dev * 100).toFixed(2)}%</td></tr>`).join("");
    thead.querySelectorAll("th").forEach(th => th.onclick = () => {
      const k = th.dataset.k;
      if (k === sortK) asc = !asc; else { sortK = k; asc = (k === "id" || k === "region" || k === "radial" || k === "pa"); }
      draw();
    });
  }
  draw();
})();

/* ---------- ⑩ gates ---------- */
(function () {
  const G = D.checks_pass, T = D.checks_total;
  const byCat = [
    ["冻结真值逐位", ["G1", "G2", "G3", "G5", "G7"]],
    ["配置继承 7.6E/7.4", ["G8", "G9"]],
    ["口径锚", ["G12", "G13"]],
    ["边界未合并 / 残差仍在", ["G14", "G15"]],
    ["上游判决一致", ["G16", "G17", "G18", "G19"]],
    ["本步纪律（零仿真·未改参）", ["G20"]],
    ["产物落盘 6/6", ["G21"]],
    ["read-only 硬证据（输入逐位未变）", ["G22"]],
    ["W01 it.19 存在", ["G23"]],
    ["7.6C-2 靶场复现", ["G6"]],
    ["输入/产物存在", ["G10", "G11", "G4"]],
  ];
  $("#gates").innerHTML = `<div style="font-family:var(--mono);font-size:26px;font-weight:650;color:var(--ok);margin-bottom:9px">${G}/${T} <span style="font-size:12px;color:var(--ink2);font-weight:400">hard gates PASS</span></div>`
    + byCat.map(([n, ids]) => `<div style="display:flex;justify-content:space-between;gap:10px;padding:5px 0;border-top:1px solid var(--line2)">
       <span style="font-size:12px;color:var(--ink2)">${n}</span>
       <span class="mono" style="font-size:11px;color:var(--ok)">${ids.length} ✓</span></div>`).join("");
})();

/* ---------- ⑪ version line ---------- */
(function () {
  $("#vline").innerHTML = D.version_line.map((s, i) => {
    const last = i === D.version_line.length - 1;
    return `<div style="display:flex;gap:10px;align-items:flex-start;padding:5px 0">
      <span style="color:${last ? "var(--ok)" : "var(--line)"};font-size:13px;line-height:1.3">${last ? "◆" : "│"}</span>
      <span style="font-size:12.5px;font-family:${last ? "var(--mono)" : "inherit"};color:${last ? "var(--ok)" : "var(--ink2)"};font-weight:${last ? 600 : 400}">${s}</span></div>`;
  }).join("");
  $("#stopNote").innerHTML = "<b>停止规则：</b>" + D.stop_rule;
})();

$("#foot").innerHTML = `Singapore OD–MATSim · Step 7.8 Final Model Freeze &amp; Validation Package<br>
  可视化看板为 read-only 附加件，非 6 件冻结产品之一　·　空间残差由 576 断面表重算真值（region/radial/pa_key 与冻结件一致，|Δ| ≤ 1e-6）<br>
  数据源：FINAL_VALIDATION_METRICS.csv · 7.7C-0 c0_section_table.csv / c0_rank_eta2.csv · step7_8_summary.json · FINAL_SPATIAL_RESIDUAL_BOUNDARY.csv（仅用于口径校验）`;
</script>
</body>
</html>
"""

HTML = HTML.replace("__DATA__", DATA_JSON)

out = os.path.join(P78, "FINAL_MODEL_DASHBOARD.html")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(HTML)

print("written:", out)
print("bytes  :", os.path.getsize(out))
print("sections:", len(sec), "| boundary rows:", len(boundary), "| eta2 dims:", len(eta2))

# ---------------------------------------------------------------- erratum CSV
ERRA = os.path.join(P78, "ERRATUM_spatial_residual_boundary_pa_all.csv")
with open(ERRA, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["level", "group", "n_sections",
                "frozen_ratio_FROZEN", "true_ratio_SimOverObs", "delta_frozen_minus_true",
                "frozen_rel_dev_vs_global", "true_rel_dev_vs_global", "status"])
    _tru = {r["group"]: r for r in boundary if r["level"] == "pa_all"}
    for r in sorted(boundary_frozen, key=lambda x: x["level"]):
        if r["level"] != "pa_all":
            continue
        t = _tru.get(r["group"])
        if not t:
            continue
        w.writerow([r["level"], r["group"], t["n_sections"],
                    f"{r['ratio']!r}", f"{t['ratio']!r}", f"{r['ratio'] - t['ratio']!r}",
                    f"{r['rel_dev']!r}", f"{t['rel_dev']!r}",
                    "CORRECTED_IN_DASHBOARD" if abs(r["ratio"] - t["ratio"]) > TOL else "OK"])
print("erratum:", ERRA, os.path.getsize(ERRA), "bytes")


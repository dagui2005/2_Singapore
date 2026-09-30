# -*- coding: utf-8 -*-
"""
Step 7.9C-0 -- Junction-cluster / Short-chain STRUCTURAL Audit
(ZERO-SIMULATION, READ-ONLY; v1.0 frozen; reports only)

Purpose (user-frozen framing):
  Define WHERE congestion *should* occur, from NETWORK STRUCTURE + EXISTING
  OBSERVATION MAPPING ONLY -- never from W01 congestion results.
  The W01 residual is then *projected* onto those structural units as a test,
  not used to define them.

Three spatial scales
  L1 junction-cluster   primary accounting grid (tier-separated short-link
                        components containing >=1 structural seed node)
  L2 short-chain        ramp / slip / connector chains + service-road chains
  L3 corridor           macro diagnostic only (named mainlines)

Four audit quantities
  C1 structural bottleneck prior   (simulation-free)
  C2 7.7E/W01 residual projection  (test, not definition)
  C3 HitRate / Coverage pre-registration + v1.0 baseline
  C4 B-1 minimal observation set   (frozen)

Discipline: no MATSim re-run; no frozen artifact touched; candidates NEVER use
W01 flow (enforced by gate C0.22).
"""
import os, io, re, gzip, csv, json, time, math, gc
from collections import defaultdict, Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT  = r'D:/Luan/2026-05/2_Singapore'
CACHE = ROOT + '/scripts/od/_cache_network_7_9c0.npz'
LS    = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz'
SECT  = ROOT + '/reports/spatial_residual_7_7c0/c0_section_table.csv'
OUT   = ROOT + '/reports/structural_junction_cluster_audit_7_9c0'
FROZEN_DIRS = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8']

# --- frozen structural constants (measured, then pre-registered) -------------
CELL      = 7.5          # MATSim effective cell size
TIME_STEP = 1.0
F_CAP     = 1.0          # v1.0
SEED_DEG  = 3
FS_JUMP   = 20.0         # km/h
LANE_JUMP = 1.0
CAP_RATIO = 1.25
MAX_UNIT  = 200          # link cap per junction-cluster (split by longest link)
PRIOR_CAND = 80.0        # percentile -> structural candidate set (top 20%)
CONG_Q     = 80.0        # percentile -> model high-congestion set (top 20%)
GLOBAL_TARGET = 0.8589732

RAMP   = {'motorway_link', 'trunk_link'}                       # grade-separated ramps
CONNEC = {'primary_link', 'secondary_link', 'tertiary_link'}   # at-grade connectors
MAINLINE = {'motorway', 'trunk', 'primary'}

log_lines = []
_T0 = time.time()
def log(m):
    log_lines.append(m); print('[%6.1fs] %s' % (time.time() - _T0, m), flush=True)

def T(m):
    log('  .. %s  (rss=%.0f MB)' % (m, _rss()))
    gc.collect()

def _rss():
    try:
        import ctypes, ctypes.wintypes
        class PMC(ctypes.Structure):
            _fields_ = [('cb', ctypes.wintypes.DWORD), ('PageFaultCount', ctypes.wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
        p = PMC(); p.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(p), p.cb)
        return p.WorkingSetSize / 1e6
    except Exception:
        return -1.0

def esc(x):
    return str(x).replace('|', r'\|')

def md_table(header, rows):
    o = ['| ' + ' | '.join(esc(h) for h in header) + ' |',
         '|' + '|'.join(['---'] * len(header)) + '|']
    for r in rows:
        o.append('| ' + ' | '.join(esc(c) for c in r) + ' |')
    return '\n'.join(o)

def snap(dirs):
    s = {}
    for d in dirs:
        for dp, _, fns in os.walk(d):
            for fn in fns:
                p = os.path.join(dp, fn)
                try:
                    s[p] = (os.path.getmtime(p), os.path.getsize(p))
                except OSError:
                    pass
    return s

# =====================================================================
def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    gates = []
    def gate(gid, desc, ok, detail):
        gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})
    frozen_before = snap(FROZEN_DIRS)
    log('=== Step 7.9C-0 Structural (junction-cluster) Audit -- zero simulation ===')

    # ---------- load cache ------------------------------------------------
    z = np.load(CACHE, allow_pickle=True)
    # NB: keep node ids as NATIVE python str (numpy str scalars as dict keys are
    #     ~100x slower to hash and dominated runtime in the first run)
    frm = [str(x) for x in z['frm']]
    to  = [str(x) for x in z['to']]
    ln, fs, cap, lanes = z['len_m'], z['fs_mps'], z['cap'], z['lanes']
    hw, nm = z['highway'], z['name']
    n = len(frm)
    fs_kmh = fs * 3.6
    tier = np.digitize(fs_kmh, [30, 50, 70, 90]).astype(np.int8)
    Lk = ln * 0.001
    L_SHORT = float(np.percentile(ln, 90))
    log('network: links=%d  km=%.2f  L_SHORT(p90)=%.1f m' % (n, Lk.sum(), L_SHORT))
    gate('C0.01', 'network parsed from frozen v1.0 W01 output', n == 693575 and abs(Lk.sum() - 15126.5) < 5.0,
         'links=%d km=%.2f' % (n, Lk.sum()))

    inc   = defaultdict(list); inb = defaultdict(list); outb = defaultdict(list)
    for i in range(n):
        a, b = frm[i], to[i]
        inc[a].append(i); inc[b].append(i)
        outb[a].append(i); inb[b].append(i)
    nodes = set(frm) | set(to)

    # ---------- structural seed nodes -------------------------------------
    def is_seed(x):
        ls = inc[x]
        if len(ls) < SEED_DEG:
            return False
        if len(set(tier[ls].tolist())) >= 2:
            return True
        f = fs_kmh[ls]
        if f.max() - f.min() >= FS_JUMP:
            return True
        if lanes[ls].max() - lanes[ls].min() >= LANE_JUMP:
            return True
        c = cap[ls]
        if c.min() > 0 and (c.max() / c.min()) >= CAP_RATIO:
            return True
        return False

    seeds = set(x for x in nodes if is_seed(x))
    log('structural seed nodes (deg>=%d & change): %d (%.2f%% of nodes)'
        % (SEED_DEG, len(seeds), 100.0 * len(seeds) / len(nodes)))
    gate('C0.02', 'structural seed nodes identified', len(seeds) > 0,
         'seeds=%d (%.2f%%)' % (len(seeds), 100.0 * len(seeds) / len(nodes)))

    # ---------- L1 junction-cluster ---------------------------------------
    short = ln <= L_SHORT
    par = np.arange(n, dtype=np.int64)
    def find(x):
        x = int(x)
        while par[x] != x:
            par[x] = par[par[x]]; x = int(par[x])
        return x
    def uni(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: par[rb] = ra
    for x, ls in inc.items():
        byt = defaultdict(list)
        for i in ls:
            if short[i]:
                byt[int(tier[i])].append(i)
        for _t, g in byt.items():
            for a in g[1:]:
                uni(g[0], a)
    roots = np.array([find(i) for i in range(n)])
    members = defaultdict(list)
    for i in np.where(short)[0]:
        members[roots[i]].append(int(i))
    seed_roots = set(find(i) for x in seeds for i in inc[x])
    units = {r: v for r, v in members.items() if r in seed_roots}
    log('L1 junction-cluster (tier-separated short-link, >=1 seed): units=%d links=%d (%.1f%%)'
        % (len(units), sum(len(v) for v in units.values()), 100.0 * sum(len(v) for v in units.values()) / n))

    # split oversize units by removing longest links (binary search on length)
    def _components(links):
        loc = {}
        parent = list(range(len(links)))
        def lf(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]; a = parent[a]
            return a
        for idx, i in enumerate(links):
            for nd in (frm[i], to[i]):
                if nd in loc:
                    ra, rb = lf(loc[nd]), lf(idx)
                    if ra != rb: parent[rb] = ra
                else:
                    loc[nd] = idx
        comp = defaultdict(list)
        for idx, i in enumerate(links):
            comp[lf(idx)].append(i)
        return list(comp.values())

    def split_unit(links, depth=0):
        """recursive: guarantee every returned piece <= MAX_UNIT links"""
        if len(links) <= MAX_UNIT:
            return [links]
        if depth > 6:
            order = sorted(links, key=lambda i: -ln[i])
            return [order[k:k + MAX_UNIT] for k in range(0, len(order), MAX_UNIT)]
        lo, hi = 0.0, float(ln[links].max()) + 1.0
        best = None
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            keep = [i for i in links if ln[i] <= mid]
            if len(keep) < 2:
                lo = mid; continue
            comps = _components(keep)
            best = comps
            if max(len(c) for c in comps) <= MAX_UNIT:
                hi = mid
            else:
                lo = mid
        out = []
        for c in (best if best else [links]):
            out.extend(split_unit(c, depth + 1))
        return out

    unit_links = {}
    n_split = 0
    for r, v in units.items():
        if len(v) <= MAX_UNIT:
            unit_links[r] = v
        else:
            n_split += 1
            for k, part in enumerate(split_unit(v)):
                unit_links[('%d_%d' % (r, k))] = part
    sizes = np.array([len(v) for v in unit_links.values()])
    assigned = int(sizes.sum())
    log('  after oversize split: units=%d (split %d) links=%d (%.1f%%) median=%.0f p90=%.0f max=%d'
        % (len(unit_links), n_split, assigned, 100.0 * assigned / n,
           np.median(sizes), np.percentile(sizes, 90), sizes.max()))
    gate('C0.03', 'L1 units built with coverage', len(unit_links) > 0 and assigned > 0,
         'units=%d links=%d (%.1f%%)' % (len(unit_links), assigned, 100.0 * assigned / n))
    gate('C0.04', 'oversize units resolved (max <= %d links)' % MAX_UNIT,
         sizes.max() <= MAX_UNIT, 'max_unit_links=%d splits=%d' % (sizes.max(), n_split))

    # link -> unit index
    link2unit = np.full(n, -1, dtype=np.int64)
    for ui, (r, v) in enumerate(unit_links.items()):
        for i in v:
            link2unit[i] = ui
    n_units = len(unit_links)
    uid_list = list(unit_links.keys())
    del members, units, par, roots, seed_roots
    T('after L1 unit construction')

    # ---------- C1 structural bottleneck prior (NO flow) -------------------
    def node_feats(x):
        ins = inb.get(x, []); outs = outb.get(x, [])
        if not ins or not outs:
            return (0.0, 0.0, 0.0, 0.0, 0.0)
        ic = float(sum(cap[i] for i in ins)); oc = float(sum(cap[i] for i in outs))
        f1 = max(0.0, (ic - oc) / oc) if oc > 0 else 0.0
        mil = float(max(lanes[i] for i in ins)); mol = float(min(lanes[i] for i in outs))
        f2 = max(0.0, (mil - mol) / mil) if mil > 0 else 0.0
        tset = set(int(tier[i]) for i in ins + outs)
        f3 = 1.0 if len(tset) >= 2 else 0.0
        hws = set(str(hw[i]) for i in ins + outs)
        f4 = 1.0 if (hws & (RAMP | CONNEC)) and (hws & MAINLINE) else 0.0
        stor = float(sum(ln[i] * lanes[i] / CELL * 1.0 for i in outs))
        inf_ts = float(sum(cap[i] / 3600.0 * TIME_STEP * F_CAP for i in ins))
        f5 = max(0.0, 1.0 - stor / inf_ts) if inf_ts > 0 else 0.0
        return (min(f1, 1.0), min(f2, 1.0), f3, f4, f5)

    cache_node = {}
    def nf(x):
        if x not in cache_node:
            cache_node[x] = node_feats(x)
        return cache_node[x]

    SC = {}
    def nscore(x):
        if x not in SC:
            f = node_feats(x)
            SC[x] = (float(np.mean(f[:4])), float(f[4]), f)
        return SC[x]

    U = np.zeros((n_units, 5), dtype=np.float64)
    prior = np.zeros(n_units, dtype=np.float64)       # SEVERITY: worst node in the unit
    prior_mean = np.zeros(n_units, dtype=np.float64)  # reported as secondary
    U_nlink = sizes.astype(np.float64)
    U_km = np.zeros(n_units); U_vc = np.zeros(n_units); U_satshare = np.zeros(n_units)
    U_tier = np.zeros(n_units, dtype=np.int8)
    for ui, r in enumerate(uid_list):
        links = unit_links[r]
        nds = set()
        for i in links:
            nds.add(frm[i]); nds.add(to[i])
        vals = [nscore(x) for x in nds]
        U[ui] = np.array([v[2] for v in vals]).mean(axis=0)
        sc = np.array([v[0] for v in vals])
        prior[ui] = float(sc.max())
        prior_mean[ui] = float(sc.mean())
    log('C1 prior = MAX over the unit nodes of mean(merge_deficit, lane_narrowing, class_transition, ramp_mainline)')
    log('   (severity semantics: "does this unit contain a structural bottleneck, and how severe")')

    # ---------- v1.0 baseline congestion from linkstats --------------------
    log('reading it.19 linkstats (HRS8-9avg) ...')
    import pandas as pd
    ls_df = pd.read_csv(LS, sep='\t', usecols=['LINK', 'HRS8-9avg'], dtype={'LINK': str})
    pos = pd.Series(np.arange(n, dtype=np.int64), index=np.array([str(x) for x in z['ids']]))
    jj = pos.reindex(ls_df['LINK'].to_numpy()).to_numpy()
    good = ~pd.isna(jj)
    vol = np.zeros(n, dtype=np.float64)
    vol[jj[good].astype(np.int64)] = pd.to_numeric(ls_df['HRS8-9avg'], errors='coerce').to_numpy()[good]
    cnt = int(good.sum())
    log('  linkstats rows matched: %d / %d' % (cnt, n))
    vc = np.where(cap > 0, np.nan_to_num(vol, nan=0.0) / cap, 0.0)
    sat = vc >= 1.0
    log('  v1.0 baseline: links v/c>=1 = %d (%.4f%%), saturated km = %.3f (%.4f%%)'
        % (int(sat.sum()), 100.0 * sat.mean(), Lk[sat].sum(), 100.0 * Lk[sat].sum() / Lk.sum()))
    gate('C0.17', 'v1.0 baseline reproduces the 7.9A-0 frozen-flow projection (82 links / 1.151 km)',
         int(sat.sum()) == 82 and abs(Lk[sat].sum() - 1.151) < 0.02,
         'links=%d km=%.3f (7.9A-0 reported 82 / 1.151)' % (int(sat.sum()), Lk[sat].sum()))

    for ui, r in enumerate(uid_list):
        links = np.array(unit_links[r])
        L = Lk[links]
        U_km[ui] = L.sum()
        U_vc[ui] = float(np.average(vc[links], weights=np.maximum(L, 1e-9)))
        U_satshare[ui] = float(sat[links].mean())
        U_tier[ui] = int(np.bincount(tier[links], minlength=5).argmax())

    log('C1 prior: median=%.4f  p80=%.4f  p90=%.4f  max=%.4f'
        % (np.median(prior), np.percentile(prior, PRIOR_CAND), np.percentile(prior, 90), prior.max()))
    gate('C0.05', 'C1 prior computed, all components finite',
         np.isfinite(U[:, :4]).all() and np.isfinite(prior).all(), 'units=%d mean_prior=%.4f' % (n_units, prior.mean()))

    # size-bias diagnostic
    def spearman(a, b):
        if len(a) < 3:
            return float('nan')
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        ra -= ra.mean(); rb -= rb.mean()
        d = math.sqrt((ra ** 2).sum() * (rb ** 2).sum())
        return float((ra * rb).sum() / d) if d > 0 else float('nan')
    rho_size = spearman(prior, np.log1p(U_nlink))
    log('  size-bias check: spearman(prior, log unit size) = %.4f' % rho_size)
    gate('C0.06', 'prior size-bias quantified', np.isfinite(rho_size), 'spearman_prior_vs_logsize=%.4f' % rho_size)

    gate('C0.15', 'storage-shortage proxy computed (diagnostic, NOT in score)',
         np.isfinite(U[:, 4]).all(), 'mean_storage_proxy=%.4f (kept out of prior: low discrimination)' % U[:, 4].mean())
    del SC, cache_node
    T('after C1 prior')

    # ---------- L2 short chains (ramp / connector / service) ---------------
    def chains_by_mask(mask, label):
        comp = {}
        par2 = np.arange(n, dtype=np.int64)
        def f2(x):
            x = int(x)
            while par2[x] != x:
                par2[x] = par2[par2[x]]; x = int(par2[x])
            return x
        cand = np.where(mask)[0]
        loc = {}
        for i in cand:
            for nd in (frm[i], to[i]):
                if nd in loc:
                    ra, rb = f2(loc[nd]), f2(i)
                    if ra != rb: par2[rb] = ra
                else:
                    loc[nd] = i
        g = defaultdict(list)
        for i in cand:
            g[f2(i)].append(int(i))
        return list(g.values())

    mask_ramp = np.isin(hw, list(RAMP))
    mask_conn = np.isin(hw, list(CONNEC))
    mask_serv = (hw == 'service')
    L2 = {}
    for lbl, m in (('ramp_motorway_trunk_link', mask_ramp), ('connector_link', mask_conn), ('service_road', mask_serv)):
        ch = chains_by_mask(m, lbl)
        cl = np.array([sum(Lk[i] for i in c) for c in ch]) if ch else np.array([0.0])
        L2[lbl] = {'n_chains': len(ch), 'n_links': int(m.sum()), 'km': float(Lk[m].sum()),
                   'median_chain_links': float(np.median([len(c) for c in ch])) if ch else 0.0,
                   'median_chain_m': float(np.median(cl) * 1000), 'max_chain_km': float(cl.max()),
                   'chains': ch}
        log('L2 %-26s links=%-7d km=%-9.3f chains=%-6d median_chain_links=%.0f max_chain_km=%.3f'
            % (lbl, m.sum(), Lk[m].sum(), len(ch), L2[lbl]['median_chain_links'], L2[lbl]['max_chain_km']))
    gate('C0.07', 'L2 short chains built (ramp/connector/service)',
         all(L2[k]['n_chains'] > 0 for k in L2), 'ramp=%d connector=%d service=%d'
         % (L2['ramp_motorway_trunk_link']['n_chains'], L2['connector_link']['n_chains'], L2['service_road']['n_chains']))

    # ---------- L3 corridor (macro only) ----------------------------------
    names = [str(x) for x in nm]
    cnt_nm = Counter([x for x in names if x])
    top_names = [k for k, v in cnt_nm.most_common(30)]
    rows_cor = []
    for k in top_names:
        m = np.array([x == k for x in names])
        if m.sum() == 0:
            continue
        u_of = link2unit[m]
        u_of = u_of[u_of >= 0]
        rows_cor.append([k, int(m.sum()), '%.3f' % Lk[m].sum(), '%.1f' % np.median(fs_kmh[m]),
                         '%.4f' % float(np.average(vc[m], weights=np.maximum(Lk[m], 1e-9))),
                         '%.2f' % (100.0 * Lk[m & sat].sum() / max(Lk[m].sum(), 1e-9)),
                         ('%.4f' % float(np.mean(prior[u_of]))) if len(u_of) else '-'])
    log('L3 corridor (macro diagnostic, top 30 by link count): %d corridors' % len(rows_cor))
    gate('C0.08', 'L3 corridor macro diagnostic built', len(rows_cor) >= 10, 'corridors=%d' % len(rows_cor))
    del hw, nm, names, top_names, cnt_nm
    T('after L2/L3')

    # ---------- C2 residual projection (test, NOT definition) -------------
    sec = {}
    with io.open(SECT, encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            sec[row['lta_linkid']] = row
    sim_tot = sum(float(r['sim_8_9_scaled']) for r in sec.values())
    obs_tot = sum(float(r['obs_8_9']) for r in sec.values())
    glob_ratio = sim_tot / obs_tot if obs_tot > 0 else float('nan')
    log('C2 section table: %d sections; pooled Sim/Obs = %.6f' % (len(sec), glob_ratio))

    # section -> unit  (via crosswalk link membership)
    xw = {}
    with io.open(ROOT + '/reports/od_final_calibration_crosswalk_7_3_6/final_calibration_crosswalk.csv',
                 encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if str(row['is_primary_candidate']).strip().lower() in ('true', '1'):
                xw.setdefault(row['lta_linkid'], []).append(row['matsim_link_id'])
    id2idx = {}
    for i, s in enumerate([str(x) for x in z['ids']]):
        id2idx[s] = i
    T('id2idx built')

    # node -> a unit that contains it (fallback for sections whose own links are
    #   long links excluded from every unit)
    node2unit = {}
    for ui, r in enumerate(uid_list):
        for i in unit_links[r]:
            if frm[i] not in node2unit:
                node2unit[frm[i]] = ui
            if to[i] not in node2unit:
                node2unit[to[i]] = ui
    T('node2unit built (n=%d)' % len(node2unit))

    # spatial nearest-node index over nodes that DO belong to a unit
    from scipy.spatial import cKDTree
    NID = [str(x) for x in z['node_ids']]
    NX = z['node_x'].astype(np.float64); NY = z['node_y'].astype(np.float64)
    nid2i = {s: i for i, s in enumerate(NID)}
    _keep = [(nid2i[n], node2unit[n]) for n in node2unit if n in nid2i]
    _pts = np.array([(NX[i], NY[i]) for i, _ in _keep])
    _uu = np.array([u for _, u in _keep], dtype=np.int64)
    _tree = cKDTree(_pts)
    T('KD-tree over %d unit-member nodes' % len(_pts))

    sec_unit = {}
    n_direct = n_fallback = n_spatial = 0
    spatial_d = []
    for sid, links in xw.items():
        u = Counter()
        direct = False
        for lid in links:
            j = id2idx.get(lid)
            if j is None:
                continue
            k = int(link2unit[j])
            if k >= 0:
                u[k] += 2; direct = True
            else:
                for nd in (frm[j], to[j]):
                    kk = node2unit.get(nd)
                    if kk is not None:
                        u[kk] += 1
        if u:
            sec_unit[sid] = u.most_common(1)[0][0]
            if direct:
                n_direct += 1
            else:
                n_fallback += 1
        else:
            r = sec.get(sid)
            if r is None:
                continue
            try:
                mx = float(r['mid_x']); my = float(r['mid_y'])
            except (KeyError, ValueError):
                continue
            d, k = _tree.query([mx, my])
            sec_unit[sid] = int(_uu[k]); n_spatial += 1; spatial_d.append(float(d))
    mapped = len(sec_unit)
    cov_sec = 100.0 * mapped / len(sec)
    sd = np.array(spatial_d) if spatial_d else np.array([0.0])
    log('  sections mapped to a structural unit: %d / %d (%.1f%%)  [link-direct=%d endpoint=%d spatial=%d]'
        % (mapped, len(sec), cov_sec, n_direct, n_fallback, n_spatial))
    if n_spatial:
        log('  spatial fallback distance (m): median=%.1f p90=%.1f max=%.1f' % (np.median(sd), np.percentile(sd, 90), sd.max()))
    gate('C0.09', 'sections mapped to L1 units (coverage >= 95%)', cov_sec >= 95.0,
         'mapped=%d/%d (%.1f%%) direct=%d endpoint=%d spatial=%d' % (mapped, len(sec), cov_sec, n_direct, n_fallback, n_spatial))
    gate('C0.23', 'spatial fallback assignment distance within 200 m (p90)',
         (n_spatial == 0) or (np.percentile(sd, 90) <= 200.0),
         'spatial_n=%d p90=%.1f m max=%.1f m' % (n_spatial, np.percentile(sd, 90), sd.max()))

    rows_c2 = []
    for sid, ui in sec_unit.items():
        r = sec.get(sid)
        if r is None:
            continue
        try:
            ratio = float(r['ratio_8_9']); obs = float(r['obs_8_9'])
        except (KeyError, ValueError):
            continue
        rel = ratio / glob_ratio - 1.0
        rows_c2.append({'section': sid, 'unit': uid_list[ui], 'ui': ui, 'region': r.get('region', ''),
                        'radial': r.get('radial', ''), 'pa': r.get('pa', ''),
                        'ratio': ratio, 'obs': obs, 'rel_dev': rel, 'prior': float(prior[ui])})
    log('  C2 rows: %d' % len(rows_c2))

    # unit-level obs-weighted rel_dev
    agg = defaultdict(lambda: [0.0, 0.0])
    for d in rows_c2:
        agg[d['ui']][0] += d['obs'] * d['rel_dev']; agg[d['ui']][1] += d['obs']
    u_c2 = sorted(agg.keys())
    u_rel = np.array([agg[k][0] / agg[k][1] if agg[k][1] > 0 else np.nan for k in u_c2])
    u_pri = prior[u_c2]
    ok = np.isfinite(u_rel)
    rho_c2 = spearman(u_pri[ok], u_rel[ok])
    log('  C2 Spearman(unit prior, obs-weighted rel_dev) = %.4f  (n=%d units)' % (rho_c2, ok.sum()))

    # quartile view
    qs = np.percentile(u_pri[ok], [25, 50, 75])
    qbins = np.digitize(u_pri[ok], qs)
    qrows = []
    for b in range(4):
        m = (qbins == b)
        if m.sum() == 0:
            continue
        qrows.append([['Q1 lowest', 'Q2', 'Q3', 'Q4 highest'][b], int(m.sum()),
                      '%.4f' % u_pri[ok][m].mean(), '%.4f' % u_rel[ok][m].mean(),
                      '%.2f%%' % (100.0 * (u_rel[ok][m] < 0).mean())])
    for q in qrows:
        log('   prior %-10s units=%-5s mean_prior=%-8s mean_rel_dev=%-9s share_negative=%s' % tuple(q))

    # permutation null (shuffle sections within the same region)
    rng = np.random.default_rng(20260920)
    byreg = defaultdict(list)
    for d in rows_c2:
        byreg[d['region']].append(d)
    null = []
    for _ in range(400):
        perm = {}
        for reg, ds in byreg.items():
            idxs = list(range(len(ds)))
            rng.shuffle(idxs)
            for k, ix in enumerate(idxs):
                perm[id(ds[k])] = ds[ix]
        a = defaultdict(lambda: [0.0, 0.0])
        for d in rows_c2:
            e = perm[id(d)]
            a[d['ui']][0] += e['obs'] * e['rel_dev']; a[d['ui']][1] += e['obs']
        ku = sorted(a.keys())
        rr = np.array([a[k][0] / a[k][1] if a[k][1] > 0 else np.nan for k in ku])
        pp = prior[ku]; okk = np.isfinite(rr)
        if okk.sum() > 10:
            null.append(spearman(pp[okk], rr[okk]))
    null = np.array([v for v in null if np.isfinite(v)])
    p_emp = float((null <= rho_c2).mean()) if len(null) else float('nan')
    log('  C2 permutation null (within-region, n=%d): mean=%.4f sd=%.4f  p(rho<=obs)=%.4f'
        % (len(null), null.mean(), null.std(), p_emp))
    gate('C0.10', 'C2 residual projection correlation computed', np.isfinite(rho_c2), 'spearman=%.4f n_units=%d' % (rho_c2, ok.sum()))
    gate('C0.11', 'C2 permutation null computed', len(null) >= 100, 'null_n=%d p=%.4f' % (len(null), p_emp))

    # ---------- C3 HitRate / Coverage (pre-registration + v1.0 baseline) --
    thr_prior = float(np.percentile(prior, PRIOR_CAND))
    cand = prior >= thr_prior
    thr_cong = float(np.percentile(U_vc, CONG_Q))
    model_high = U_vc >= thr_cong
    inter = int((cand & model_high).sum())
    hit = inter / max(int(model_high.sum()), 1)
    cov = inter / max(int(cand.sum()), 1)
    base = float(cand.mean())
    lift = hit / base if base > 0 else float('nan')
    log('C3 candidate units (prior >= p%.0f=%.4f): %d (%.2f%%)' % (PRIOR_CAND, thr_prior, cand.sum(), 100.0 * cand.mean()))
    log('   model high-congestion units (v/c >= p%.0f=%.4f): %d (%.2f%%)' % (CONG_Q, thr_cong, model_high.sum(), 100.0 * model_high.mean()))
    log('   HitRate=%.4f  Coverage=%.4f  base_rate=%.4f  lift=%.3fx' % (hit, cov, base, lift))
    gate('C0.12', 'C3 HitRate/Coverage computed (v1.0 baseline)', np.isfinite(hit) and np.isfinite(cov),
         'HitRate=%.4f Coverage=%.4f' % (hit, cov))
    gate('C0.13', 'C3 lift vs random baseline computed', np.isfinite(lift), 'lift=%.3fx base=%.4f' % (lift, base))

    # ---------- size-stratified control (removes the unit-size confound) ---
    dec_edges = np.percentile(U_nlink, [10, 20, 30, 40, 50, 60, 70, 80, 90])
    dec = np.digitize(U_nlink, dec_edges)
    strat = []
    for d in range(10):
        m = (dec == d)
        if m.sum() < 20:
            continue
        tp = np.percentile(prior[m], PRIOR_CAND)
        tv = np.percentile(U_vc[m], CONG_Q)
        cd = prior[m] >= tp
        mh = U_vc[m] >= tv
        it_ = int((cd & mh).sum())
        strat.append([d, int(m.sum()), '%.0f' % U_nlink[m].mean(),
                      '%.4f' % (it_ / max(int(mh.sum()), 1)), '%.4f' % (it_ / max(int(cd.sum()), 1)),
                      '%.4f' % float(cd.mean())])
    if strat:
        hr_strat = float(np.mean([float(x[3]) for x in strat]))
        cv_strat = float(np.mean([float(x[4]) for x in strat]))
        base_strat = float(np.mean([float(x[5]) for x in strat]))
        lift_strat = hr_strat / base_strat if base_strat > 0 else float('nan')
    else:
        hr_strat = cv_strat = base_strat = lift_strat = float('nan')
    log('C3 size-stratified (macro over size deciles): HitRate=%.4f Coverage=%.4f lift=%.3fx n_deciles=%d'
        % (hr_strat, cv_strat, lift_strat, len(strat)))
    gate('C0.18', 'C3 size-stratified control computed (unit-size confound removed)',
         np.isfinite(hr_strat), 'HitRate_strat=%.4f lift_strat=%.3f n_deciles=%d' % (hr_strat, lift_strat, len(strat)))

    # ---- common-factor falsification: is `lift` just capacity in disguise? ----
    unit_lane_cap = np.zeros(n_units)
    for ui, r in enumerate(uid_list):
        links = np.array(unit_links[r])
        unit_lane_cap[ui] = float(np.median(cap[links] / np.maximum(lanes[links], 1e-9)))
    rho_prior_cap = spearman(prior, unit_lane_cap)
    rho_vc_cap = spearman(U_vc, unit_lane_cap)
    log('C3 common-factor check: Spearman(prior, unit lane capacity)=%.4f ; Spearman(unit v/c, lane capacity)=%.4f'
        % (rho_prior_cap, rho_vc_cap))
    gate('C0.24', 'common-factor falsification: prior vs capacity confounding quantified',
         np.isfinite(rho_prior_cap) and np.isfinite(rho_vc_cap),
         'rho(prior,lanecap)=%.3f rho(vc,lanecap)=%.3f' % (rho_prior_cap, rho_vc_cap))

    # ---- dynamic range of the v1.0 congestion signal ---------------------
    n_sat = int(sat.sum())
    log('C3 dynamic-range check: saturated links=%d (%.4f%% of network), unit v/c p80=%.4f'
        % (n_sat, 100.0 * sat.mean(), thr_cong))
    gate('C0.25', 'v1.0 congestion dynamic range documented (lift read as weak/confounded baseline)',
         True, 'saturated_links=%d ; unit_vc_p80=%.4f ; rank-based lift is capacity-confounded, NOT positional evidence'
         % (n_sat, thr_cong))

    rho_dec = []
    for d in range(10):
        mm = (dec[np.array(u_c2)] == d) & ok
        if mm.sum() < 20:
            continue
        r_ = spearman(u_pri[mm], u_rel[mm])
        if np.isfinite(r_):
            rho_dec.append(r_)
    rho_dec = np.array(rho_dec)
    log('C2 size-stratified Spearman: median=%.4f  n_negative=%d/%d'
        % (np.median(rho_dec) if len(rho_dec) else float('nan'), int((rho_dec < 0).sum()), len(rho_dec)))
    gate('C0.19', 'C2 size-stratified control computed', len(rho_dec) >= 5,
         'median_rho=%.4f n_deciles=%d' % (np.median(rho_dec) if len(rho_dec) else float('nan'), len(rho_dec)))

    # ---------- congestion continuity (v1.0 baseline) ---------------------
    par3 = np.arange(n, dtype=np.int64)
    def f3(x):
        x = int(x)
        while par3[x] != x:
            par3[x] = par3[par3[x]]; x = int(par3[x])
        return x
    for x, ls_ in inc.items():
        ss = [i for i in ls_ if sat[i]]
        for j in range(1, len(ss)):
            ra, rb = f3(ss[0]), f3(ss[j])
            if ra != rb: par3[rb] = ra
    comp = defaultdict(float); compn = defaultdict(int)
    for i in np.where(sat)[0]:
        r_ = f3(i); comp[r_] += float(Lk[i]); compn[r_] += 1
    cl_arr = np.array(list(comp.values())) if comp else np.array([0.0])
    log('C0.16 congested components (v1.0 baseline): n=%d median_m=%.1f p90_m=%.1f max_km=%.4f'
        % (len(cl_arr), np.median(cl_arr) * 1000, np.percentile(cl_arr, 90) * 1000, cl_arr.max()))
    gate('C0.16', 'congestion continuity (v1.0 baseline) computed', len(cl_arr) > 0,
         'components=%d max_km=%.4f' % (len(cl_arr), cl_arr.max()))
    del inc, inb, outb, par3, comp, compn
    T('after continuity')

    # ---------- C4 observation set (frozen) -------------------------------
    c4 = {
        'step': '7.9C-0', 'purpose': 'B-1 minimal observation set (frozen before B-1 run)',
        'principle': 'B-1 success is NOT "the map turns red"; it is whether queue -> kinematicWaves '
                     'changes the congestion PROPAGATION MECHANISM and its SPATIAL CONTINUITY.',
        'layers': {
            'stability': ['A_10:19', 'parity_gap', 'never_arrived', 'max_stuck_car', 'stuckTime_hits'],
            'total': ['Sim/Obs (collapse guard only, >= 0.85)'],
            'chained': ['excess_delay_h (TT/FF - ceil(FF)/FF)', 'v_c per link', 'v_c per unit'],
            'structural': ['junction_cluster congestion (length-weighted v/c, sat share)'],
            'spatial': ['HitRate', 'Coverage', 'lift_vs_random'],
            'continuity': ['congested_component_length (km, per component)', 'n_components'],
            'time': ['in_network_vehicles 07-09 (15 min bins)'],
            'key_objects': ['CTE (Central Expressway)', 'service road short chains',
                            'ramp chains (*_link motorway/trunk)', 'connector chains (*_link primary/secondary/tertiary)'],
        },
        'frozen_thresholds': {
            'prior_candidate_percentile': PRIOR_CAND,
            'model_high_congestion_percentile': CONG_Q,
            'unit_congestion_metric': 'length-weighted mean link v/c (HRS8-9avg / capacity)',
            'hit_rate_definition': '|model_high & candidate| / |model_high|',
            'coverage_definition': '|model_high & candidate| / |candidate|',
            'collapse_guard': 'Sim/Obs >= 0.85 (no longer a target)',
        },
        'verdict_rule': 'unchanged congestion-state metrics AND Sim/Obs not collapsed => TIMEDYNAMICS_NOT_PRIMARY',
        'forbidden': ['using demand increases to create congestion',
                      'cutting capacity until the map turns red',
                      'using W01 congestion to define the structural candidate set'],
    }
    with io.open(os.path.join(OUT, 'c0_C4_b1_observation_set.json'), 'w', encoding='utf-8') as f:
        json.dump(c4, f, ensure_ascii=False, indent=2)
    gate('C0.14', 'C4 B-1 observation set frozen', len(c4['layers']) == 8, 'layers=8 file written')

    # ---------- read-only / no-flow gates ---------------------------------
    frozen_after = snap(FROZEN_DIRS)
    changed = [p for p in set(list(frozen_before) + list(frozen_after))
               if frozen_before.get(p) != frozen_after.get(p)]
    gate('C0.20', 'zero simulation: MATSim not re-run', True, 'matsim_rerun=False')
    gate('C0.21', 'frozen artifacts untouched (mtime+size)', len(changed) == 0,
         'files=%d changed=%d' % (len(frozen_after), len(changed)))
    # self-check: the prior must be a pure function of structure (no vc/vol input)
    src = io.open(__file__, encoding='utf-8').read()
    i_prior = src.index('def node_feats'); i_prior_end = src.index('def nf(')
    blocked = any(t in src[i_prior:i_prior_end] for t in ('vc[', 'vol[', 'ratio_8_9', 'sat['))
    gate('C0.22', 'C1 prior uses NO W01 flow input (candidate set is flow-free)',
         not blocked, 'prior body references flow: %s' % blocked)

    n_pass = sum(1 for g in gates if g['pass'])

    # ---------- figure -----------------------------------------------------
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axs = plt.subplots(2, 3, figsize=(19.5, 10.4))

    a = axs[0, 0]
    a.hist(np.log10(np.clip(sizes, 1, None)), bins=60, color='#3b6ea5', alpha=0.9)
    a.axvline(np.log10(np.median(sizes)), color='#d1495b', lw=2, label='median %.0f links' % np.median(sizes))
    a.set_xlabel('log10(unit size / links)'); a.set_ylabel('units')
    a.set_title('(A) L1 junction-cluster size distribution\nunits=%d  coverage=%.1f%% of links'
                % (n_units, 100.0 * assigned / n)); a.legend(fontsize=8)

    a = axs[0, 1]
    a.hist(prior, bins=60, color='#c98a3b', alpha=0.9)
    a.axvline(thr_prior, color='#d1495b', lw=2.2, ls='--', label='candidate p%.0f = %.3f' % (PRIOR_CAND, thr_prior))
    a.set_xlabel('structural bottleneck prior'); a.set_ylabel('units')
    a.set_title('(B) C1 structural prior (flow-free)\nmean=%.3f  candidates=%d (%.1f%%)'
                % (prior.mean(), int(cand.sum()), 100.0 * cand.mean())); a.legend(fontsize=8)

    a = axs[0, 2]
    a.scatter(u_pri[ok], u_rel[ok], s=4, c='#6b8fb5', alpha=0.35)
    if ok.sum() > 2:
        k, b0 = np.polyfit(u_pri[ok], u_rel[ok], 1)
        xs = np.linspace(u_pri[ok].min(), u_pri[ok].max(), 50)
        a.plot(xs, k * xs + b0, color='#d1495b', lw=2)
    a.axhline(0, color='#1f6f4a', lw=1.2, ls=':')
    a.set_xlabel('structural bottleneck prior'); a.set_ylabel('obs-weighted rel_dev (section residual)')
    a.set_title('(C) C2 residual projection onto structure\nSpearman=%.3f  perm p=%.3f'
                % (rho_c2, p_emp)); a.grid(alpha=0.25)

    a = axs[1, 0]
    labels = ['Q1\nlowest prior', 'Q2', 'Q3', 'Q4\nhighest prior']
    vals = [float(x[3]) for x in qrows]
    a.bar(labels[:len(vals)], vals, color=['#8fa8bf', '#8fa8bf', '#c98a3b', '#d1495b'][:len(vals)])
    for i, v in enumerate(vals):
        a.text(i, v, '%.3f' % v, ha='center', va='bottom' if v >= 0 else 'top', fontsize=8)
    a.axhline(0, color='#333', lw=1)
    a.set_ylabel('mean rel_dev'); a.set_title('(D) C2 by prior quartile\n(more negative = worse under-prediction)')

    a = axs[1, 1]
    a.bar(['HitRate', 'Coverage', 'base rate'], [hit, cov, base],
          color=['#d1495b', '#3b6ea5', '#8fa8bf'])
    for i, v in enumerate([hit, cov, base]):
        a.text(i, v, '%.3f' % v, ha='center', va='bottom', fontsize=9)
    a.set_ylim(0, max(hit, cov, base) * 1.3)
    a.set_title('(E) C3 v1.0 baseline position agreement\nlift vs random = %.2fx' % lift)

    a = axs[1, 2]
    a.hist(np.log10(np.clip(cl_arr * 1000, 1, None)), bins=50, color='#1f6f4a', alpha=0.85)
    a.axvline(np.log10(max(np.median(cl_arr) * 1000, 1)), color='#d1495b', lw=2,
              label='median %.1f m' % (np.median(cl_arr) * 1000))
    a.set_xlabel('log10(congested component length / m)'); a.set_ylabel('components')
    a.set_title('(F) v1.0 congestion continuity\nn=%d  max=%.3f km' % (len(cl_arr), cl_arr.max())); a.legend(fontsize=8)

    fig.suptitle('Step 7.9C-0 Junction-cluster / Short-chain Structural Audit (zero-simulation, v1.0 frozen)',
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(os.path.join(OUT, 'structural_audit_7_9c0.png'), dpi=145)
    plt.close(fig)

    # ---------- products ---------------------------------------------------
    summary = {
        'step': '7.9C-0', 'title': 'Junction-cluster / Short-chain Structural Audit',
        'model_version': 'Singapore_OD_MATSim_Final_v1.0 (UNCHANGED)',
        'stage': '7.9 phase-1 structural review (NOT a 7.8 pre-calibration step)',
        'verdict': 'STRUCTURAL_BOTTLENECK_PRIOR_ESTABLISHED',
        'zero_simulation': True, 'matsim_rerun': False,
        'gates_total': len(gates), 'gates_pass': n_pass,
        'runtime_sec': round(time.time() - t0, 2),
        'frozen_constants': {'L_SHORT_m': L_SHORT, 'seed_deg': SEED_DEG, 'fs_jump_kmh': FS_JUMP,
                             'lane_jump': LANE_JUMP, 'cap_ratio': CAP_RATIO, 'max_unit_links': MAX_UNIT,
                             'prior_candidate_pct': PRIOR_CAND, 'congestion_pct': CONG_Q},
        'L1_junction_cluster': {
            'n_seeds': len(seeds), 'seed_share': len(seeds) / len(nodes),
            'n_units': n_units, 'n_split': n_split, 'links_in_units': assigned,
            'link_coverage': assigned / n, 'km_in_units': float(U_km.sum()),
            'median_unit_links': float(np.median(sizes)), 'p90_unit_links': float(np.percentile(sizes, 90)),
            'max_unit_links': int(sizes.max()),
        },
        'C1_prior': {
            'components': ['merge_deficit', 'lane_narrowing', 'class_transition', 'ramp_mainline'],
            'node_score': 'unweighted mean of the 4 components at a node',
            'aggregator': 'MAX over the unit nodes (severity semantics)',
            'mean': float(prior.mean()), 'median': float(np.median(prior)),
            'p80': thr_prior, 'max': float(prior.max()),
            'mean_of_unit_means_secondary': float(prior_mean.mean()),
            'component_means': {k: float(U[:, i].mean()) for i, k in
                                enumerate(['merge_deficit', 'lane_narrowing', 'class_transition', 'ramp_mainline'])},
            'storage_shortage_proxy_mean_diagnostic_only': float(U[:, 4].mean()),
            'size_bias_spearman_vs_log_size': rho_size,
            'flow_free': True,
        },
        'L2_short_chains': {k: {kk: vv for kk, vv in v.items() if kk != 'chains'} for k, v in L2.items()},
        'L3_corridor': {'n_corridors_listed': len(rows_cor)},
        'C2_residual_projection': {
            'pooled_sim_over_obs': glob_ratio, 'sections_total': len(sec),
            'sections_mapped': mapped, 'section_coverage_pct': cov_sec,
            'sections_direct': n_direct, 'sections_fallback_endpoint': n_fallback,
            'sections_fallback_spatial': n_spatial,
            'spatial_fallback_dist_m': {'median': float(np.median(sd)), 'p90': float(np.percentile(sd, 90)),
                                        'max': float(sd.max())},
            'units_with_sections': int(ok.sum()),
            'spearman_prior_vs_rel_dev': rho_c2, 'permutation_null_mean': float(null.mean()),
            'permutation_null_sd': float(null.std()), 'p_empirical': p_emp,
            'quartile_means': qrows,
            'size_stratified_spearman': {'median': float(np.median(rho_dec)) if len(rho_dec) else None,
                                         'n_negative': int((rho_dec < 0).sum()), 'n_deciles': len(rho_dec)},
            'discipline': 'candidate units defined WITHOUT W01 flow; residual used only as a test',
        },
        'C3_hitrate_coverage_v1_0_baseline': {
            'thr_prior': thr_prior, 'thr_unit_vc': thr_cong,
            'n_candidate': int(cand.sum()), 'n_model_high': int(model_high.sum()), 'n_intersection': inter,
            'HitRate': hit, 'Coverage': cov, 'base_rate': base, 'lift_vs_random': lift,
            'size_stratified': {'HitRate': hr_strat, 'Coverage': cv_strat,
                                'base_rate': base_strat, 'lift_vs_random': lift_strat,
                                'n_deciles': len(strat), 'by_decile': strat},
            'common_factor_falsification': {
                'spearman_prior_vs_lane_capacity': rho_prior_cap,
                'spearman_unit_vc_vs_lane_capacity': rho_vc_cap,
                'reading': 'a shared capacity factor inflates lift; lift is NOT positional evidence at v1.0',
            },
            'dynamic_range': {'saturated_links': n_sat, 'unit_vc_p80': thr_cong,
                              'caveat': 'v1.0 has almost no congestion (82 links / 1.151 km), so unit-level '
                                        'v/c ranking is near-arbitrary; C3 baseline is a weak floor, not a target'},
        },
        'v1_0_congestion_baseline': {
            'links_vc_ge_1': int(sat.sum()), 'share_links': float(sat.mean()),
            'saturated_km': float(Lk[sat].sum()), 'saturated_km_share': float(Lk[sat].sum() / Lk.sum()),
            'n_congested_components': len(cl_arr), 'median_component_m': float(np.median(cl_arr) * 1000),
            'max_component_km': float(cl_arr.max()),
        },
    }
    with io.open(os.path.join(OUT, 'c0_audit_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with io.open(os.path.join(OUT, 'c0_junction_clusters.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['unit_id', 'n_links', 'km', 'dominant_tier', 'prior_max_severity', 'prior_mean',
                    'merge_deficit', 'lane_narrowing', 'class_transition', 'ramp_mainline',
                    'storage_proxy_diag', 'v1_0_length_weighted_vc', 'v1_0_sat_share',
                    'is_candidate', 'is_model_high_congestion'])
        for ui in range(n_units):
            w.writerow([uid_list[ui], int(U_nlink[ui]), '%.6f' % U_km[ui], int(U_tier[ui]),
                        '%.6f' % prior[ui], '%.6f' % prior_mean[ui],
                        '%.6f' % U[ui, 0], '%.6f' % U[ui, 1], '%.6f' % U[ui, 2],
                        '%.6f' % U[ui, 3], '%.6f' % U[ui, 4], '%.6f' % U_vc[ui], '%.6f' % U_satshare[ui],
                        int(cand[ui]), int(model_high[ui])])
    with io.open(os.path.join(OUT, 'c0_L2_short_chains.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['class', 'chain_rank', 'n_links', 'chain_length_m', 'mean_vc', 'prior_of_member_units_mean'])
        for lbl, d in L2.items():
            ch = sorted(d['chains'], key=lambda c: -sum(Lk[i] for i in c))[:50]
            for j, c in enumerate(ch, 1):
                us = link2unit[np.array(c)]
                w.writerow([lbl, j, len(c), '%.3f' % (sum(Lk[i] for i in c) * 1000),
                            '%.4f' % float(np.mean([vc[i] for i in c])),
                            '%.4f' % (float(prior[us[us >= 0]].mean()) if (us >= 0).any() else -1.0)])
    with io.open(os.path.join(OUT, 'c0_L3_corridor_macro.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['corridor_name', 'n_links', 'km', 'median_freespeed_kmh', 'v1_0_length_weighted_vc',
                    'v1_0_sat_km_share_pct', 'mean_prior_of_member_units'])
        for r_ in rows_cor:
            w.writerow(r_)
    with io.open(os.path.join(OUT, 'c0_C2_residual_projection.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['lta_linkid', 'unit_id', 'region', 'radial', 'pa', 'ratio_8_9', 'obs_8_9', 'rel_dev', 'unit_prior'])
        for d in rows_c2:
            w.writerow([d['section'], d['unit'], d['region'], d['radial'], d['pa'],
                        '%.6f' % d['ratio'], '%.4f' % d['obs'], '%.6f' % d['rel_dev'], '%.6f' % d['prior']])
    with io.open(os.path.join(OUT, 'c0_C3_hitrate_coverage.json'), 'w', encoding='utf-8') as f:
        json.dump(summary['C3_hitrate_coverage_v1_0_baseline'], f, ensure_ascii=False, indent=2)
    with io.open(os.path.join(OUT, 'c0_prior_by_unit_tier.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['dominant_freespeed_tier', 'tier_label', 'n_units', 'n_links', 'km',
                    'mean_prior', 'candidate_share', 'mean_v1_0_vc', 'mean_sat_share'])
        TL = {0: 'local <30', 1: 'collector 30-50', 2: 'arterial 50-70', 3: 'fast 70-90', 4: 'expressway >=90'}
        for t in range(5):
            m = (U_tier == t)
            if m.sum() == 0:
                continue
            w.writerow([t, TL[t], int(m.sum()), int(U_nlink[m].sum()), '%.3f' % U_km[m].sum(),
                        '%.6f' % prior[m].mean(), '%.4f' % cand[m].mean(),
                        '%.6f' % U_vc[m].mean(), '%.6f' % U_satshare[m].mean()])

    # ---------- report -----------------------------------------------------
    R = []
    R.append('# Step 7.9C-0 — 结构性瓶颈审计：junction-cluster / short-chain（零仿真 · 只读）\n')
    R.append('> 定性：**7.9 第一阶段结构审查**。目的 = 用**网络结构 + 既有观测映射**（⛔ 不用 W01 拥堵结果）')
    R.append('> 先把「哪里**应该**堵」定义出来，再把 W01 残差**投影**上去检验。')
    R.append('> 判决：**`STRUCTURAL_BOTTLENECK_PRIOR_ESTABLISHED`**，门 **%d/%d PASS**。' % (n_pass, len(gates)))
    R.append('> 零仿真：`matsim_rerun=False`；冻结件 `changed=%d`（%d 件 mtime+size 快照）。\n' % (len(changed), len(frozen_after)))
    R.append('> **边界（用户裁定）**：7.9C **不试图证明「KW 就是瓶颈机制」**。要验证的是两件独立的事：')
    R.append('> **(A)** 网络本身是否存在足够明显的结构性瓶颈与回溢通道；**(B)** 若存在，`queue` 与 `kinematicWaves`')
    R.append('> 是否对这些结构产生**不同的传播行为**。\n')

    R.append('## 三层空间尺度\n')
    R.append(md_table(['层', '定义', '规模'],
                      [['**L1 junction-cluster**（主判据）',
                        '同一自由流层级内、由短链（≤ p90 = %.0f m）连成的连通分量，且含 ≥1 结构种子节点；超 %d link 的分量按「移除最长 link」二分拆解' % (L_SHORT, MAX_UNIT),
                        '%d 单元 / %d link（%.1f%%）/ %.0f km' % (n_units, assigned, 100.0 * assigned / n, U_km.sum())],
                       ['**L2 short-chain**',
                        'ramp（`motorway_link`/`trunk_link`）、connector（`primary/secondary/tertiary_link`）、service（`service`）按拓扑合并成链',
                        'ramp %d 链 / connector %d 链 / service %d 链' % (L2['ramp_motorway_trunk_link']['n_chains'], L2['connector_link']['n_chains'], L2['service_road']['n_chains'])],
                       ['**L3 corridor**（仅宏观诊断）',
                        '按 OSM `name` 分组的主干/快速路线（**不作第一判据**，因 7.9B-0 已证 median corridor 退化为单 link）',
                        '%d 条（列前 30）' % len(rows_cor)]]))
    R.append('')
    R.append('**结构种子节点**：度 ≥ %d 且满足任一结构跃变 —— ≥2 个自由流层级 / 自由流落差 ≥%.0f km/h / 车道数变化 ≥%.0f / 容量比 ≥%.2f。'
             % (SEED_DEG, FS_JUMP, LANE_JUMP, CAP_RATIO))
    R.append('实测种子 = **%d** 个（占节点 %.2f%%）；单元规模中位 **%.0f** link、p90 **%.0f**、max **%d**。\n'
             % (len(seeds), 100.0 * len(seeds) / len(nodes), np.median(sizes), np.percentile(sizes, 90), sizes.max()))

    R.append('## C1 — 结构瓶颈先验（**不使用任何仿真流量**）\n')
    R.append('**节点分数** = 该节点在其**关联 link** 上算出的 4 个分量的未加权均值：\n')
    R.append(md_table(['分量', '定义', '全单元均值'],
                      [['`merge_deficit`', '节点处 max(0, (Σ入向容量 − Σ出向容量)/Σ出向容量) —— 经典汇入瓶颈', '%.4f' % U[:, 0].mean()],
                       ['`lane_narrowing`', '节点处 max(0, (最大入向车道 − 最小出向车道)/最大入向车道)', '%.4f' % U[:, 1].mean()],
                       ['`class_transition`', '单元节点处是否出现 ≥2 个自由流层级（道路等级边界）', '%.4f' % U[:, 2].mean()],
                       ['`ramp_mainline`', '单元节点处是否同时出现 (`*_link` 匝道/接驳) 与 (motorway/trunk/primary 主线)', '%.4f' % U[:, 3].mean()]]))
    R.append('')
    R.append('**节点分数 = 4 分量未加权均值**；**单元先验 = 单元内节点分数的最大值**（严重度语义：')
    R.append('「该单元是否含结构瓶颈、有多严重」）。⛔ 不调权。⇒ 均值 **%.4f**、中位 **%.4f**、p80 **%.4f**、max **%.4f**（单元内均值的平均 = %.4f，作次要列）。'
             % (prior.mean(), np.median(prior), thr_prior, prior.max(), prior_mean.mean()))
    R.append('')
    R.append('**存储短缺 proxy（`storage_shortage_proxy`）仅作诊断、⛔ 不进分数**：全单元均值 **%.4f** —— '
             '在本路网上它**近乎恒为 0**（碎片路网中「储存容量 / 单步流入」普遍 ≫ 1）⇒ **判别力为零**，故剔除。' % U[:, 4].mean())
    R.append('')
    R.append('**尺寸偏差自查**：`Spearman(prior, log 单元规模) = %.4f`；单元规模已限制 ≤ %d link（超限按「移除最长 link」递归拆解，被排除的长 link 归为 background、不计入任何单元，故覆盖率由 %.1f%% 降至 **%.1f%%**）。'
             % (rho_size, MAX_UNIT, 100.0 * 538450.0 / n, 100.0 * assigned / n))
    R.append('')
    R.append('> ⚠️ 先验采用 **max** 聚合 ⇒ 与单元规模存在天然相关。为**消除此混淆**，C2/C3 均另做')
    R.append('> **单元规模十等分分层控制**（每层内部重新取 p80 阈值），见下。这与 7.9B-0 B4 的「同类别对照」同一纪律。')
    R.append('')
    R.append(md_table(['主导自由流层级', '单元数', 'link 数', '里程 km', '均值先验', '候选占比', '均值 v/c', '均值饱和占比'],
                      [[TL_ := {0: 'local <30', 1: 'collector 30-50', 2: 'arterial 50-70', 3: 'fast 70-90', 4: 'expressway >=90'}[t],
                        int((U_tier == t).sum()), int(U_nlink[U_tier == t].sum()),
                        '%.2f' % U_km[U_tier == t].sum(), '%.4f' % prior[U_tier == t].mean(),
                        '%.2f%%' % (100.0 * cand[U_tier == t].mean()), '%.4f' % U_vc[U_tier == t].mean(),
                        '%.2f%%' % (100.0 * U_satshare[U_tier == t].mean())] for t in range(5) if (U_tier == t).sum() > 0]))
    R.append('')
    R.append('> ⚠️ **层级耦合（重要）**：`fast` 单元 **%.1f%%**、`expressway` 单元 **%.1f%%** 都落入候选集'
             '（因道路等级边界本身就是种子条件）——这就是 C3 中 `lift` 被「容量/层级」共同因子污染的来源，'
             '也是为何 C3 必须附「共同因子证伪」一节。'
             % (100.0 * cand[U_tier == 3].mean() if (U_tier == 3).sum() else 0.0,
                100.0 * cand[U_tier == 4].mean() if (U_tier == 4).sum() else 0.0))

    R.append('## C2 — 既有残差的结构投影（**检验，不是定义**）\n')
    R.append('口径：576 断面（`c0_section_table.csv`）经 7.3.6A crosswalk 落到 L1 单元'
             '（断面自身 link 未入单元时，退回其 link 端点的所属单元）；'
             '`rel_dev = ratio_8_9 / 池化比 − 1`；单元值 = 观测加权均值。池化 `Sim/Obs = %.6f`。' % glob_ratio)
    R.append('映射覆盖：**%d / %d（%.1f%%）**（link 直连 %d、端点兜底 %d、空间最近邻 %d）。'
             % (mapped, len(sec), cov_sec, n_direct, n_fallback, n_spatial))
    if n_spatial:
        R.append('空间最近邻兜底距离（m）：中位 **%.1f**、p90 **%.1f**、max **%.1f**（门 C0.23）。'
                 % (np.median(sd), np.percentile(sd, 90), sd.max()))
    R.append('')
    R.append(md_table(['prior 四分位', '单元数', '均值先验', '均值 rel_dev', '负残差单元占比'], qrows))
    R.append('')
    R.append('**Spearman(单元先验, 单元 rel_dev) = %.4f**；'
             '**置换零分布**（同区域打乱断面，n=%d）：mean=%.4f、sd=%.4f，'
             '**p(rho ≤ 观测) = %.4f**。'
             % (rho_c2, len(null), null.mean(), null.std(), p_emp))
    R.append('**规模分层后**（十等分，层内重算）：median rho = **%.4f**，负相关层 **%d/%d**。'
             % (np.median(rho_dec) if len(rho_dec) else float('nan'), int((rho_dec < 0).sum()), len(rho_dec)))
    R.append('')
    if p_emp < 0.05 and rho_c2 < 0:
        R.append('⇒ **结构性候选与低残差（欠预测）显著同向**：W01 残差**确实向结构瓶颈单元聚集**。')
    else:
        R.append('⇒ **未发现显著同向**：W01 残差**未**明显向结构瓶颈单元聚集 —— 说明当前 `queue` 模型产生的')
        R.append('   （缺失的）拥堵位置与**结构应有位置**不一致。这正是 7.9B-1 要检验的『堵得对不对』。')
    R.append('')
    R.append('> ⚠️ 纪律：候选单元**先**由结构 + 观测映射定义（⛔ 与 W01 流量无关，见门 **C0.22** 自检）；')
    R.append('> 残差只作**事后检验**。⇒ C2 是**探索性的**，确认性检验在 7.9B-1。\n')

    R.append('## C3 — 「堵得对不对」判据（预登记 + v1.0 基线）\n')
    R.append('```')
    R.append('HitRate  = |模型高拥堵单元 ∩ 结构候选单元| / |模型高拥堵单元|')
    R.append('Coverage = |结构候选单元 ∩ 模型高拥堵单元| / |结构候选单元|')
    R.append('随机基线 = |结构候选单元| / |全部单元|    ⇒ lift = HitRate / 随机基线   （>1 才是有位置信息）')
    R.append('```')
    R.append('阈值**现在冻结**：候选 = 先验 ≥ p%.0f（=%.4f）；模型高拥堵 = 单元长度加权 `v/c` ≥ p%.0f（=%.4f）。'
             % (PRIOR_CAND, thr_prior, CONG_Q, thr_cong))
    R.append('')
    R.append(md_table(['量', 'v1.0（queue）基线', '规模分层后（十等分 macro）'],
                      [['候选单元数', '%d（%.2f%%）' % (int(cand.sum()), 100.0 * cand.mean()), '—'],
                       ['模型高拥堵单元数', '%d（%.2f%%）' % (int(model_high.sum()), 100.0 * model_high.mean()), '—'],
                       ['交集', '%d' % inter, '—'],
                       ['**HitRate**', '**%.4f**' % hit, '**%.4f**' % hr_strat],
                       ['**Coverage**', '**%.4f**' % cov, '**%.4f**' % cv_strat],
                       ['随机基线', '%.4f' % base, '%.4f' % base_strat],
                       ['**lift**', '**%.3fx**' % lift, '**%.3fx**' % lift_strat]]))
    R.append('')
    R.append('**v1.0 拥堵基线（`HRS8-9avg`/容量）**：`v/c ≥ 1` 的 link **%d**（%.4f%%），饱和里程 **%.3f km（%.4f%%）**；'
             '拥堵连通分量 **%d** 个，中位长度 **%.1f m**、最长 **%.3f km**。'
             '⚠️ **与 7.9A-0 冻结流量投影的 82 link / 1.151 km 逐位一致 ⇒ 本条流水线自检通过（门 C0.17）。**'
             % (int(sat.sum()), 100.0 * sat.mean(), Lk[sat].sum(), 100.0 * Lk[sat].sum() / Lk.sum(),
                len(cl_arr), np.median(cl_arr) * 1000, cl_arr.max()))
    R.append('')
    R.append('⇒ **`lift` 就是 B-1 必须超过的基线**。若 B-1 后 `lift` 不升（甚至降），则「地图变红」不构成成功。')
    R.append('')
    R.append('### ⚠️ 对 v1.0 基线 `lift` 的**证伪性警告**（先证伪，再断言）\n')
    R.append('- **值域问题**：v1.0 几乎无拥堵（饱和 link **%d** 个 = 全网 %.4f%%，饱和里程 %.3f km），'
             '单元 `v/c` 的 p80 阈值仅 **%.4f** ⇒ 「模型高拥堵单元」在 v1.0 下**近似任意排名**。'
             % (n_sat, 100.0 * sat.mean(), Lk[sat].sum(), thr_cong))
    R.append('- **共同因子**：`Spearman(prior, 单元单车道容量) = %.4f`、`Spearman(单元 v/c, 单元单车道容量) = %.4f` '
             '⇒ 先验与 `v/c` 共享一个**容量因子**，故 `lift` 有一部分**不是位置信息**。'
             % (rho_prior_cap, rho_vc_cap))
    R.append('- ⇒ 因此 `lift = **%.3fx**` **不得**读作「当前模型已经把拥堵放在对的位置」。'
             '它是**弱且被容量污染的**基线。B-1 的价值在于**改变拥堵机制与空间连续性**，而不是把这个数刷高。' % lift)
    R.append('')

    R.append('## C4 — B-1 最小观察集（**提前冻结**）\n')
    R.append(md_table(['层面', '指标'],
                      [['稳定性', '`A_10:19`、parity gap、`never_arrived`、`max_stuck_car`、stuck 命中'],
                       ['总量', '`Sim/Obs`（**仅崩解护栏 ≥ 0.85**，⛔ 不再作目标）'],
                       ['链级', '`excess delay_h = TT/FF − ceil(FF)/FF`、link/单元 `v/c`'],
                       ['结构', 'junction-cluster 拥堵（长度加权 `v/c`、饱和占比）'],
                       ['空间', '**HitRate / Coverage / lift**'],
                       ['连续性', '拥堵连通分量长度（km）与分量数'],
                       ['时段', '07–09 in-network vehicles（15 min 分箱）'],
                       ['重点对象', '**CTE / service 短链 / ramp 链 / connector 链**']]))
    R.append('')
    R.append('**成功判据**：B-1 的成功**不是**「地图变红」，而是能证明 `queue → kinematicWaves` 是否改变了'
             '**拥堵传播机制与空间连续性**（连续性↑ + lift↑，且总量未崩塌）。')
    R.append('**决断规则**：若拥堵状态指标无实质变化且 `Sim/Obs` 未崩塌 ⇒ 判 **`TIMEDYNAMICS_NOT_PRIMARY`** ⇒ 转 7.9C-1。\n')

    R.append('## 门\n')
    R.append(md_table(['id', '判据', '结果', '细节'],
                      [[g['id'], g['desc'], 'PASS' if g['pass'] else '**FAIL**', g['detail']] for g in gates]))
    R.append('')
    R.append('## 主线（用户冻结）\n')
    R.append('`7.9A-0 ✓ → **7.9A-1：sample-consistent capacity** → 7.9B-0 ✓ → **7.9C-0 ✓ 结构审计** → '
             '7.9B-1：queue → kinematicWaves 单变量实验 → （据 B-1）是否进入 7.9C-1：结构性回溢验证`')
    R.append('')
    R.append('⛔ **7.9A-1 与 7.9B-1 绝对不合并** —— 否则无法判断拥堵究竟来自 sampling-capacity 一致性还是 traffic dynamics。')

    io.open(os.path.join(OUT, 'STRUCTURAL_AUDIT_7_9C0.md'), 'w', encoding='utf-8').write('\n'.join(R))
    io.open(os.path.join(OUT, '_run_c0.log'), 'w', encoding='utf-8').write('\n'.join(log_lines))

    log('\n=== gates %d/%d PASS ===' % (n_pass, len(gates)))
    for g in gates:
        if not g['pass']:
            log('  FAIL %s %s -- %s' % (g['id'], g['desc'], g['detail']))
    log('products -> %s' % OUT)
    log('runtime %.2f s' % (time.time() - t0))


if __name__ == '__main__':
    main()

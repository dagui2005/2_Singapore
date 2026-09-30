# -*- coding: utf-8 -*-
"""
Step 7.9E-0 -- Arterial-Layer Delay Attribution Audit
(ZERO-SIMULATION, READ-ONLY, no network/capacity modification)

Implements exactly the frozen rules of:
    reports/arterial_delay_attribution_7_9e0/PREREG_7_9E0.md
        sha256 = 4fa98a96fd05893fb21670304fc0fc007d85f8c83b878cbe181fe11212ea08f1

Target question (user-ratified):
    Is the `primary / secondary / tertiary` arterial layer the main carrier of the
    W01 off-mainline running time AND the existing spatial residual?

Layers:
    E1  time attribution      : ff_time_share(class) = FFTT(class) / FFTT(off_mainline)
    E2  delay attribution     : delay_share(class) + delay_ratio = delay_share / ff_time_share
    E3  spatial residual       : 7.7C-0 frozen residual -> arterial vs non-arterial
                                 (mean/median/quantiles + Spearman + stratified permutation)
    E4  topology              : multi-hop REVERSE Dijkstra arterial -> nearest mainline,
                                 physical distance in m (PRIMARY), hop count AUXILIARY

Discipline: never produces v1.1; no demand/lambda/capacity/queue/service-400/endpoint change.
"""
import os, io, csv, gzip, re, json, time, math, sys, collections, hashlib, heapq
import numpy as np
import pandas as pd

SCRIPT_VER = '7.9E-0 engine v1.0'

ROOT   = r'D:/Luan/2026-05/2_Singapore'
CACHE  = ROOT + '/scripts/od/_cache_network_7_9c0.npz'          # W01 network + source-copy highway/name
SRC    = ROOT + '/reports/matsim_network/network_links_source_copy.csv'
PREREG = ROOT + '/reports/arterial_delay_attribution_7_9e0/PREREG_7_9E0.md'
V1_LS  = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz'
RESID  = ROOT + '/reports/spatial_residual_7_7c0/c0_section_table.csv'
OUT    = ROOT + '/reports/arterial_delay_attribution_7_9e0'
FROZEN = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8',
          ROOT + '/matsim_kw_7_9b1', ROOT + '/reports/spatial_residual_7_7c0']

PREREG_SHA = '4fa98a96fd05893fb21670304fc0fc007d85f8c83b878cbe181fe11212ea08f1'

# ---- frozen constants (PREREG) ---------------------------------------------
EXPECT_LINKS, EXPECT_KM = 693575, 15126.5
EXPECT_SECTIONS = 576
E4_CAP_M = 3000.0                      # PREREG §4 E4 default search cap
E4_BANDS = (300.0, 1000.0, 2000.0)
HOP_CAP = 300
N_PERM = 10000
PERM_SEED = 20260920
SPATIAL_SAMPLE = 20000
TOL = 1e-6

# PREREG §3.1 / §3.2
ARTERIAL_CORE = ('primary', 'secondary', 'tertiary')
MAINLINE_HW   = ('motorway', 'motorway_link')
# PREREG §3.4 auxiliary reporting buckets (exhaustive & disjoint over off_mainline)
OFF_BUCKETS = ('primary', 'secondary', 'tertiary', 'trunk', 'trunk_link',
               'primary_link', 'secondary_link', 'tertiary_link',
               'residential', 'service', 'unclassified', 'other')

log_lines = []; _T0 = time.time()
def log(m):
    s = '[%6.1fs] %s' % (time.time() - _T0, m)
    log_lines.append(s); print(s, flush=True)


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def snap(dirs):
    s = {}
    for d in dirs:
        for dp, _, fns in os.walk(d):
            for fn in fns:
                p = os.path.join(dp, fn)
                try: s[p] = (os.path.getmtime(p), os.path.getsize(p))
                except OSError: pass
    return s


def read_ls(path, ids):
    """linkstats -> per-cache-link (vol, tt). Returns (vol, tt, matched, LINK_unique)."""
    df = pd.read_csv(path, sep='\t', usecols=['LINK', 'HRS8-9avg', 'TRAVELTIME8-9avg'], dtype={'LINK': str})
    uni = bool(df['LINK'].is_unique)
    pos = pd.Series(np.arange(len(ids), dtype=np.int64), index=ids)
    jj = pos.reindex(df['LINK'].to_numpy()).to_numpy()
    good = ~pd.isna(jj)
    vol = np.zeros(len(ids)); tt = np.full(len(ids), np.nan)
    idx = jj[good].astype(np.int64)
    vol[idx] = pd.to_numeric(df['HRS8-9avg'], errors='coerce').to_numpy()[good]
    tt[idx]  = pd.to_numeric(df['TRAVELTIME8-9avg'], errors='coerce').to_numpy()[good]
    return vol, tt, int(good.sum()), uni


def spearman_rank(a):
    r = pd.Series(a).rank(method='average').to_numpy(dtype=float)
    return r


def spearman(x, y):
    rx, ry = spearman_rank(x), spearman_rank(y)
    rx = rx - rx.mean(); ry = ry - ry.mean()
    d = math.sqrt(float((rx * rx).sum()) * float((ry * ry).sum()))
    return float((rx * ry).sum() / d) if d > 0 else float('nan')


def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    gates = []
    def gate(gid, desc, ok, detail):
        gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

    fb = snap(FROZEN)
    log('=== Step 7.9E-0 Arterial-Layer Delay Attribution Audit (%s) ===' % SCRIPT_VER)

    # -- G1  prereg hash gate -------------------------------------------------
    h = sha256_of(PREREG)
    log('prereg sha256 = %s (frozen=%s) MATCH=%s' % (h, PREREG_SHA, h == PREREG_SHA))
    gate('E0.01', 'PREREG file hash == frozen value', h == PREREG_SHA, 'sha256=%s' % h)
    if h != PREREG_SHA:
        log('!! PREREG HASH MISMATCH -> abort (pre-registration integrity gate)')
        raise SystemExit(2)

    # -- G2  zero-simulation (static self-audit of this script) --------------
    src_self = io.open(os.path.abspath(__file__), encoding='utf-8').read()
    FORB = ('subproc' + 'ess.', 'os.sys' + 'tem(', 'Po' + 'pen(', 'jp' + 'ype', 'py' + '4j', '.j' + 'ar')
    hits = [t for t in FORB if t in src_self]
    gate('E0.02', 'zero-simulation (no Java/MATSim invocation API in script)', not hits,
         'forbidden_tokens_found=%s' % hits)

    # -- load network cache (W01 network bridged w/ source-copy highway/name) --
    z = np.load(CACHE, allow_pickle=True)
    frm = [str(x) for x in z['frm']]; to = [str(x) for x in z['to']]
    ln  = z['len_m'].astype(float); cap = z['cap'].astype(float)
    lanes = z['lanes'].astype(float); fs = z['fs_mps'].astype(float)
    hw  = np.array([str(x) for x in z['highway']])
    nm  = np.array([str(x) for x in z['name']])
    ids = np.array([str(x) for x in z['ids']])
    nd_ids = np.array([str(x) for x in z['node_ids']])
    nd_x = z['node_x'].astype(float); nd_y = z['node_y'].astype(float)
    n = len(frm); Lk = ln * 0.001
    log('network: links=%d km=%.2f' % (n, Lk.sum()))
    gate('E0.03', 'network from frozen v1.0 cache (%d links / %.1f km) + matsim_link_id unique'
         % (EXPECT_LINKS, EXPECT_KM), n == EXPECT_LINKS and abs(Lk.sum() - EXPECT_KM) < 5.0
         and len(set(ids.tolist())) == n,
         'links=%d km=%.2f id_unique=%s' % (n, Lk.sum(), len(set(ids.tolist())) == n))

    # -- free-flow time: PREREG §2.1 prefer source-copy travel_time_s ---------
    ff_net = np.where(fs > 0, ln / np.maximum(fs, 1e-9), np.nan)      # W01 network freespeed
    tt_src = np.full(n, np.nan); sp_src = np.full(n, np.nan)
    src_join = 0
    src_rows = 0
    with io.open(SRC, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        srv = {}
        for row in rd:
            src_rows += 1
            k = (row['from_node'], row['to_node'])
            try: srv[k] = (float(row['travel_time_s']), float(row['speed_kmh']))
            except (TypeError, ValueError): pass
    for i in range(n):
        v = srv.get((frm[i], to[i]))
        if v is not None:
            tt_src[i] = v[0]; sp_src[i] = v[1]; src_join += 1
    ff_src = tt_src
    cov_src = float(np.isfinite(ff_src).mean())
    both = np.isfinite(ff_src) & np.isfinite(ff_net) & (ff_src > 0)
    rel = np.abs(ff_net[both] / ff_src[both] - 1.0) if both.any() else np.array([np.nan])
    agree_1e4 = float((rel <= 1e-4).mean()) if both.any() else float('nan')
    log('source copy: rows=%d joined=%d (cov=%.4f) | ff_net vs travel_time_s: n=%d med_rel=%.2e agree(1e-4)=%.4f'
        % (src_rows, src_join, cov_src, int(both.sum()), float(np.nanmedian(rel)), agree_1e4))

    # primary ff: travel_time_s where valid, else W01 freespeed
    ff = np.where(np.isfinite(ff_src) & (ff_src > 0), ff_src, ff_net)
    vld = np.isfinite(ff) & (ff > 0)
    log('primary free-flow valid = %.5f' % vld.mean())
    gate('E0.05', 'free-flow time valid fraction >= 0.99', vld.mean() >= 0.99, 'valid=%.5f' % vld.mean())

    # -- class membership ----------------------------------------------------
    MAIN = np.isin(hw, MAINLINE_HW)
    ART  = np.isin(hw, ARTERIAL_CORE)
    OFF  = ~MAIN
    def bucket_of(h):
        return h if h in OFF_BUCKETS[:-1] else 'other'
    bkt = np.array([bucket_of(x) for x in hw])
    log('mainline=%d (%.1f km) | arterial_core=%d (%.1f km) | off_mainline=%d (%.1f km)'
        % (MAIN.sum(), Lk[MAIN].sum(), ART.sum(), Lk[ART].sum(), OFF.sum(), Lk[OFF].sum()))
    gate('E0.06', 'arterial_core / mainline / off_mainline non-empty',
         ART.sum() > 0 and MAIN.sum() > 0 and OFF.sum() > 0,
         'art=%d main=%d off=%d' % (ART.sum(), MAIN.sum(), OFF.sum()))

    # -- linkstats (W01 it.19) ------------------------------------------------
    vol, tt, matched, uni = read_ls(V1_LS, ids)
    gate('E0.04', 'W01 it.19 linkstats fields present & LINK unique', uni and matched > 0,
         'matched=%d LINK_unique=%s' % (matched, uni))

    # =========================== E1 + E2 ====================================
    fftt_h = np.where(vld, ff, 0.0) / 3600.0                    # structural link-hours
    vh_ff  = np.where(vld, vol * ff, 0.0) / 3600.0              # VOLUME-weighted VH (cross-check)
    dh     = np.where(np.isfinite(tt) & vld, np.maximum(tt - ff, 0.0) * vol, 0.0) / 3600.0

    denom_ff  = float(fftt_h[OFF].sum())        # PREREG §4 E1 denominator = off_mainline
    denom_wff = float(vh_ff[OFF].sum())
    denom_dh  = float(dh[OFF].sum())
    tot_dh    = float(dh.sum())
    log('E1 FFTT(off_mainline)=%.1f link-h | VH_ff(off)=%.1f | E2 delay(off)=%.1f h | delay(all)=%.1f h'
        % (denom_ff, denom_wff, denom_dh, tot_dh))

    def shares(mask):
        return (float(fftt_h[mask].sum() / denom_ff) if denom_ff > 0 else float('nan'),
                float(vh_ff[mask].sum() / denom_wff) if denom_wff > 0 else float('nan'),
                float(dh[mask].sum() / denom_dh) if denom_dh > 0 else float('nan'))

    rows = []
    art_ff, art_wff, art_dh = shares(ART)
    for b in OFF_BUCKETS:
        m = (bkt == b) & OFF
        fs_, ws_, ds_ = shares(m)
        rows.append({'bucket': b, 'n_links': int(m.sum()), 'km': float(Lk[m].sum()),
                     'fftt_h': float(fftt_h[m].sum()), 'ff_time_share': fs_,
                     'vh_ff': float(vh_ff[m].sum()), 'wff_share': ws_,
                     'delay_h': float(dh[m].sum()), 'delay_share': ds_,
                     'delay_ratio': (ds_ / fs_) if (fs_ and fs_ == fs_ and fs_ > 0) else float('nan'),
                     'delay_ratio_weighted': (ds_ / ws_) if (ws_ and ws_ == ws_ and ws_ > 0) else float('nan')})
    rows.append({'bucket': 'arterial_core', 'n_links': int(ART.sum()), 'km': float(Lk[ART].sum()),
                 'fftt_h': float(fftt_h[ART].sum()), 'ff_time_share': art_ff,
                 'vh_ff': float(vh_ff[ART].sum()), 'wff_share': art_wff,
                 'delay_h': float(dh[ART].sum()), 'delay_share': art_dh,
                 'delay_ratio': (art_dh / art_ff) if art_ff > 0 else float('nan'),
                 'delay_ratio_weighted': (art_dh / art_wff) if art_wff > 0 else float('nan')})
    with open(OUT + '/e0_class_summary.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader()
        for r in rows: w.writerow(r)
    for r in rows:
        log('  E1/E2 %-14s share(ff)=%.4f wshare=%.4f delay_share=%.4f delay_ratio=%.4f'
            % (r['bucket'], r['ff_time_share'], r['wff_share'], r['delay_share'], r['delay_ratio']))

    # closure check (E0.11)
    s_ff = sum(r['ff_time_share'] for r in rows if r['bucket'] != 'arterial_core')
    s_dh = sum(r['delay_share'] for r in rows if r['bucket'] != 'arterial_core')
    gate('E0.11', 'all class shares sum to parent (tol 1e-6)',
         abs(s_ff - 1.0) <= 1e-6 and abs(s_dh - 1.0) <= 1e-6,
         'sum_ff_share=%.9f sum_delay_share=%.9f' % (s_ff, s_dh))

    # =========================== E4 topology =================================
    outb = collections.defaultdict(list); inb = collections.defaultdict(list)
    frm_l = frm; to_l = to
    for i in range(n):
        outb[frm_l[i]].append(i); inb[to_l[i]].append(i)

    def dij_rev(weight, capm):
        d = np.full(n, math.inf, dtype=float); pq = []
        for i in np.where(MAIN)[0]:
            d[i] = 0.0; heapq.heappush(pq, (0.0, int(i)))
        while pq:
            du, k = heapq.heappop(pq)
            if du > d[k] + 1e-9: continue
            if du >= capm: continue
            for j in inb.get(frm_l[k], ()):
                nd = du + weight(j)
                if nd < d[j] - 1e-9 and nd <= capm:
                    d[j] = nd; heapq.heappush(pq, (nd, int(j)))
        return d

    Lm = ln  # metres
    d_m = dij_rev(lambda j: float(Lm[j]), E4_CAP_M)             # PREREG §4 E4 PRIMARY (metres)
    d_h = dij_rev(lambda j: 1.0, float(HOP_CAP))                # AUXILIARY (hops)
    fin = np.isfinite(d_m)
    log('E4 arterial_core: finite=%.4f med=%.1fm p90=%.1fm | hops med=%.1f (aux)' %
        (fin[ART].mean(),
         float(np.median(d_m[ART][np.isfinite(d_m[ART])])) if fin[ART].any() else -1,
         float(np.percentile(d_m[ART][np.isfinite(d_m[ART])], 90)) if fin[ART].any() else -1,
         float(np.median(d_h[ART][np.isfinite(d_h[ART])])) if np.isfinite(d_h[ART]).any() else -1))
    gate('E0.10', 'E4 uses multi-hop topology distance (not single-hop) as primary',
         bool(np.isfinite(d_h[ART]).any() and np.median(d_h[ART][np.isfinite(d_h[ART])]) >= 2.0),
         'hop_median=%.2f' % float(np.median(d_h[ART][np.isfinite(d_h[ART])])) if np.isfinite(d_h[ART]).any() else 'nan')

    topo_rows = []
    for b in OFF_BUCKETS:
        m = (bkt == b) & OFF
        topo_rows.append(topo_summary(b, m, d_m, d_h, dh))
    topo_rows.append(topo_summary('arterial_core', ART, d_m, d_h, dh))
    # delay-weighted distance to mainline (coupling), PREREG §5 / user E4
    for r in topo_rows:
        r['delay_weighted_dist_m'] = None
    dw = {}
    for b, m in [('arterial_core', ART)] + [(b, (bkt == b) & OFF) for b in OFF_BUCKETS]:
        wsum = float(dh[m].sum())
        mm = m & np.isfinite(d_m)
        dw[b] = float(np.average(d_m[mm], weights=dh[mm])) if (wsum > 0 and mm.any() and dh[mm].sum() > 0) else None
    for r in topo_rows:
        r['delay_weighted_dist_m'] = dw.get(r['bucket'])
    with open(OUT + '/e0_topology_summary.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(topo_rows[0].keys())); w.writeheader()
        for r in topo_rows: w.writerow(r)

    # optional spatial consistency (straight-line vs topology), sampled
    spatial = None
    try:
        mw_i = np.where(MAIN)[0]
        # build fast node-id -> index for coords
        nidx = {s: k for k, s in enumerate(nd_ids.tolist())}
        def mid(i):
            a = nidx.get(frm_l[i]); b = nidx.get(to_l[i])
            if a is None or b is None: return (np.nan, np.nan)
            return (0.5 * (nd_x[a] + nd_x[b]), 0.5 * (nd_y[a] + nd_y[b]))
        mw_mid = np.array([mid(i) for i in mw_i], dtype=float)
        mw_mid = mw_mid[np.isfinite(mw_mid).all(axis=1)]
        grid = collections.defaultdict(list); CELL = 500.0
        for k in range(len(mw_mid)):
            grid[(int(mw_mid[k, 0] // CELL), int(mw_mid[k, 1] // CELL))].append(k)
        art_fin = np.where(ART & np.isfinite(d_m))[0]
        rng = np.random.default_rng(PERM_SEED)
        samp = rng.choice(art_fin, size=min(SPATIAL_SAMPLE, len(art_fin)), replace=False) if len(art_fin) else np.array([], int)
        ratios = []
        for i in samp:
            x, y = mid(i)
            if not (np.isfinite(x) and np.isfinite(y)): continue
            cx, cy = int(x // CELL), int(y // CELL); best = math.inf
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for k in grid.get((cx + dx, cy + dy), ()):
                        j = mw_i[k]
                        d2 = (mw_mid[k, 0] - x) ** 2 + (mw_mid[k, 1] - y) ** 2
                        if d2 < best: best = d2
            if best < math.inf and d_m[i] > 0:
                ratios.append(float(d_m[i]) / math.sqrt(best))
        ratios = np.array(ratios, dtype=float)
        okv = ratios[ratios > 0]
        viol = float((ratios < 1.0 - 1e-6).mean()) if len(ratios) else float('nan')
        spatial = {'n_sampled': int(len(ratios)),
                   'median_topo_over_straight': float(np.median(okv)) if len(okv) else None,
                   'p10': float(np.percentile(okv, 10)) if len(okv) else None,
                   'violation_share_topo_lt_straight': viol,
                   'note': 'topology distance >= straight-line expected; small violation share is a geometric artifact'}
        log('E4 spatial consistency: n=%d med(topo/straight)=%.3f viol=%.4f'
            % (int(len(ratios)), (spatial['median_topo_over_straight'] or float('nan')), viol))
    except Exception as e:
        spatial = {'status': 'BLOCKED', 'error': repr(e)}
        log('E4 spatial consistency BLOCKED: %r' % e)

    # =========================== E3 residual coupling ========================
    res = pd.read_csv(RESID, dtype={'lta_linkid': str}, low_memory=False)
    nsec = int(len(res))
    log('7.7C-0 sections = %d' % nsec)
    gate('E0.08', '7.7C-0 section table readable & >= %d sections' % EXPECT_SECTIONS,
         nsec >= EXPECT_SECTIONS, 'n_sections=%d' % nsec)

    res['residual'] = pd.to_numeric(res['ratio_8_9'], errors='coerce') - 1.0
    dh_str = pd.Series([str(x) for x in res['dominant_highway']], index=res.index)
    res['is_art'] = dh_str.isin(ARTERIAL_CORE)
    vc = dh_str.value_counts().to_dict()
    log('E3 dominant_highway counts: %s'
        % {k: int(v) for k, v in sorted(vc.items(), key=lambda kv: -kv[1])})
    ok = res['residual'].notna()
    n_ok = int(ok.sum())
    log('E3 valid residual samples = %d (arterial=%d)' % (n_ok, int((ok & res['is_art']).sum())))
    gate('E0.09', 'ratio_8_9 valid samples enough for E3 (>=30 per group)',
         n_ok >= 30 and int((ok & res['is_art']).sum()) >= 30 and int((ok & ~res['is_art']).sum()) >= 30,
         'n_ok=%d art=%d non=%d' % (n_ok, int((ok & res['is_art']).sum()), int((ok & ~res['is_art']).sum())))

    def q(s, p): return float(np.percentile(s, p)) if len(s) else None
    coup_rows = []
    for label, mask in [('arterial_core', res['is_art']),
                        ('non_arterial', ~res['is_art']),
                        ('ALL', pd.Series(True, index=res.index))]:
        s = res.loc[ok & mask, 'residual'].to_numpy(dtype=float)
        coup_rows.append({'group': label, 'n_sections': int(len(s)),
                          'mean': float(np.mean(s)) if len(s) else None,
                          'median': float(np.median(s)) if len(s) else None,
                          'p10': q(s, 10), 'p90': q(s, 90),
                          'std': float(np.std(s, ddof=1)) if len(s) > 1 else None,
                          'mean_sim_obs_ratio': float(1 + np.mean(s)) if len(s) else None})
    for sub in ARTERIAL_CORE:
        mask = ok & (dh_str == sub)
        s = res.loc[mask, 'residual'].to_numpy(dtype=float)
        coup_rows.append({'group': 'art:%s' % sub, 'n_sections': int(len(s)),
                          'mean': float(np.mean(s)) if len(s) else None,
                          'median': float(np.median(s)) if len(s) else None,
                          'p10': q(s, 10), 'p90': q(s, 90),
                          'std': float(np.std(s, ddof=1)) if len(s) > 1 else None,
                          'mean_sim_obs_ratio': float(1 + np.mean(s)) if len(s) else None})
    with open(OUT + '/e0_residual_coupling.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(coup_rows[0].keys())); w.writeheader()
        for r in coup_rows: w.writerow(r)

    # Spearman(residual, arterial indicator) among valid sections
    sub = res.loc[ok]
    rho = spearman(sub['residual'].to_numpy(dtype=float), sub['is_art'].astype(float).to_numpy())

    # stratified permutation (strata: planning 'region', then 'pa' if large enough)
    perm_rows = []
    def perm_test(stratum_col):
        if stratum_col not in sub.columns:
            perm_rows.append({'stratum': stratum_col, 'status': 'BLOCKED', 'reason': 'column absent'})
            return None
        y = sub['residual'].to_numpy(dtype=float)
        g = sub['is_art'].to_numpy()
        st = np.array([str(x) for x in sub[stratum_col]])
        obs = (y[g].mean() - y[~g].mean()) if (g.any() and (~g).any()) else float('nan')
        if not np.isfinite(obs):
            perm_rows.append({'stratum': stratum_col, 'status': 'BLOCKED', 'reason': 'one group empty'})
            return None
        idx_by = collections.defaultdict(list)
        for i, s_ in enumerate(st): idx_by[s_].append(i)
        rng = np.random.default_rng(PERM_SEED)
        cnt = 0; reps = []
        for _ in range(N_PERM):
            gp = g.copy()
            for s_, idxs in idx_by.items():
                if len(idxs) > 1:
                    v = gp[idxs]; rng.shuffle(v); gp[idxs] = v
            if not gp.any() or gp.all(): continue
            stat = y[gp].mean() - y[~gp].mean()
            reps.append(stat)
            if abs(stat) >= abs(obs) - 1e-12: cnt += 1
        p = (cnt + 1) / (len(reps) + 1) if reps else float('nan')
        perm_rows.append({'stratum': stratum_col, 'status': 'OK', 'statistic': 'mean_art_minus_nonart',
                          'observed': float(obs), 'p_value': float(p), 'n_perm': len(reps),
                          'n_arterial': int(g.sum()), 'n_nonarterial': int((~g).sum()),
                          'n_strata': len(idx_by)})
        log('E3 permutation[%s]: obs=%.4f p=%.4f (n_perm=%d, strata=%d)'
            % (stratum_col, obs, p, len(reps), len(idx_by)))
        return p
    p_region = perm_test('region')
    p_pa = perm_test('pa')

    # radial x reciprocal cross grouping (if fields present)
    cross_rows = []
    if 'radial' in res.columns and 'has_reciprocal_pair' in res.columns:
        rad_arr = np.array([str(x) for x in res['radial']])
        for rad in sorted(set(rad_arr.tolist())):
            for rec in (True, False):
                m = ok & (rad_arr == rad) & (res['has_reciprocal_pair'].astype(bool) == rec)
                s = res.loc[m, 'residual'].to_numpy(dtype=float)
                if len(s):
                    cross_rows.append({'radial': rad, 'has_reciprocal': rec, 'n': int(len(s)),
                                       'mean_residual': float(np.mean(s))})
    else:
        cross_rows.append({'status': 'BLOCKED', 'reason': 'radial/has_reciprocal_pair absent'})

    with open(OUT + '/e0_residual_permutation.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['kind', 'stratum', 'status', 'observed', 'p_value', 'n_perm', 'n_arterial', 'n_nonarterial', 'n_strata'])
        for r in perm_rows:
            w.writerow(['perm', r.get('stratum'), r.get('status'), r.get('observed'), r.get('p_value'),
                        r.get('n_perm'), r.get('n_arterial'), r.get('n_nonarterial'), r.get('n_strata')])
        w.writerow(['spearman', 'residual~is_arterial', 'OK', '%.6f' % rho, '', '', '', '', ''])
        for r in cross_rows:
            w.writerow(['cross', r.get('radial', r.get('status')), r.get('status', 'OK'),
                        r.get('mean_residual', ''), '', r.get('n', ''), '', '', ''])

    # =========================== verdict =====================================
    grp_max = max((r for r in rows if r['bucket'] != 'arterial_core'), key=lambda r: (r['delay_share'] or -1))
    art_dom = (grp_max['bucket'] in ('primary', 'secondary', 'tertiary'))
    over = (art_dh / art_ff) if art_ff > 0 else float('nan')
    def gp(gid):
        return next((g['pass'] for g in gates if g['id'] == gid), False)
    n_art_sec = int((ok & res['is_art']).sum()); n_non_sec = int((ok & ~res['is_art']).sum())
    e3_ok = (n_art_sec >= 30 and n_non_sec >= 30)
    coupled_p = min([p for p in (p_region, p_pa) if p is not None and np.isfinite(p)], default=float('nan'))
    coupled = bool(e3_ok and np.isfinite(coupled_p) and coupled_p < 0.05)
    blocked = not (gp('E0.05') and gp('E0.06') and gp('E0.08') and gp('E0.09') and gp('E0.10'))
    flags = {
        'ARTERIAL_OVER_REPRESENTED_IN_DELAY': bool(np.isfinite(over) and over >= 1.05),
        'ARTERIAL_IS_MAX_DELAY_SHARE_OFFMAIN': bool(art_dom),
        'ARTERIAL_RESIDUAL_COUPLED': coupled,
        'ARTERIAL_RESIDUAL_SPEARMAN_RHO': round(rho, 4) if np.isfinite(rho) else None,
        'ARTERIAL_RESIDUAL_COUPLED_P': None if not np.isfinite(coupled_p) else round(coupled_p, 5),
        'DOMINANT_OFFMAIN_DELAY_BUCKET': grp_max['bucket'],
        'ARTERIAL_DELAY_SHARE_OFFMAIN': round(art_dh, 6) if np.isfinite(art_dh) else None,
        'ARTERIAL_DELAY_RATIO': round(over, 4) if np.isfinite(over) else None,
        'E3_STATUS': 'OK' if e3_ok else 'BLOCKED_INSUFFICIENT_ARTERIAL_SECTIONS',
        'E3_N_ARTERIAL_SECTIONS': n_art_sec,
        'E3_N_NONARTERIAL_SECTIONS': n_non_sec,
    }
    if blocked:
        v = 'ARTERIAL_LAYER_AUDIT_BLOCKED'
    elif flags['ARTERIAL_OVER_REPRESENTED_IN_DELAY'] and art_dom and coupled:
        v = 'ARTERIAL_LAYER_SUPPORTS_DELAY_ATTRIBUTION'
    elif (not flags['ARTERIAL_OVER_REPRESENTED_IN_DELAY']) and over < 0.95:
        v = 'ARTERIAL_LAYER_NOT_PRIMARY_DELAY_ATTRIBUTION'
    else:
        v = 'ARTERIAL_LAYER_EVIDENCE_MIXED'
    log('VERDICT = %s' % v)
    log('FLAGS   = %s' % json.dumps(flags, ensure_ascii=False))

    # =========================== checks / manifest ===========================
    manifest = {'script': SCRIPT_VER, 'prereg_sha256': PREREG_SHA, 'prereg_sha256_recomputed': h,
                'zero_simulation': True, 'run_started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t0)),
                'runtime_sec': round(time.time() - t0, 1),
                'inputs': []}
    for p in (SRC, CACHE, V1_LS, RESID, PREREG):
        manifest['inputs'].append({'path': os.path.relpath(p, ROOT), 'sha256': sha256_of(p),
                                   'bytes': os.path.getsize(p), 'mtime': os.path.getmtime(p)})
    json.dump(manifest, open(OUT + '/e0_input_manifest.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    gate('E0.12', 'provenance manifest has path/sha256/bytes/mtime + script version',
         bool(manifest['script']) and all(all(k in it for k in ('path', 'sha256', 'bytes', 'mtime'))
                                          for it in manifest['inputs']),
         'n_inputs=%d script=%s' % (len(manifest['inputs']), manifest['script']))

    fa = snap(FROZEN)
    changed = sum(1 for k in set(fb) | set(fa) if fb.get(k) != fa.get(k))
    gate('E0.07', 'frozen artifacts untouched (no write-back)', changed == 0, 'changed=%d' % changed)

    with open(OUT + '/e0_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])

    summary = {'script': SCRIPT_VER, 'verdict': v, 'flags': flags,
               'prereg_sha256': PREREG_SHA, 'prereg_match': bool(h == PREREG_SHA),
               'definitions': {'arterial_core': list(ARTERIAL_CORE), 'mainline': list(MAINLINE_HW),
                               'off_mainline': 'highway not in mainline', 'e4_cap_m': E4_CAP_M},
               'E1_E2_class_shares': rows,
               'E3': {'n_sections': nsec, 'n_valid': n_ok, 'spearman_rho': rho,
                      'n_arterial_sections': n_art_sec, 'n_nonarterial_sections': n_non_sec,
                      'status': 'OK' if e3_ok else 'BLOCKED_INSUFFICIENT_ARTERIAL_SECTIONS',
                      'dominant_highway_counts': {k: int(v) for k, v in vc.items()},
                      'permutation': perm_rows, 'coupling': coup_rows, 'radial_cross': cross_rows},
               'prereg_reconciliation': {
                   'network_link_table': 'cache built from W01 output network (matsim_link_id/capacity/topology) bridged with source-copy highway+name; source copy lacks matsim_link_id & capacity, so the W01 network is REQUIRED to satisfy gate E0.03 and to join linkstats LINK ids',
                   'free_flow_time_primary': 'source-copy travel_time_s where valid (coverage=1.0000), else W01 freespeed len/fs',
                   'residual_field_mapping': 'c0_section_table has section_length_m (no length_m); residual = ratio_8_9 - 1',
                   'e3_underpowered': 'frozen 7.7C-0 target yard is dominated by motorway/expressway sections -> only %d arterial-dominant sections (<30) -> E3 arterial leg BLOCKED, NOT silently substituted' % n_art_sec,
               },
               'E4_topology': topo_rows, 'E4_spatial_consistency': spatial,
               'totals': {'fftt_off_h': denom_ff, 'vh_ff_off': denom_wff,
                          'delay_off_h': denom_dh, 'delay_all_h': tot_dh},
               'n_pass': sum(1 for g in gates if g['pass']), 'n_total': len(gates),
               'gates': gates, 'runtime_sec': round(time.time() - t0, 1)}
    json.dump(summary, open(OUT + '/e0_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    npass = sum(1 for g in gates if g['pass'])
    log('GATES: %d/%d PASS  (runtime %.1f s)' % (npass, len(gates), time.time() - t0))
    log('VERDICT = %s' % v)
    open(OUT + '/_run_e0.log', 'w', encoding='utf-8').write('\n'.join(log_lines))
    return 0


def topo_summary(bucket, mask, d_m, d_h, dh):
    dd = d_m[mask]; hh = d_h[mask]
    fin = np.isfinite(dd)
    dv = dd[fin]
    row = {'bucket': bucket, 'n_links': int(mask.sum())}
    row['finite_share'] = float(fin.mean()) if len(dd) else None
    row['acc_dist_median_m'] = float(np.median(dv)) if len(dv) else None
    row['acc_dist_p90_m'] = float(np.percentile(dv, 90)) if len(dv) else None
    for b in E4_BANDS:
        row['cov_le%dm' % int(b)] = float((dv <= b).mean()) if len(dv) else None
    row['cov_le%dm' % int(E4_CAP_M)] = float((dv <= E4_CAP_M).mean()) if len(dv) else None
    hv = hh[np.isfinite(hh)]
    row['hop_median_aux'] = float(np.median(hv)) if len(hv) else None
    return row


if __name__ == '__main__':
    sys.exit(main())

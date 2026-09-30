# -*- coding: utf-8 -*-
"""
Step 7.9D-0 -- Access-System Delay-Trapping Audit
(ZERO-SIMULATION for structure; linkstats read ONLY under the frozen PREREG)

Implements exactly the frozen rules of:
  reports/access_delay_trapping_7_9d0/PREREG_7_9D-0.md
      sha256 = 564310dee2e85a487c2dd4a93755f41b75f2fcdfe436dea5c6f068fe6bf6ee85

Narrow question:
  Why can these return-incompetent service/connector short links keep absorbing
  large delay while NOT feeding pressure back to the mainline?

Three interfaces: mainline capacity <-> access topology <-> local storage
  D0 base-rate control (km/link/delay share + ratio)      [MANDATORY FIRST]
  D1 one-way valve (sink-valve / single-exit / lane drop / asym)
  D2 local storage depth (fill time + DETERMINISTIC-CAPACITY test)
  D3 queue coupling (delay-weighted d_up / d_down hop distributions)
  D4 terminal exposure (descriptive, NO verdict power)

Discipline: no sim re-run; frozen artifacts untouched; v1.0 untouched; no v1.1.
"""
import os, io, re, csv, gzip, json, time, math, gc, sys, collections, hashlib, heapq
import numpy as np
import pandas as pd

ROOT   = r'D:/Luan/2026-05/2_Singapore'
CACHE  = ROOT + '/scripts/od/_cache_network_7_9c0.npz'
L2U    = ROOT + '/scripts/od/_cache_link_unit_7_9b1.npz'
C0CSV  = ROOT + '/reports/structural_junction_cluster_audit_7_9c0/c0_junction_clusters.csv'
PREREG = ROOT + '/reports/access_delay_trapping_7_9d0/PREREG_7_9D-0.md'
POPU   = ROOT + '/matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz'
V1_LS  = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz'
KW_LS  = ROOT + '/matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz'
OUT    = ROOT + '/reports/access_delay_trapping_7_9d0'
FROZEN = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8', ROOT + '/matsim_kw_7_9b1']

PREREG_SHA = '564310dee2e85a487c2dd4a93755f41b75f2fcdfe436dea5c6f068fe6bf6ee85'

# ---- frozen constants (PREREG §4) -------------------------------------------
CELL, D_IF, D_IF_SENS = 7.5, 3, (1, 5)
REQ_FILL_S, LANE_CAP_REF = 30.0, 1800.0
SHORT_M, VALVE_THR, THIN_THR = 20.0, 0.10, 0.60
RATIO_BASE, RATIO_CONC, PRIOR_CAND = 1.50, 2.50, 80.0
CLASSES = ('motorway', 'ramp', 'connector', 'service', 'other')
CTE_NAME, CTE_EXPECT_N = 'Central Expressway', 603
BANNED_MASK = 'CTE'          # "CTE" in name.upper() hits 0 -> banned

log_lines = []; _T0 = time.time()
def log(m):
    s = '[%6.1fs] %s' % (time.time() - _T0, m)
    log_lines.append(s); print(s, flush=True)

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
    df = pd.read_csv(path, sep='\t', usecols=['LINK', 'HRS8-9avg', 'TRAVELTIME8-9avg'],
                     dtype={'LINK': str})
    pos = pd.Series(np.arange(len(ids), dtype=np.int64), index=ids)
    jj = pos.reindex(df['LINK'].to_numpy()).to_numpy()
    good = ~pd.isna(jj)
    vol = np.zeros(len(ids)); tt = np.full(len(ids), np.nan)
    idx = jj[good].astype(np.int64)
    vol[idx] = pd.to_numeric(df['HRS8-9avg'], errors='coerce').to_numpy()[good]
    tt[idx]  = pd.to_numeric(df['TRAVELTIME8-9avg'], errors='coerce').to_numpy()[good]
    return vol, tt, int(good.sum())


def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    gates = []
    def gate(gid, desc, ok, detail):
        gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

    fb = snap(FROZEN)
    log('=== Step 7.9D-0 Access-System Delay-Trapping Audit ===')

    # ---- prereg integrity -------------------------------------------------
    h = hashlib.sha256(open(PREREG, 'rb').read()).hexdigest()
    log('prereg sha256 = %s (frozen=%s) MATCH=%s' % (h[:16] + '...', PREREG_SHA[:16] + '...', h == PREREG_SHA))

    # ---- load network -----------------------------------------------------
    z = np.load(CACHE, allow_pickle=True)
    frm = [str(x) for x in z['frm']]; to = [str(x) for x in z['to']]
    ln = z['len_m'].astype(float); cap = z['cap'].astype(float)
    lanes = z['lanes'].astype(float); fs = z['fs_mps'].astype(float)
    hw = np.array([str(x) for x in z['highway']])
    nm = np.array([str(x) for x in z['name']])
    ids = np.array([str(x) for x in z['ids']])
    n = len(frm); Lk = ln * 0.001
    cls = np.array(["ramp" if x in ("motorway_link", "trunk_link")
                    else "connector" if x.endswith("_link")
                    else "service" if x == "service"
                    else "motorway" if x in ("motorway", "trunk")
                    else "other" for x in hw])
    MW = (cls == 'motorway'); ACC = np.isin(cls, ['service', 'connector', 'ramp'])
    log('network: links=%d km=%.2f' % (n, Lk.sum()))
    gate('D0.01', 'network from frozen v1.0 cache (693575 / 15126.5 km)',
         n == 693575 and abs(Lk.sum() - 15126.5) < 5.0, 'links=%d km=%.2f' % (n, Lk.sum()))

    counts = {c: int((cls == c).sum()) for c in CLASSES}
    log('class counts: %s' % counts)
    gate('D0.02', 'class masks non-degenerate', all(v > 0 for v in counts.values()), str(counts))

    outb = collections.defaultdict(list); inb = collections.defaultdict(list)
    for i in range(n):
        outb[frm[i]].append(i); inb[to[i]].append(i)

    # ---- BFS d_up / d_down (PREREG §3.0) ----------------------------------
    def bfs(expand_src, expand_dst):
        """multi-source BFS; sources = MW links at dist 0; neighbours via accessor."""
        d = np.full(n, -1, dtype=np.int32)
        dq = collections.deque()
        for i in np.where(MW)[0]:
            d[i] = 0; dq.append(i)
        while dq:
            k = dq.popleft(); nd = d[k] + 1
            for j in expand_src(k):
                if d[j] < 0:
                    d[j] = nd; dq.append(j)
        return d
    # d_up: from mainline k, its downstream successors i (k is a feeder of i)
    d_up   = bfs(lambda k: outb.get(to[k], []), None)
    # d_down: from mainline k, its upstream feeders j (j is fed-into k)
    d_down = bfs(lambda k: inb.get(frm[k], []), None)
    log('d_up:   finite=%.4f%% min=%d median=%d p90=%d max=%d'
        % (100 * (d_up >= 0).mean(), d_up.min(), int(np.median(d_up)), int(np.percentile(d_up, 90)), d_up.max()))
    log('d_down: finite=%.4f%% min=%d median=%d p90=%d max=%d'
        % (100 * (d_down >= 0).mean(), d_down.min(), int(np.median(d_down)), int(np.percentile(d_down, 90)), d_down.max()))
    gate('D0.03', 'd_up BFS complete (100% finite, min=0)',
         bool((d_up >= 0).all()) and int(d_up.min()) == 0, 'finite=%.4f%% min=%d' % (100 * (d_up >= 0).mean(), d_up.min()))
    gate('D0.04', 'd_down BFS complete (100% finite, min=0)',
         bool((d_down >= 0).all()) and int(d_down.min()) == 0, 'finite=%.4f%% min=%d' % (100 * (d_down >= 0).mean(), d_down.min()))

    IF_UP = (d_up >= 0) & (d_up <= D_IF)
    IF_DOWN = (d_down >= 0) & (d_down <= D_IF)
    INTERFACE = IF_UP | IF_DOWN
    log('INTERFACE links: %d (%.3f%%)   IF_UP=%d  IF_DOWN=%d'
        % (INTERFACE.sum(), 100 * INTERFACE.mean(), IF_UP.sum(), IF_DOWN.sum()))
    if_nodes = set()
    for i in np.where(INTERFACE)[0]:
        if_nodes.add(frm[i]); if_nodes.add(to[i])
    log('INTERFACE nodes: %d' % len(if_nodes))

    # ---- delays (frozen linkstats) ----------------------------------------
    def delays(path):
        vol, tt, matched = read_ls(path, ids)
        with np.errstate(divide='ignore', invalid='ignore'):
            ff = np.where(fs > 0, ln / fs, np.nan)
            quant = np.where(ff > 0, np.ceil(ff) / ff, np.nan)
            excess = np.where(np.isfinite(tt) & np.isfinite(ff), tt / ff - quant, 0.0)
        dh = np.where(np.isfinite(tt) & np.isfinite(ff), np.maximum(tt - np.ceil(ff), 0.0) * vol, 0.0) / 3600.0
        return {'vol': vol, 'tt': tt, 'excess': excess, 'delay_h': dh, 'matched': matched}
    D = {'V1': delays(V1_LS), 'KW': delays(KW_LS)}
    for t in ('V1', 'KW'):
        log('  [%s] matched=%d  total delay=%.1f h' % (t, D[t]['matched'], D[t]['delay_h'].sum()))
    d1 = D['V1']['delay_h']; tot1 = float(d1.sum())

    # ---- D0 base-rate control (MANDATORY FIRST) ---------------------------
    def ratio_table(mask):
        km = {c: float(Lk[(cls == c) & mask].sum()) for c in CLASSES}
        lk = {c: int(((cls == c) & mask).sum()) for c in CLASSES}
        dy = {c: float(d1[(cls == c) & mask].sum()) for c in CLASSES}
        tkm, tlk, tdy = sum(km.values()), sum(lk.values()), sum(dy.values())
        rows = {}
        for c in CLASSES:
            ks = km[c] / tkm if tkm > 0 else 0.0
            ls = lk[c] / tlk if tlk > 0 else 0.0
            ds = dy[c] / tdy if tdy > 0 else 0.0
            rows[c] = {'km': km[c], 'km_share': ks, 'links': lk[c], 'link_share': ls,
                       'delay_h': dy[c], 'delay_share': ds,
                       'ratio_delay_over_km': (ds / ks if ks > 0 else float('nan'))}
        return {'by_class': rows, 'km_total': tkm, 'delay_total_h': tdy}
    base_all = ratio_table(np.ones(n, dtype=bool))
    base_if = ratio_table(INTERFACE)
    log('D0 base-rate (ALL):  service km_share=%.4f delay_share=%.4f ratio=%.3f'
        % (base_all['by_class']['service']['km_share'], base_all['by_class']['service']['delay_share'],
           base_all['by_class']['service']['ratio_delay_over_km']))
    log('D0 base-rate (IFACE):service km_share=%.4f delay_share=%.4f ratio=%.3f'
        % (base_if['by_class']['service']['km_share'], base_if['by_class']['service']['delay_share'],
           base_if['by_class']['service']['ratio_delay_over_km']))
    gate('D0.05', 'base-rate table produced (km/link/delay share + ratio)',
         base_all['delay_total_h'] > 0 and base_if['delay_total_h'] > 0,
         'all_delay=%.1f h iface_delay=%.1f h' % (base_all['delay_total_h'], base_if['delay_total_h']))

    # ---- D1 valve ------------------------------------------------------
    nodes = set(frm) | set(to)
    has_in_main = {}; has_out_main = {}; has_out_acc = {}
    for x in nodes:
        has_in_main[x] = any(MW[i] for i in inb.get(x, []))
        has_out_main[x] = any(MW[i] for i in outb.get(x, []))
        has_out_acc[x] = any(ACC[i] for i in outb.get(x, []))
    sink_valve = [x for x in nodes if has_in_main[x] and has_out_acc[x] and not has_out_main[x]]
    sv_if = [x for x in sink_valve if x in if_nodes]
    single_exit = [x for x in sink_valve if len(outb.get(x, [])) == 1]
    lane_drop = 0
    for x in sink_valve:
        ins = inb.get(x, []); outs = outb.get(x, [])
        li = max((lanes[i] for i in ins), default=0.0)
        lo = min((lanes[i] for i in outs), default=0.0) if outs else 0.0
        if li > lo: lane_drop += 1
    asym = float((np.abs(d_up.astype(np.int64) - d_down.astype(np.int64)) >= 2)[INTERFACE].mean())
    d1r = {'n_sink_valve_global': len(sink_valve),
           'n_sink_valve_interface': len(sv_if),
           'sink_valve_share_interface': (len(sv_if) / len(if_nodes)) if if_nodes else 0.0,
           'n_valve_single_exit': len(single_exit),
           'valve_single_exit_share': (len(single_exit) / len(sink_valve)) if sink_valve else 0.0,
           'n_valve_lane_drop': lane_drop,
           'valve_lane_drop_share': (lane_drop / len(sink_valve)) if sink_valve else 0.0,
           'asym_share_interface': asym}
    log('D1 valve: global sink-valve=%d  in-interface=%d (share=%.4f)  single-exit=%.3f  lane-drop=%.3f  asym=%.3f'
        % (len(sink_valve), len(sv_if), d1r['sink_valve_share_interface'],
           d1r['valve_single_exit_share'], d1r['valve_lane_drop_share'], asym))
    gate('D0.06', 'D1 sink-valve computed (zero allowed but recorded)',
         'n_sink_valve_global' in d1r and d1r['n_sink_valve_global'] >= 0,
         'global=%d interface=%d' % (len(sink_valve), len(sv_if)))
    gate('D0.07', 'D1 single-exit / lane-drop produced',
         np.isfinite(d1r['valve_single_exit_share']) and np.isfinite(d1r['valve_lane_drop_share']),
         'single_exit=%.4f lane_drop=%.4f' % (d1r['valve_single_exit_share'], d1r['valve_lane_drop_share']))

    # ---- D2 storage ----------------------------------------------------
    nodelist = list(nodes)
    nidx = {x: k for k, x in enumerate(nodelist)}
    stor = np.zeros(len(nodelist)); inf = np.zeros(len(nodelist))
    for k, x in enumerate(nodelist):
        outs = outb.get(x, []); ins = inb.get(x, [])
        stor[k] = sum(ln[i] * lanes[i] / CELL for i in outs)
        inf[k] = sum(cap[i] / 3600.0 for i in ins)
    fill = np.where(inf > 0, stor / inf, np.nan)
    if_mask = np.array([x in if_nodes for x in nodelist])
    fill_if = fill[if_mask & np.isfinite(fill)]
    fill_all = fill[np.isfinite(fill)]
    d2r = {'n_nodes_interface': int(if_mask.sum()),
           'fill_time_s_interface': {'p10': float(np.percentile(fill_if, 10)), 'p25': float(np.percentile(fill_if, 25)),
                                     'median': float(np.median(fill_if)), 'p75': float(np.percentile(fill_if, 75)),
                                     'p90': float(np.percentile(fill_if, 90))},
           'fill_time_s_all': {'median': float(np.median(fill_all)),
                               'share_lt_REQ': float((fill_all < REQ_FILL_S).mean())},
           'share_fill_lt_REQ_interface': float((fill_if < REQ_FILL_S).mean()),
           'cap_per_lane': {}, 'ndistinct_cap_per_lane': {}, 'cap_ratio_ref': {},
           'link_storage_veh_median': {}}
    for c in CLASSES:
        m = (cls == c)
        r = np.round(cap[m] / np.maximum(lanes[m], 1), 6)
        u = np.unique(r)
        d2r['cap_per_lane'][c] = float(np.median(r))
        d2r['ndistinct_cap_per_lane'][c] = int(len(u))
        d2r['cap_ratio_ref'][c] = float(np.median(r) / LANE_CAP_REF)
        d2r['link_storage_veh_median'][c] = float(np.median(ln[m] * lanes[m] / CELL))
    cap_det = all(v == 1 for v in d2r['ndistinct_cap_per_lane'].values())
    log('D2 storage: INTERFACE fill median=%.1f s  share<%.0fs=%.3f | ALL median=%.1f s share<%.0fs=%.3f'
        % (d2r['fill_time_s_interface']['median'], REQ_FILL_S, d2r['share_fill_lt_REQ_interface'],
           d2r['fill_time_s_all']['median'], REQ_FILL_S, d2r['fill_time_s_all']['share_lt_REQ']))
    log('D2 cap/lane: %s' % {c: int(d2r['cap_per_lane'][c]) for c in CLASSES})
    log('D2 ndistinct(cap/lane): %s  => CAP_DETERMINISTIC=%s' % (d2r['ndistinct_cap_per_lane'], cap_det))
    gate('D0.08', 'D2 fill_time produced', len(fill_if) > 0,
         'iface_nodes=%d median=%.1fs' % (len(fill_if), d2r['fill_time_s_interface']['median']))
    gate('D0.09', 'D2 deterministic-capacity test produced',
         all(c in d2r['ndistinct_cap_per_lane'] for c in CLASSES),
         'ndistinct=%s' % d2r['ndistinct_cap_per_lane'])

    # ---- D3 coupling ---------------------------------------------------
    d3r = {}
    for tag in ('V1', 'KW'):
        dh = D[tag]['delay_h']; tt_ = float(dh.sum())
        if tt_ <= 0:
            d3r[tag] = {}; continue
        rec = {'total_delay_h': tt_,
               'delay_share_up_le_DIF': float(dh[d_up <= D_IF].sum() / tt_),
               'delay_share_up_gt_DIF': float(dh[d_up > D_IF].sum() / tt_),
               'delay_share_down_le_DIF': float(dh[d_down <= D_IF].sum() / tt_),
               'delay_share_down_gt_DIF': float(dh[d_down > D_IF].sum() / tt_),
               'delay_weighted_d_up': float((dh * d_up).sum() / tt_),
               'delay_weighted_d_down': float((dh * d_down).sum() / tt_),
               'delay_weighted_d_up_by_class': {},
               'delay_weighted_d_up_share_le_DIF_by_class': {}}
        for c in CLASSES:
            m = (cls == c); s = float(dh[m].sum())
            rec['delay_weighted_d_up_by_class'][c] = float((dh[m] * d_up[m]).sum() / s) if s > 0 else float('nan')
            rec['delay_weighted_d_up_share_le_DIF_by_class'][c] = float(dh[m & (d_up <= D_IF)].sum() / s) if s > 0 else float('nan')
        d3r[tag] = rec
        log('D3 [%s] delay-weighted d_up=%.2f hops ; share(d_up<=%d)=%.4f ; share(d_up>%d)=%.4f'
            % (tag, rec['delay_weighted_d_up'], D_IF, rec['delay_share_up_le_DIF'], D_IF, rec['delay_share_up_gt_DIF']))
    # sensitivity on V1
    d3sens = {}
    for d in D_IF_SENS:
        d3sens[str(d)] = float(d1[d_up <= d].sum() / tot1)
    log('D3 sensitivity (V1 share d_up<=D): %s' % {k: round(v, 4) for k, v in d3sens.items()})
    gate('D0.10', 'D3 delay-weighted d_up distribution produced',
         'V1' in d3r and 'delay_share_up_le_DIF' in d3r['V1'], 'share_le=%s' % d3r['V1'].get('delay_share_up_le_DIF'))
    gate('D0.11', 'D3 delay-weighted d_down distribution produced',
         'V1' in d3r and 'delay_share_down_le_DIF' in d3r['V1'], 'share_le=%s' % d3r['V1'].get('delay_share_down_le_DIF'))

    # ==================================================================
    # SUPPLEMENTARY (NOT pre-registered; cannot alter the frozen verdict)
    # Motivation: hop counts are inflated by hyper-fragmentation (median link
    # ~11 m).  Translate hops -> physical metres, and re-test capacity
    # determinism at (highway x lanes) resolution instead of merged class.
    # ==================================================================
    sup_gates = []
    def sgate(gid, desc, ok, detail):
        sup_gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

    def dijkstra(expand):
        d = np.full(n, math.inf, dtype=float); pq = []
        for i in np.where(MW)[0]:
            d[i] = 0.0; heapq.heappush(pq, (0.0, int(i)))
        while pq:
            du, k = heapq.heappop(pq)
            if du > d[k] + 1e-9: continue
            for j, w in expand(int(k)):
                nd = du + w
                if nd < d[j] - 1e-9:
                    d[j] = nd; heapq.heappush(pq, (nd, int(j)))
        return d
    dist_up_m   = dijkstra(lambda k: [(int(i), float(ln[i])) for i in outb.get(to[k], [])])
    dist_down_m = dijkstra(lambda k: [(int(j), float(ln[j])) for j in inb.get(frm[k], [])])
    fin_u = np.isfinite(dist_up_m)
    log('SUP dist_up_m: finite=%.3f%%  median=%.0f m  p90=%.0f m'
        % (100 * fin_u.mean(), np.median(dist_up_m[fin_u]), np.percentile(dist_up_m[fin_u], 90)))
    sgate('S0.01', 'physical upstream distance to mainline finite for >=99% links',
          fin_u.mean() >= 0.99, 'finite=%.4f median=%.0f m' % (fin_u.mean(), np.median(dist_up_m[fin_u])))

    sup_phys = {}
    for tag in ('V1', 'KW'):
        dh = D[tag]['delay_h']; tt_ = float(dh.sum())
        if tt_ <= 0: continue
        msk = np.isfinite(dist_up_m)
        sup_phys[tag] = {
            'delay_weighted_dist_up_m': float((dh[msk] * dist_up_m[msk]).sum() / dh[msk].sum()),
            'delay_share_dist_up_le_300m': float(dh[msk & (dist_up_m <= 300)].sum() / tt_),
            'delay_share_dist_up_le_1000m': float(dh[msk & (dist_up_m <= 1000)].sum() / tt_),
            'delay_share_dist_up_gt_1000m': float(dh[msk & (dist_up_m > 1000)].sum() / tt_),
            'median_dist_up_m_of_delay_bearing_links': float(np.median(dist_up_m[dh > 0])) if (dh > 0).any() else float('nan'),
        }
        log('SUP [%s] delay-weighted upstream distance to mainline = %.0f m ; share<=300m=%.4f ; share<=1000m=%.4f'
            % (tag, sup_phys[tag]['delay_weighted_dist_up_m'],
               sup_phys[tag]['delay_share_dist_up_le_300m'], sup_phys[tag]['delay_share_dist_up_le_1000m']))

    capdet_hw = {}
    for h in np.unique(hw):
        m = (hw == h)
        r = np.round(cap[m] / np.maximum(lanes[m], 1), 6)
        capdet_hw[h] = {'n': int(m.sum()), 'n_distinct_cap_per_lane': int(len(np.unique(r))),
                        'cap_per_lane': float(np.median(r))}
    bad = {k: v for k, v in capdet_hw.items() if v['n_distinct_cap_per_lane'] != 1}
    log('SUP cap determinism by highway: %d highway types, non-deterministic=%s'
        % (len(capdet_hw), bad if bad else 'NONE (all lookup-assigned)'))
    sgate('S0.02', 'capacity is a pure (highway x lanes) lookup at finest resolution',
          len(bad) == 0, 'highway_types=%d violations=%d' % (len(capdet_hw), len(bad)))

    # ---- candidate prior reproducibility -------------------------------
    l2u = np.load(L2U, allow_pickle=True)
    with io.open(C0CSV, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    cand = [u['unit_id'] for u in rows if u['is_candidate'] == '1']
    log('candidate units = %d (expect 5490)' % len(cand))
    gate('D0.12', 'candidate prior reproduced (5490)', len(cand) == 5490, 'candidates=%d' % len(cand))

    # ---- CTE naming gate (corrected definition) -------------------------
    cte_mask_hits = int(sum(1 for x in nm if BANNED_MASK in x.upper()))
    cte_links = np.array([x == CTE_NAME for x in nm])
    cte_n = int(cte_links.sum())
    cte_delay_v1 = float(d1[cte_links].sum()); cte_share_v1 = cte_delay_v1 / tot1 if tot1 > 0 else 0.0
    cte_delay_kw = float(D['KW']['delay_h'][cte_links].sum()); tot_kw = float(D['KW']['delay_h'].sum())
    log('CTE: banned-mask("%s") hits=%d ; proper "%s" n=%d  V1 delay=%.2f h (%.4f)  KW delay=%.2f h (%.4f)'
        % (BANNED_MASK, cte_mask_hits, CTE_NAME, cte_n, cte_delay_v1, cte_share_v1,
           cte_delay_kw, cte_delay_kw / tot_kw if tot_kw > 0 else 0))
    gate('D0.13', 'CTE naming correct (proper name 603 links, banned mask == 0)',
         cte_n == CTE_EXPECT_N and cte_mask_hits == 0,
         'proper_n=%d banned_mask_hits=%d' % (cte_n, cte_mask_hits))

    # ---- D4 terminal exposure (descriptive only) ------------------------
    d4r = {'status': 'UNAVAILABLE'}
    try:
        id2i = {s: k for k, s in enumerate(ids)}
        sc = collections.Counter(); ec = collections.Counter()
        n_person = 0; n_trip = 0; term_service = 0
        acts = []
        with gzip.open(POPU, 'rt', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '<person' in line:
                    acts = []
                for m in re.finditer(r'<act[^>]*\blink="([^"]+)"', line):
                    acts.append(m.group(1))
                if '</person>' in line and acts:
                    a = id2i.get(acts[0]); b = id2i.get(acts[-1])
                    if a is not None and b is not None:
                        ca, cb = cls[a], cls[b]
                        sc[ca] += 1; ec[cb] += 1; n_trip += 1
                        if ca == 'service' or cb == 'service': term_service += 1
                    n_person += 1
                    acts = []
        tot_t = max(n_trip, 1)
        d4r = {'status': 'OK', 'n_person': n_person, 'n_trip_mapped': n_trip,
               'start_link_class_share': {c: sc[c] / tot_t for c in CLASSES},
               'end_link_class_share': {c: ec[c] / tot_t for c in CLASSES},
               'terminal_is_service_share': term_service / tot_t}
        log('D4 terminal: trips=%d  start service=%.4f  end service=%.4f  either=%.4f (km_share service=%.4f)'
            % (n_trip, d4r['start_link_class_share']['service'], d4r['end_link_class_share']['service'],
               d4r['terminal_is_service_share'], base_all['by_class']['service']['km_share']))
    except Exception as e:
        log('D4 UNAVAILABLE: %r' % e)
    gate('D0.14', 'D4 terminal exposure (or UNAVAILABLE)',
         d4r['status'] in ('OK', 'UNAVAILABLE'), 'status=%s' % d4r['status'])

    # ---- VERDICT --------------------------------------------------------
    share_if = d3r['V1']['delay_share_up_le_DIF']
    share_off = d3r['V1']['delay_share_up_gt_DIF']
    thin_share = d2r['share_fill_lt_REQ_interface']
    if share_if >= 0.50 and thin_share >= THIN_THR:
        v = 'ACCESS_INTERFACE_DELAY_DOMINANT__THIN_STORAGE'
    elif share_off >= 0.90:
        v = 'DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED'
    elif share_if >= 0.50 and thin_share < THIN_THR:
        v = 'ACCESS_INTERFACE_DELAY_DOMINANT__STORAGE_NOT_THIN__LOOK_ELSEWHERE'
    else:
        v = 'INDETERMINATE'
    flags = {
        'VALVE_PRESENT': d1r['sink_valve_share_interface'] >= VALVE_THR,
        'THIN_STORAGE': thin_share >= THIN_THR,
        'CAP_DETERMINISTIC': bool(cap_det),
        'COUPLING_ABSENT': share_off >= 0.90,
        'BASE_RATE_ARTIFACT': bool(base_all['by_class']['service']['ratio_delay_over_km'] <= RATIO_BASE
                                   or base_if['by_class']['service']['ratio_delay_over_km'] <= RATIO_BASE),
    }
    log('VERDICT = %s' % v)
    log('FLAGS   = %s' % flags)
    # NOTE: the pre-registration (PREREG §5) lists 15 gates and does NOT include a
    # "verdict determined" gate.  The verdict is therefore recorded as a top-level
    # field (with the matched branch), NOT as a gate, so the gate list matches the
    # frozen pre-registration exactly.  Branch order is the frozen §6 order.
    if v == 'ACCESS_INTERFACE_DELAY_DOMINANT__THIN_STORAGE':
        verdict_rule = 'branch1: share_if=%.4f>=0.50 AND thin=%.4f>=%.2f' % (share_if, thin_share, THIN_THR)
    elif v == 'DELAY_TRAP_OFF_MAINLINE_BY_CONSTRUCTION__BASE_RATE_DOMINATED':
        verdict_rule = 'branch2: share_off=%.4f>=0.90' % share_off
    elif v == 'ACCESS_INTERFACE_DELAY_DOMINANT__STORAGE_NOT_THIN__LOOK_ELSEWHERE':
        verdict_rule = 'branch3: share_if=%.4f>=0.50 AND thin=%.4f<%.2f' % (share_if, thin_share, THIN_THR)
    else:
        verdict_rule = 'fallthrough: share_if=%.4f share_off=%.4f thin=%.4f' % (share_if, share_off, thin_share)
    log('VERDICT_RULE = %s' % verdict_rule)

    # ---- write ----------------------------------------------------------
    json.dump({'prereg_sha256': PREREG_SHA, 'prereg_sha256_recomputed': h,
               'prereg_match': bool(h == PREREG_SHA),
               'constants': {'CELL': CELL, 'D_IF': D_IF, 'REQ_FILL_S': REQ_FILL_S,
                             'LANE_CAP_REF': LANE_CAP_REF, 'THIN_THR': THIN_THR,
                             'VALVE_THR': VALVE_THR, 'RATIO_BASE': RATIO_BASE},
               'verdict': v, 'verdict_rule': verdict_rule, 'flags': flags,
               'SUPPLEMENTARY': {'phys_dist': sup_phys, 'cap_det_by_highway': capdet_hw},
               'base_rate_all': base_all, 'base_rate_interface': base_if,
               'D1_valve': d1r, 'D2_storage': d2r, 'D3_coupling': d3r, 'D3_sensitivity': d3sens,
               'D4_terminal': d4r, 'CTE': {'proper_name': CTE_NAME, 'n_links': cte_n,
                                           'banned_mask_hits': cte_mask_hits,
                                           'V1_delay_h': cte_delay_v1, 'V1_share': cte_share_v1,
                                           'KW_delay_h': cte_delay_kw,
                                           'KW_share': cte_delay_kw / tot_kw if tot_kw > 0 else 0.0},
               'interface': {'n_links': int(INTERFACE.sum()), 'n_if_up': int(IF_UP.sum()),
                             'n_if_down': int(IF_DOWN.sum()), 'n_nodes': len(if_nodes)},
               'runtime_sec': round(time.time() - t0, 1)},
              open(OUT + '/d0_audit_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    with open(OUT + '/d0_base_rate.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['scope', 'class', 'km', 'km_share', 'links', 'link_share',
                                       'delay_h', 'delay_share', 'ratio_delay_over_km'])
        for sc_, bt in (('ALL', base_all), ('INTERFACE', base_if)):
            for c in CLASSES:
                r = bt['by_class'][c]
                w.writerow([sc_, c, '%.3f' % r['km'], '%.6f' % r['km_share'], r['links'],
                            '%.6f' % r['link_share'], '%.4f' % r['delay_h'],
                            '%.6f' % r['delay_share'], '%.4f' % r['ratio_delay_over_km']])
    with open(OUT + '/d0_d1_valve.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        for k, val in d1r.items(): w.writerow([k, val])
    with open(OUT + '/d0_d2_storage.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['class', 'cap_per_lane', 'ndistinct_cap_per_lane',
                                       'cap_ratio_ref', 'link_storage_veh_median'])
        for c in CLASSES:
            w.writerow([c, '%.1f' % d2r['cap_per_lane'][c], d2r['ndistinct_cap_per_lane'][c],
                        '%.4f' % d2r['cap_ratio_ref'][c], '%.3f' % d2r['link_storage_veh_median'][c]])
        for k in ('n_nodes_interface', 'share_fill_lt_REQ_interface'):
            w.writerow([k, d2r[k]])
        for k, val in d2r['fill_time_s_interface'].items():
            w.writerow(['fill_time_s_interface_' + k, '%.4f' % val])
    with open(OUT + '/d0_d3_coupling.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['run', 'metric', 'value'])
        for tag in ('V1', 'KW'):
            for k, val in d3r.get(tag, {}).items():
                if isinstance(val, dict): continue
                w.writerow([tag, k, '%.6f' % val])
        for k, val in d3sens.items(): w.writerow(['V1', 'share_up_le_' + k, '%.6f' % val])
    with open(OUT + '/d0_sup_phys.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['run', 'metric', 'value'])
        for tag, d in sup_phys.items():
            for k, val in d.items(): w.writerow([tag, k, '%.4f' % val])
        for h, d in capdet_hw.items():
            w.writerow(['cap_det_by_highway', h, '%d/%d' % (d['n_distinct_cap_per_lane'], d['n'])])
    with open(OUT + '/d0_d4_terminal.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['class', 'start_share', 'end_share'])
        if d4r['status'] == 'OK':
            for c in CLASSES:
                w.writerow([c, '%.6f' % d4r['start_link_class_share'][c], '%.6f' % d4r['end_link_class_share'][c]])
            w.writerow(['TERMINAL_IS_SERVICE', '%.6f' % d4r['terminal_is_service_share'], ''])
        else:
            w.writerow(['UNAVAILABLE', '', ''])
    with open(OUT + '/d0_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])

    fa = snap(FROZEN)
    changed = sum(1 for k in set(fb) | set(fa) if fb.get(k) != fa.get(k))
    gate('D0.15', 'frozen artifacts untouched', changed == 0, 'changed=%d' % changed)
    with open(OUT + '/d0_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])
        for g in sup_gates: w.writerow([g['id'], '[SUPPLEMENTARY] ' + g['desc'], g['pass'], g['detail']])
    npass = sum(1 for g in gates if g['pass'])
    nsup = sum(1 for g in sup_gates if g['pass'])
    log('GATES: %d/%d PASS  (supplementary %d/%d)  runtime %.1f s'
        % (npass, len(gates), nsup, len(sup_gates), time.time() - t0))
    log('VERDICT = %s' % v)
    json.dump({'prereg_sha256': PREREG_SHA, 'gates': gates, 'sup_gates': sup_gates,
               'n_pass': npass, 'n_total': len(gates),
               'sup_n_pass': nsup, 'sup_n_total': len(sup_gates),
               'verdict': v, 'verdict_rule': verdict_rule, 'flags': flags,
               'SUPPLEMENTARY': {'phys_dist': sup_phys, 'cap_det_by_highway': capdet_hw}},
              open(OUT + '/d0_gates.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(OUT + '/_run_d0.log', 'w', encoding='utf-8').write('\n'.join(log_lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())

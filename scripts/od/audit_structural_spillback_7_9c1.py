# -*- coding: utf-8 -*-
"""
Step 7.9C-1 -- Structural Spillback Validation
(ZERO-SIMULATION, READ-ONLY; v1.0 frozen; reports only)

Question (user-frozen):
  Why should the real congestion structure appear on CTE / main expressways and
  their spillback chains, while MATSim absorbs large delays into service /
  connector short segments?

Frozen three chains:  candidate bottleneck -> upstream propagation path -> downstream storage/blocking
Frozen checks: K1 mainline propagatable channel; K2 downstream storage/fill-time;
               K3 service/connector return-breakpoints; K4 ultra-short-link fragmentation.
Discipline: no sim re-run; frozen artifacts untouched; candidates never use W01/KW flow.
"""
import os, io, csv, json, time, math, gc, sys, collections
import numpy as np
import pandas as pd
sys.setrecursionlimit(1000000)

ROOT = r'D:/Luan/2026-05/2_Singapore'
CACHE = ROOT + '/scripts/od/_cache_network_7_9c0.npz'
L2U   = ROOT + '/scripts/od/_cache_link_unit_7_9b1.npz'
C0CSV = ROOT + '/reports/structural_junction_cluster_audit_7_9c0/c0_junction_clusters.csv'
V1_LS = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz'
KW_LS = ROOT + '/matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz'
OUT   = ROOT + '/reports/structural_spillback_7_9c1'
FROZEN_DIRS = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8', ROOT + '/matsim_kw_7_9b1']

# --- frozen constants / pre-registered thresholds ----------------------------
CELL, TIME_STEP, F_CAP = 7.5, 1.0, 1.0
CHAIN_MIN_M      = 300.0     # K1 propagatable mainline channel (m)
CHAIN_SENS       = (500.0, 1000.0)
FILL_BLOCK_S     = 10.0      # K2 downstream fill time (s)
SHORT_M          = 20.0      # K4 ultra-short link (m)
FRAG_LPKM        = 40.0      # K4 fragmentation-heavy (links/km)
PRIOR_CAND       = 80.0
RAMP    = {'motorway_link', 'trunk_link'}
CONNEC  = {'primary_link', 'secondary_link', 'tertiary_link'}
MAINLINE = {'motorway', 'trunk', 'primary'}
CLASSES = ('motorway', 'ramp', 'connector', 'service', 'other')
EXPRESSWAY_NAMES = ['Central Expressway', 'Tampines Expressway', 'Pan-Island Expressway',
                    'Ayer Rajah Expressway', 'Kallang-Paya Lebar Expressway',
                    'East Coast Parkway', 'Seletar Expressway', 'Bukit Timah Expressway',
                    'Marina Coastal Expressway', 'Kranji Expressway', 'West Coast Highway']

log_lines = []; _T0 = time.time()
def log(m):
    log_lines.append(m); print('[%6.1fs] %s' % (time.time() - _T0, m), flush=True)

def esc(x): return str(x).replace('|', r'\|')
def md_table(header, rows):
    o = ['| ' + ' | '.join(esc(h) for h in header) + ' |',
         '|' + '|'.join(['---'] * len(header)) + '|']
    for r in rows: o.append('| ' + ' | '.join(esc(c) for c in r) + ' |')
    return '\n'.join(o)

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
    fb = snap(FROZEN_DIRS)
    log('=== Step 7.9C-1 Structural Spillback Validation -- zero simulation ===')

    # ---------- load ------------------------------------------------------
    z = np.load(CACHE, allow_pickle=True)
    frm = [str(x) for x in z['frm']]; to = [str(x) for x in z['to']]
    ln = z['len_m'].astype(float); fs = z['fs_mps'].astype(float)
    cap = z['cap'].astype(float); lanes = z['lanes'].astype(float)
    hw = np.array([str(x) for x in z['highway']]); nm = np.array([str(x) for x in z['name']])
    ids = np.array([str(x) for x in z['ids']])
    n = len(frm); Lk = ln * 0.001; fs_kmh = fs * 3.6
    tier = np.digitize(fs_kmh, [30, 50, 70, 90]).astype(np.int8)
    cls = np.array(["ramp" if h in ("motorway_link", "trunk_link")
                    else "connector" if h.endswith("_link")
                    else "service" if h == "service"
                    else "motorway" if h in ("motorway", "trunk")
                    else "other" for h in hw])
    HASNAME = np.array([bool(x) and x.lower() not in ('nan', 'none') for x in nm])
    MW = (cls == 'motorway')
    log('network: links=%d km=%.2f  named=%.1f%%  motorway_links=%d (%.1f km)'
        % (n, Lk.sum(), 100 * HASNAME.mean(), MW.sum(), Lk[MW].sum()))
    gate('C1.01', 'network parsed from frozen v1.0 cache (693575 / 15126.5 km)',
         n == 693575 and abs(Lk.sum() - 15126.5) < 5.0, 'links=%d km=%.2f' % (n, Lk.sum()))

    outb = collections.defaultdict(list); inb = collections.defaultdict(list)
    for i in range(n):
        outb[frm[i]].append(i); inb[to[i]].append(i)

    # ---------- chain primitives (same physical road; cycle-safe) ----------
    def chain_fn(pred):
        memo = {}; guard = set()
        def f(i):
            if i in memo: return memo[i]
            if i in guard: return ln[i]
            guard.add(i); best = 0.0
            if HASNAME[i]:
                for j in inb.get(frm[i], []):
                    if pred(j, i):
                        v = f(j)
                        if v > best: best = v
            guard.discard(i); memo[i] = ln[i] + best
            return memo[i]
        return f
    up_name_fn = chain_fn(lambda j, i: HASNAME[j] and nm[j] == nm[i])
    up_main_fn = chain_fn(lambda j, i: HASNAME[j] and nm[j] == nm[i] and MW[j])
    log('computing up_name_m for all links ...')
    up_name_m = np.array([up_name_fn(i) for i in range(n)], dtype=float)
    log('computing up_main_m for motorway links ...')
    up_main_m = np.full(n, np.nan)
    for i in np.where(MW)[0]:
        up_main_m[i] = up_main_fn(i)
    gate('C1.02', 'channel primitives computed (finite)',
         np.isfinite(up_name_m).all() and np.isfinite(up_main_m[MW]).all(),
         'median up_name=%.0f m  median up_main(mw)=%.0f m'
         % (np.median(up_name_m), np.median(up_main_m[MW])))
    gc.collect()

    # ---------- K1 mainline propagatable channel ---------------------------
    mw_len = Lk[MW].sum()
    k1 = {'n_motorway_links': int(MW.sum()), 'motorway_km': float(mw_len),
          'up_main_m_dist': {'min': float(np.nanmin(up_main_m)), 'p25': float(np.nanpercentile(up_main_m, 25)),
                             'median': float(np.nanmedian(up_main_m)), 'p75': float(np.nanpercentile(up_main_m, 75)),
                             'p90': float(np.nanpercentile(up_main_m, 90)), 'max': float(np.nanmax(up_main_m))},
          'share_ge': {}}
    for th in (CHAIN_MIN_M,) + CHAIN_SENS:
        share_links = float((up_main_m[MW] >= th).mean())
        share_len = float(Lk[MW & (up_main_m >= th)].sum() / mw_len)
        k1['share_ge']['%.0f' % th] = {'by_links': share_links, 'by_length': share_len}
    log('K1 mainline channel: median=%.0f m  share_len(>=%.0f m)=%.1f%%  share_len(>=1000)=%.1f%%'
        % (np.nanmedian(up_main_m), CHAIN_MIN_M, 100 * k1['share_ge']['300']['by_length'],
           100 * k1['share_ge']['1000']['by_length']))
    gate('C1.03', 'K1 mainline channel computed', np.isfinite(k1['share_ge']['300']['by_length']),
         'share_len>=300m=%.4f' % k1['share_ge']['300']['by_length'])

    # ---------- K3 return-breakpoints (downstream node has motorway out-edge) --
    ret_comp = np.zeros(n, dtype=bool)
    for i in range(n):
        ret_comp[i] = any(MW[j] for j in outb.get(to[i], []))
    k3 = {'by_class': {}, 'service_or_connector_incompetent_share': None}
    for c in CLASSES:
        m = (cls == c)
        sh = float((~ret_comp[m]).mean())
        k3['by_class'][c] = {'n': int(m.sum()), 'km': float(Lk[m].sum()),
                             'incompetent_share': sh}
    sc = np.isin(cls, ['service', 'connector'])
    k3['service_or_connector_incompetent_share'] = float((~ret_comp[sc]).mean())
    log('K3 return-breakpoints: service∪connector incompetent = %.2f%%  (motorway = %.2f%%)'
        % (100 * k3['service_or_connector_incompetent_share'], 100 * k3['by_class']['motorway']['incompetent_share']))
    gate('C1.04', 'K3 return-breakpoints computed', np.isfinite(k3['service_or_connector_incompetent_share']),
         'svc/conn incompetent=%.4f' % k3['service_or_connector_incompetent_share'])

    # ---------- K4 fragmentation by class ----------------------------------
    k4 = {'by_class': {}}
    for c in CLASSES:
        m = (cls == c)
        k4['by_class'][c] = {'n': int(m.sum()), 'km': float(Lk[m].sum()),
                             'median_len_m': float(np.median(ln[m])),
                             'links_per_km': float(m.sum() / max(Lk[m].sum(), 1e-9)),
                             'share_le_20m': float((ln[m] <= SHORT_M).mean())}
    # named motorway roads
    nmidx = collections.defaultdict(list)
    for i in np.where(MW)[0]:
        if HASNAME[i]: nmidx[nm[i]].append(i)
    k4['motorway_named'] = []
    for k, v in nmidx.items():
        a = np.array(v); km = Lk[a].sum()
        if km >= 3.0:
            k4['motorway_named'].append({'name': k, 'n': int(len(a)), 'km': float(km),
                                         'median_len_m': float(np.median(ln[a])),
                                         'links_per_km': float(len(a) / km),
                                         'share_le_20m': float((ln[a] <= SHORT_M).mean())})
    k4['motorway_named'].sort(key=lambda r: -r['km'])
    frag_heavy = [r for r in k4['motorway_named'] if r['links_per_km'] > FRAG_LPKM]
    k4['n_frag_heavy_motorway_roads'] = len(frag_heavy)
    log('K4 fragmentation: motorway %.1f links/km (med %.1f m) ; service %.1f ; connector %.1f ; frag-heavy mw roads=%d'
        % (k4['by_class']['motorway']['links_per_km'], k4['by_class']['motorway']['median_len_m'],
           k4['by_class']['service']['links_per_km'], k4['by_class']['connector']['links_per_km'], len(frag_heavy)))
    gate('C1.05', 'K4 fragmentation computed', len(k4['motorway_named']) > 0,
         'mw roads=%d frag_heavy=%d' % (len(k4['motorway_named']), len(frag_heavy)))

    # ---------- K2 downstream storage / fill-time at candidate bottlenecks ---
    with io.open(C0CSV, encoding='utf-8-sig', newline='') as f:
        units = list(csv.DictReader(f))
    cand_uids = [u['unit_id'] for u in units if u['is_candidate'] == '1']
    l2u = np.load(L2U, allow_pickle=True)
    link2unit = l2u['link2unit'].astype(np.int64); uid_list = [str(x) for x in l2u['uid_list']]
    uid2i = {u: i for i, u in enumerate(uid_list)}
    prior = l2u['prior'].astype(float)

    def node_feats(x):
        ins = inb.get(x, []); outs = outb.get(x, [])
        if not ins or not outs: return (0.0, 0.0, 0.0, 0.0, 0.0)
        ic = float(sum(cap[i] for i in ins)); oc = float(sum(cap[i] for i in outs))
        f1 = max(0.0, (ic - oc) / oc) if oc > 0 else 0.0
        mil = float(max(lanes[i] for i in ins)); mol = float(min(lanes[i] for i in outs))
        f2 = max(0.0, (mil - mol) / mil) if mil > 0 else 0.0
        f3 = 1.0 if len(set(int(tier[i]) for i in ins + outs)) >= 2 else 0.0
        hws = set(str(hw[i]) for i in ins + outs)
        f4 = 1.0 if (hws & (RAMP | CONNEC)) and (hws & MAINLINE) else 0.0
        stor = float(sum(ln[i] * lanes[i] / CELL for i in outs))
        inf_ts = float(sum(cap[i] / 3600.0 * TIME_STEP * F_CAP for i in ins))
        f5 = max(0.0, 1.0 - stor / inf_ts) if inf_ts > 0 else 0.0
        return (min(f1, 1.0), min(f2, 1.0), f3, f4, f5)

    cand_nodes = []
    on_mainline = 0
    for u in cand_uids:
        ui = uid2i.get(u)
        if ui is None: continue
        ls = np.where(link2unit == ui)[0]
        if ls.size == 0: continue
        if MW[ls].any(): on_mainline += 1
        nds = set()
        for i in ls:
            nds.add(frm[i]); nds.add(to[i])
        best, bs = None, -1.0
        for x in nds:
            s = float(np.mean(node_feats(x)[:4]))
            if s > bs: bs, best = s, x
        if best is None: continue
        inls = inb.get(best, []); outls = outb.get(best, [])
        down_stor = float(sum(ln[i] * lanes[i] / CELL for i in outls))
        up_stor   = float(sum(ln[i] * lanes[i] / CELL for i in inls))
        inf_rate  = float(sum(cap[i] / 3600.0 for i in inls))       # veh/s
        fill_s    = down_stor / inf_rate if inf_rate > 0 else float('inf')
        cand_nodes.append({'unit_id': u, 'node': best, 'score': bs,
                           'down_storage_veh': down_stor, 'up_storage_veh': up_stor,
                           'inflow_veh_s': inf_rate, 'fill_time_s': fill_s,
                           'n_in': len(inls), 'n_out': len(outls)})
    fill = np.array([c['fill_time_s'] for c in cand_nodes if np.isfinite(c['fill_time_s'])])
    k2 = {'n_candidate_units': len(cand_uids), 'n_candidate_nodes': len(cand_nodes),
          'candidate_units_with_motorway_link': int(on_mainline),
          'candidate_units_with_motorway_share': float(on_mainline / max(len(cand_uids), 1)),
          'fill_time_s': {'p10': float(np.percentile(fill, 10)), 'p25': float(np.percentile(fill, 25)),
                          'median': float(np.median(fill)), 'p75': float(np.percentile(fill, 75)),
                          'p90': float(np.percentile(fill, 90)), 'max': float(fill.max())},
          'share_fill_lt_thr': float((fill < FILL_BLOCK_S).mean()),
          'median_down_storage_veh': float(np.median([c['down_storage_veh'] for c in cand_nodes])),
          'median_up_storage_veh': float(np.median([c['up_storage_veh'] for c in cand_nodes]))}
    log('K2 candidate bottlenecks: n=%d  with_motorway_link=%d (%.1f%%)  fill_time median=%.0f s  share<%.0fs=%.1f%%'
        % (len(cand_nodes), on_mainline, 100 * k2['candidate_units_with_motorway_share'],
           k2['fill_time_s']['median'], FILL_BLOCK_S, 100 * k2['share_fill_lt_thr']))
    gate('C1.06', 'K2 candidate-bottleneck storage computed', len(cand_nodes) > 0,
         'n=%d median_fill=%.1fs' % (len(cand_nodes), k2['fill_time_s']['median']))
    gate('C1.07', 'K2 candidate prior decoupled from flow (reproduces 5490)',
         len(cand_uids) == 5490, 'candidates=%d' % len(cand_uids))

    # ---------- reconciliation: delay by class / channel / corridor ----------
    def delays(path):
        vol, tt, matched = read_ls(path, ids)
        with np.errstate(divide='ignore', invalid='ignore'):
            ff = np.where(fs > 0, ln / fs, np.nan)
            quant = np.where(ff > 0, np.ceil(ff) / ff, np.nan)
            excess = np.where(np.isfinite(tt) & np.isfinite(ff), tt / ff - quant, 0.0)
        delay_h = np.where(np.isfinite(tt) & np.isfinite(ff),
                           np.maximum(tt - np.ceil(ff), 0.0) * vol, 0.0) / 3600.0
        return {'vol': vol, 'tt': tt, 'excess': excess, 'delay_h': delay_h,
                'matched': matched, 'total_delay_h': float(delay_h.sum())}
    rec = {}
    for tag, p in (('V1', V1_LS), ('KW', KW_LS)):
        m = delays(p)
        by_class = {c: float(m['delay_h'][cls == c].sum()) for c in CLASSES}
        tot = m['total_delay_h']
        rec[tag] = {'total_delay_h': tot, 'matched': m['matched'],
                    'delay_by_class_h': by_class,
                    'delay_by_class_share': {c: (by_class[c] / tot if tot > 0 else 0.0) for c in CLASSES},
                    'delay_share_return_incompetent': float(m['delay_h'][~ret_comp].sum() / tot) if tot > 0 else 0.0,
                    'delay_weighted_up_name_m': float((m['delay_h'] * up_name_m).sum() / m['delay_h'].sum())
                    if m['delay_h'].sum() > 0 else float('nan'),
                    'delay_weighted_up_name_m_by_class': {
                        c: (float((m['delay_h'][cls == c] * up_name_m[cls == c]).sum() / m['delay_h'][cls == c].sum())
                            if m['delay_h'][cls == c].sum() > 0 else float('nan')) for c in CLASSES}}
        # corridor (proper names)
        corr = {}
        for name in EXPRESSWAY_NAMES:
            mk = np.array([x == name for x in nm])
            if mk.any():
                corr[name] = {'n': int(mk.sum()), 'km': float(Lk[mk].sum()),
                              'delay_h': float(m['delay_h'][mk].sum()),
                              'delay_share': float(m['delay_h'][mk].sum() / tot) if tot > 0 else 0.0}
        rec[tag]['corridors'] = corr
        log('  [%s] total delay=%.1f h ; by class %s' % (tag, tot,
            {c: round(100 * rec[tag]['delay_by_class_share'][c], 1) for c in CLASSES}))
    gate('C1.08', 'V1 delay recomputed; v1.0 class shares available',
         rec['V1']['total_delay_h'] > 0, 'V1 total=%.1f h' % rec['V1']['total_delay_h'])
    gate('C1.09', 'KW delay recomputed',
         rec['KW']['total_delay_h'] > 0, 'KW total=%.1f h' % rec['KW']['total_delay_h'])

    # ---------- VERDICT ----------------------------------------------------
    k1_ok = k1['share_ge']['300']['by_length'] >= 0.80      # channel intact
    k1_broken = k1['share_ge']['300']['by_length'] < 0.50
    k4_broken = len(frag_heavy) > 0
    k3_ok = k3['service_or_connector_incompetent_share'] >= 0.90
    delay_off_mainline = rec['V1']['delay_by_class_share']['motorway'] < 0.05
    if (k1_broken or k4_broken):
        v = 'SPILLBACK_CHANNEL_BLOCKED_BY_NETWORK_REPRESENTATION'
    elif k1_ok and k3_ok and delay_off_mainline:
        v = 'SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE'
    else:
        v = 'INDETERMINATE'
    log('VERDICT = %s' % v)
    gate('C1.10', 'verdict determined', v in (
        'SPILLBACK_CHANNEL_BLOCKED_BY_NETWORK_REPRESENTATION',
        'SPILLBACK_CHANNEL_INTACT__DELAY_TRAPPED_OFF_MAINLINE', 'INDETERMINATE'),
        'verdict=%s (K1_intact=%s K1_broken=%s K4_broken=%s K3_ok=%s delay_off_mw=%s)'
        % (v, k1_ok, k1_broken, k4_broken, k3_ok, delay_off_mainline))

    # ---------- write outputs ---------------------------------------------
    json.dump({'prereg': {'CHAIN_MIN_M': CHAIN_MIN_M, 'FILL_BLOCK_S': FILL_BLOCK_S,
                          'SHORT_M': SHORT_M, 'FRAG_LPKM': FRAG_LPKM, 'PRIOR_CAND': PRIOR_CAND},
               'verdict': v, 'K1': k1, 'K2': k2, 'K3': k3, 'K4': k4,
               'reconciliation': rec, 'runtime_sec': round(time.time() - t0, 1)},
              open(OUT + '/c1_audit_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    with open(OUT + '/c1_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])
    with open(OUT + '/c1_k1_channel.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['threshold_m', 'share_by_links', 'share_by_length'])
        for th, d in k1['share_ge'].items(): w.writerow([th, '%.6f' % d['by_links'], '%.6f' % d['by_length']])
    with open(OUT + '/c1_k2_candidate_storage.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['unit_id', 'node', 'score', 'down_storage_veh', 'up_storage_veh',
                                       'inflow_veh_s', 'fill_time_s', 'n_in', 'n_out'])
        for c in cand_nodes:
            w.writerow([c['unit_id'], c['node'], '%.4f' % c['score'], '%.3f' % c['down_storage_veh'],
                        '%.3f' % c['up_storage_veh'], '%.4f' % c['inflow_veh_s'], '%.2f' % c['fill_time_s'],
                        c['n_in'], c['n_out']])
    with open(OUT + '/c1_k3_breakpoints.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['class', 'n', 'km', 'incompetent_share'])
        for c in CLASSES:
            d = k3['by_class'][c]; w.writerow([c, d['n'], '%.3f' % d['km'], '%.6f' % d['incompetent_share']])
    with open(OUT + '/c1_k4_fragmentation.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['class', 'n', 'km', 'median_len_m', 'links_per_km', 'share_le_20m'])
        for c in CLASSES:
            d = k4['by_class'][c]; w.writerow([c, d['n'], '%.3f' % d['km'], '%.1f' % d['median_len_m'],
                                               '%.2f' % d['links_per_km'], '%.4f' % d['share_le_20m']])
    with open(OUT + '/c1_corridor_delay.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['corridor', 'n', 'km', 'V1_delay_h', 'V1_share', 'KW_delay_h', 'KW_share'])
        for name in EXPRESSWAY_NAMES:
            if name in rec['V1']['corridors']:
                a = rec['V1']['corridors'][name]; b = rec['KW']['corridors'].get(name, {})
                w.writerow([name, a['n'], '%.3f' % a['km'], '%.3f' % a['delay_h'], '%.5f' % a['delay_share'],
                            '%.3f' % b.get('delay_h', 0), '%.5f' % b.get('delay_share', 0)])
    json.dump({'V1': {c: rec['V1']['delay_by_class_share'][c] for c in CLASSES},
               'KW': {c: rec['KW']['delay_by_class_share'][c] for c in CLASSES},
               'V1_weighted_channel_m': rec['V1']['delay_weighted_up_name_m'],
               'KW_weighted_channel_m': rec['KW']['delay_weighted_up_name_m'],
               'V1_return_incompetent_share': rec['V1']['delay_share_return_incompetent'],
               'KW_return_incompetent_share': rec['KW']['delay_share_return_incompetent']},
              open(OUT + '/c1_reconciliation.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    fa = snap(FROZEN_DIRS)
    changed = sum(1 for k in set(fb) | set(fa) if fb.get(k) != fa.get(k))
    gate('C1.11', 'frozen artifacts untouched', changed == 0, 'changed=%d' % changed)
    with open(OUT + '/c1_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])
    npass = sum(1 for g in gates if g['pass'])
    log('GATES: %d/%d PASS  (runtime %.1f s)' % (npass, len(gates), time.time() - t0))
    log('VERDICT = %s' % v)
    json.dump({'gates': gates, 'n_pass': npass, 'n_total': len(gates), 'verdict': v},
              open(OUT + '/c1_gates.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    # persist for report writer
    json.dump({'k1': k1, 'k2': k2, 'k3': k3, 'k4': k4, 'rec': rec, 'verdict': v,
               'gates': gates, 'npass': npass}, open(OUT + '/_c1_state.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())

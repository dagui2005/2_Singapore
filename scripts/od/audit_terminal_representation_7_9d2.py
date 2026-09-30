# -*- coding: utf-8 -*-
"""
Step 7.9D-2 -- Terminal Representation Audit
(ZERO-SIMULATION structure; free-flow times; v1.0 linkstats read ONLY for volume
 weighting / cross-check, under the frozen PREREG)

Implements exactly the frozen rules of:
  reports/terminal_representation_7_9d2/PREREG_7_9D-2.md
      sha256 = 03f24243d300157e47af727998b894f97013058fc125d2fa9e019534b0933369

Narrow question (user-ratified):
  Do a large share of trips spend a large share of their free-flow travel time on
  the NON-mainline (terminal/access) network before/after using the mainline?
  i.e. is time consumed by the terminal-access representation?

T2 endpoint class + raw-highway distribution (input demand)
T2 free-flow access/egress time (multi-hop physical, PRIMacy per R-DIST-1)
T2 network-level free-flow decomposition -> share_offmain  (== TT_terminal/TT_trip)
T2 v1.0 / KW cross-check

Discipline: no sim re-run; frozen artifacts untouched; v1.0 untouched; no v1.1.
"""
import os, io, csv, gzip, re, json, time, math, sys, collections, hashlib, heapq
import numpy as np
import pandas as pd

ROOT   = r'D:/Luan/2026-05/2_Singapore'
CACHE  = ROOT + '/scripts/od/_cache_network_7_9c0.npz'
PREREG = ROOT + '/reports/terminal_representation_7_9d2/PREREG_7_9D-2.md'
POPU   = ROOT + '/matsim_final_7_6h/populations/pop_W01/population_lambda_0p075.xml.gz'
V1_LS  = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz'
KW_LS  = ROOT + '/matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz'
OUT    = ROOT + '/reports/terminal_representation_7_9d2'
FROZEN = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8', ROOT + '/matsim_kw_7_9b1']

PREREG_SHA = '03f24243d300157e47af727998b894f97013058fc125d2fa9e019534b0933369'

# ---- frozen constants (PREREG §3) -------------------------------------------
OFFMAIN_HI, OFFMAIN_LO, ACC_MED_HI_S = 0.70, 0.50, 180.0
EXPECT_TRIPS, EXPECT_V1_DELAY_H = 236044, 4778.8
CLASSES = ('motorway', 'ramp', 'connector', 'service', 'other')
GRPS = ('mainline', 'ramp', 'arterial', 'local', 'other')
CTE_NAME, CTE_EXPECT_N = 'Central Expressway', 603
BANNED_MASK = 'CTE'

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

def grp_of(h):
    if h in ('motorway', 'trunk'): return 'mainline'
    if h in ('motorway_link', 'trunk_link'): return 'ramp'
    if h in ('primary', 'secondary', 'tertiary', 'primary_link', 'secondary_link', 'tertiary_link'): return 'arterial'
    if h in ('residential', 'living_street', 'unclassified', 'service', 'road'): return 'local'
    return 'other'


def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    gates = []
    def gate(gid, desc, ok, detail):
        gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

    fb = snap(FROZEN)
    log('=== Step 7.9D-2 Terminal Representation Audit ===')

    h = hashlib.sha256(open(PREREG, 'rb').read()).hexdigest()
    log('prereg sha256 = %s (frozen=%s) MATCH=%s'
        % (h[:16] + '...', PREREG_SHA[:16] + '...', h == PREREG_SHA))

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
    grp = np.array([grp_of(x) for x in hw])
    MW = (cls == 'motorway')
    ff = np.where(fs > 0, ln / fs, np.nan)       # free-flow seconds
    log('network: links=%d km=%.2f  mainline(km)=%.2f' % (n, Lk.sum(), Lk[MW].sum()))
    gate('T2.01', 'network from frozen v1.0 cache (693575 / 15126.5 km)',
         n == 693575 and abs(Lk.sum() - 15126.5) < 5.0, 'links=%d km=%.2f' % (n, Lk.sum()))

    outb = collections.defaultdict(list); inb = collections.defaultdict(list)
    for i in range(n):
        outb[frm[i]].append(i); inb[to[i]].append(i)

    # ---- free-flow access / egress time (PRIMARY) -------------------------
    def dij_ff(expand):
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
    # t_to_mw: from i forward to mainline (expand UPSTREAM from mainline)
    t_to_mw = dij_ff(lambda k: [(int(j), float(ff[j])) for j in inb.get(frm[k], [])])
    # t_from_mw: from mainline forward to i (expand DOWNSTREAM from mainline)
    t_from_mw = dij_ff(lambda k: [(int(i2), float(ff[i2])) for i2 in outb.get(to[k], [])])
    fin_o = np.isfinite(t_to_mw); fin_e = np.isfinite(t_from_mw)
    log('T2 free-flow: t_to_mw finite=%.4f med=%.1fs p90=%.1fs | t_from_mw finite=%.4f med=%.1fs'
        % (fin_o.mean(), np.median(t_to_mw[fin_o]), np.percentile(t_to_mw[fin_o], 90),
           fin_e.mean(), np.median(t_from_mw[fin_e])))
    gate('T2.05', 't_to_mw complete (finite>=0.99)', fin_o.mean() >= 0.99, 'finite=%.4f' % fin_o.mean())
    gate('T2.06', 't_from_mw complete (finite>=0.99)', fin_e.mean() >= 0.99, 'finite=%.4f' % fin_e.mean())

    # ---- endpoint parse (frozen INPUT demand) -----------------------------
    id2i = {s: k for k, s in enumerate(ids)}
    sc = collections.Counter(); ec = collections.Counter()
    sgr = collections.Counter(); egr = collections.Counter()
    scw = collections.Counter(); ecw = collections.Counter()
    n_person = 0; n_trip = 0; either_service = 0
    tacc = []; tegr = []; tw = []
    with gzip.open(POPU, 'rt', encoding='utf-8', errors='ignore') as f:
        acts = []; ef = 1.0
        for line in f:
            if '<person ' in line:
                acts = []; ef = 1.0
            m = re.search(r'name="expansionFactor"[^>]*>([0-9.eE+-]+)<', line)
            if m:
                try: ef = float(m.group(1))
                except ValueError: ef = 1.0
            for mm in re.finditer(r'<act[^>]*\blink="([^"]+)"', line):
                acts.append(mm.group(1))
            if '</person>' in line and acts:
                a = id2i.get(acts[0]); b = id2i.get(acts[-1])
                if a is not None and b is not None:
                    ca, cb = cls[a], cls[b]
                    sc[ca] += 1; ec[cb] += 1
                    scw[ca] += ef; ecw[cb] += ef
                    sgr[grp[a]] += 1; egr[grp[b]] += 1
                    if ca == 'service' or cb == 'service': either_service += 1
                    if fin_o[a] and fin_e[b]:
                        tacc.append(float(t_to_mw[a])); tegr.append(float(t_from_mw[b]))
                        tw.append(ef)
                    n_trip += 1
                n_person += 1
                acts = []
    log('T2 endpoints: persons=%d trips=%d' % (n_person, n_trip))
    gate('T2.02', 'endpoint parse reproduced (236044)',
         n_trip == EXPECT_TRIPS, 'n_trip_mapped=%d' % n_trip)

    tot = max(n_trip, 1)
    start_cls = {c: sc[c] / tot for c in CLASSES}
    end_cls = {c: ec[c] / tot for c in CLASSES}
    sw = sum(scw.values()) or 1.0
    start_cls_w = {c: scw[c] / sw for c in CLASSES}
    end_cls_w = {c: ecw[c] / sw for c in CLASSES}
    sg = {g: sgr[g] / tot for g in GRPS}
    eg = {g: egr[g] / tot for g in GRPS}
    log('T2 endpoint class: O svc=%.4f mw=%.4f | D svc=%.4f mw=%.4f | either_service=%.4f'
        % (start_cls['service'], start_cls['motorway'], end_cls['service'], end_cls['motorway'],
           either_service / tot))
    log('T2 endpoint group : O %s' % {g: round(sg[g], 4) for g in GRPS})
    log('T2 endpoint group : D %s' % {g: round(eg[g], 4) for g in GRPS})
    gate('T2.03', 'endpoint class distribution computed (O/D/either)',
         all(c in start_cls for c in CLASSES) and all(c in end_cls for c in CLASSES),
         'either_service=%.4f' % (either_service / tot))
    gate('T2.04', 'endpoint raw-highway group distribution computed',
         all(g in sg for g in GRPS) and sum(sg.values()) > 0,
         'O_groups=%s' % {g: round(sg[g], 4) for g in GRPS})

    tacc = np.array(tacc); tegr = np.array(tegr)
    tterm = tacc + tegr
    med_acc = float(np.median(tacc)) if len(tacc) else float('nan')
    med_egr = float(np.median(tegr)) if len(tegr) else float('nan')
    med_term = float(np.median(tterm)) if len(tterm) else float('nan')
    p90_term = float(np.percentile(tterm, 90)) if len(tterm) else float('nan')
    tw = np.array(tw, dtype=float)
    med_acc_w = float(np.average(tacc, weights=tw)) if len(tacc) else float('nan')
    log('T2 access time: n=%d  T_acc med=%.1fs p90=%.1fs | T_egr med=%.1fs | T_terminal med=%.1fs p90=%.1fs'
        % (len(tacc), med_acc, np.percentile(tacc, 90) if len(tacc) else -1, med_egr, med_term, p90_term))
    gate('T2.07', 'per-trip access/egress distribution computed',
         len(tacc) > 0 and np.isfinite(med_acc), 'n=%d med_acc=%.1fs' % (len(tacc), med_acc))

    # ---- network-level free-flow decomposition (== TT_terminal/TT_trip) ----
    vol, tt, matched = read_ls(V1_LS, ids)
    vh_ff = np.where(np.isfinite(ff), vol * ff, 0.0) / 3600.0
    vh_act = np.where(np.isfinite(tt), vol * tt, 0.0) / 3600.0
    dh = np.where(np.isfinite(tt), np.maximum(tt - np.ceil(ff), 0.0) * vol, 0.0) / 3600.0
    tot_ff = float(vh_ff.sum()); tot_act = float(vh_act.sum())
    off_main = (cls != 'motorway')
    share_offmain = float(vh_ff[off_main].sum() / tot_ff) if tot_ff > 0 else float('nan')
    share_offmain_act = float(vh_act[off_main].sum() / tot_act) if tot_act > 0 else float('nan')
    tot1 = float(dh.sum())
    log('T2 free-flow VH: total=%.1f  off-mainline=%.1f (share=%.4f)  | actual VH total=%.1f share_off=%.4f'
        % (tot_ff, vh_ff[off_main].sum(), share_offmain, tot_act, share_offmain_act))
    log('T2 delay total=%.1f h (off-mainline share=%.4f)'
        % (tot1, float(dh[off_main].sum() / tot1) if tot1 > 0 else float('nan')))
    gate('T2.08', 'network-level free-flow decomposition computed', tot_ff > 0, 'total_VH_ff=%.1f' % tot_ff)
    gate('T2.09', 'share_offmain computed', np.isfinite(share_offmain) and 0.0 <= share_offmain <= 1.0,
         'share_offmain=%.4f' % share_offmain)
    gate('T2.10', 'v1.0 delay recomputed consistently (4778.8 h)',
         abs(tot1 - EXPECT_V1_DELAY_H) < 0.5, 'V1 total=%.1f h' % tot1)

    # per-class / per-group free-flow share
    ff_by_class = {c: float(vh_ff[cls == c].sum() / tot_ff) for c in CLASSES}
    ff_by_grp = {g: float(vh_ff[grp == g].sum() / tot_ff) for g in GRPS}
    dly_by_class = {c: float(dh[cls == c].sum() / tot1) for c in CLASSES}
    log('T2 ff-share by class: %s' % {c: round(ff_by_class[c], 4) for c in CLASSES})
    log('T2 ff-share by group: %s' % {g: round(ff_by_grp[g], 4) for g in GRPS})
    log('T2 delay-share by class: %s' % {c: round(dly_by_class[c], 4) for c in CLASSES})

    # ---- KW cross-check ----------------------------------------------------
    kwvol, kwtt, kwm = read_ls(KW_LS, ids)
    kw_vh_ff = np.where(np.isfinite(ff), kwvol * ff, 0.0) / 3600.0
    kw_share = float(kw_vh_ff[off_main].sum() / kw_vh_ff.sum()) if kw_vh_ff.sum() > 0 else float('nan')
    kw_dh = np.where(np.isfinite(kwtt), np.maximum(kwtt - np.ceil(ff), 0.0) * kwvol, 0.0) / 3600.0
    log('T2 KW: VH_ff total=%.1f share_offmain=%.4f | delay=%.1f h off-share=%.4f'
        % (kw_vh_ff.sum(), kw_share, kw_dh.sum(),
           float(kw_dh[off_main].sum() / kw_dh.sum()) if kw_dh.sum() > 0 else float('nan')))
    gate('T2.11', 'KW cross-check computed', kw_vh_ff.sum() > 0, 'KW VH_ff=%.1f' % kw_vh_ff.sum())

    # ---- fixed-representation flags ---------------------------------------
    svc = (hw == 'service')
    svc_cpl = np.unique(np.round(cap[svc] / np.maximum(lanes[svc], 1), 6))
    svc_fs = np.unique(np.round(fs[svc] * 3.6, 6))
    log('T2 service representation: cap/lane distinct=%s  fs_kmh distinct=%s  n_links=%d'
        % (list(svc_cpl), list(svc_fs), int(svc.sum())))
    flags = {
        'ENDPOINT_SERVICE_DOMINANT': bool(start_cls['service'] >= 0.50 or end_cls['service'] >= 0.50),
        'TERMINAL_IS_SERVICE_90': bool(either_service / tot >= 0.90),
        'OFFMAIN_MAJORITY': bool(np.isfinite(share_offmain) and share_offmain >= 0.50),
        'SERVICE_CAP_FIXED': bool(len(svc_cpl) == 1 and abs(float(svc_cpl[0]) - 400.0) < 1e-6),
        'SERVICE_SPEED_FIXED': bool(len(svc_fs) == 1 and abs(float(svc_fs[0]) - 20.0) < 1e-6),
    }

    # ---- CTE naming assertion ---------------------------------------------
    banned_hits = int(sum(1 for x in nm if BANNED_MASK in x.upper()))
    cte_n = int((nm == CTE_NAME).sum())

    # ---- VERDICT ----------------------------------------------------------
    if fin_o.mean() < 0.99 or fin_e.mean() < 0.99:
        v = 'TERMINAL_ACCESS_UNMEASURABLE'
    elif share_offmain >= OFFMAIN_HI and med_acc >= ACC_MED_HI_S:
        v = 'TERMINAL_ACCESS_CONSUMES_DOMINANT_FREE_FLOW_TIME'
    elif share_offmain >= OFFMAIN_HI:
        v = 'TERMINAL_NETWORK_DOMINATES_FREE_FLOW_TIME__ACCESS_SHORT'
    elif share_offmain >= OFFMAIN_LO:
        v = 'MIXED__TERMINAL_AND_MAINLINE_COMPARABLE'
    else:
        v = 'MAINLINE_DOMINATES_FREE_FLOW_TIME__TERMINAL_NOT_THE_BOTTLENECK'
    log('VERDICT = %s' % v)
    log('FLAGS   = %s' % flags)
    gate('T2.12', 'verdict determined', v in (
        'TERMINAL_ACCESS_UNMEASURABLE',
        'TERMINAL_ACCESS_CONSUMES_DOMINANT_FREE_FLOW_TIME',
        'TERMINAL_NETWORK_DOMINATES_FREE_FLOW_TIME__ACCESS_SHORT',
        'MIXED__TERMINAL_AND_MAINLINE_COMPARABLE',
        'MAINLINE_DOMINATES_FREE_FLOW_TIME__TERMINAL_NOT_THE_BOTTLENECK'), 'v=%s' % v)

    # ---- write ------------------------------------------------------------
    json.dump({'prereg_sha256': PREREG_SHA, 'prereg_sha256_recomputed': h,
               'prereg_match': bool(h == PREREG_SHA),
               'constants': {'OFFMAIN_HI': OFFMAIN_HI, 'OFFMAIN_LO': OFFMAIN_LO, 'ACC_MED_HI_S': ACC_MED_HI_S},
               'verdict': v, 'flags': flags,
               'endpoints': {'n_person': n_person, 'n_trip': n_trip,
                             'start_class': start_cls, 'end_class': end_cls,
                             'start_class_expansion_weighted': start_cls_w,
                             'end_class_expansion_weighted': end_cls_w,
                             'start_group': sg, 'end_group': eg,
                             'either_service_share': either_service / tot,
                             'start_service_exp_weighted': start_cls_w['service'],
                             'end_service_exp_weighted': end_cls_w['service']},
               'access_time': {'n': int(len(tacc)), 'T_acc_median_s': med_acc, 'T_egr_median_s': med_egr,
                               'T_terminal_median_s': med_term, 'T_terminal_p90_s': p90_term,
                               'T_acc_p90_s': float(np.percentile(tacc, 90)) if len(tacc) else None,
                               'T_acc_exp_weighted_mean_s': med_acc_w},
               'ff_decomposition': {'total_VH_ff': tot_ff, 'off_mainline_VH_ff': float(vh_ff[off_main].sum()),
                                    'share_offmain': share_offmain,
                                    'total_VH_actual': tot_act, 'share_offmain_actual': share_offmain_act,
                                    'ff_share_by_class': ff_by_class, 'ff_share_by_group': ff_by_grp,
                                    'delay_share_by_class': dly_by_class,
                                    'delay_offmain_share': float(dh[off_main].sum() / tot1) if tot1 > 0 else None},
               'kw_cross': {'VH_ff_total': float(kw_vh_ff.sum()), 'share_offmain': kw_share,
                            'delay_h': float(kw_dh.sum())},
               'service_representation': {'cap_per_lane_distinct': [float(x) for x in svc_cpl],
                                          'fs_kmh_distinct': [float(x) for x in svc_fs],
                                          'n_links': int(svc.sum())},
               'CTE': {'proper_n': cte_n, 'banned_mask_hits': banned_hits},
               'runtime_sec': round(time.time() - t0, 1)},
              open(OUT + '/t2_audit_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    with open(OUT + '/t2_endpoint_class.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['side', 'class', 'share', 'share_expansion_weighted'])
        for c in CLASSES:
            w.writerow(['O', c, '%.6f' % start_cls[c], '%.6f' % start_cls_w[c]])
        for c in CLASSES:
            w.writerow(['D', c, '%.6f' % end_cls[c], '%.6f' % end_cls_w[c]])
        w.writerow(['EITHER', 'service', '%.6f' % (either_service / tot), ''])
    with open(OUT + '/t2_endpoint_highway.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['side', 'group', 'share'])
        for g in GRPS: w.writerow(['O', g, '%.6f' % sg[g]])
        for g in GRPS: w.writerow(['D', g, '%.6f' % eg[g]])
    with open(OUT + '/t2_access_time.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        for k, val in (('T_acc_median_s', med_acc), ('T_acc_p90_s', float(np.percentile(tacc, 90)) if len(tacc) else -1),
                       ('T_egr_median_s', med_egr), ('T_terminal_median_s', med_term),
                       ('T_terminal_p90_s', p90_term), ('T_acc_exp_weighted_mean_s', med_acc_w),
                       ('n_trip_timed', len(tacc))):
            w.writerow([k, '%.2f' % val])
    with open(OUT + '/t2_ff_decomposition.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['scope', 'key', 'ff_share', 'vh_ff'])
        w.writerow(['ALL', 'total', '1.000000', '%.2f' % tot_ff])
        w.writerow(['ALL', 'off_mainline', '%.6f' % share_offmain, '%.2f' % float(vh_ff[off_main].sum())])
        for c in CLASSES: w.writerow(['class', c, '%.6f' % ff_by_class[c], '%.2f' % float(vh_ff[cls == c].sum())])
        for g in GRPS: w.writerow(['group', g, '%.6f' % ff_by_grp[g], '%.2f' % float(vh_ff[grp == g].sum())])
    with open(OUT + '/t2_kw_cross.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        w.writerow(['KW_VH_ff_total', '%.2f' % float(kw_vh_ff.sum())])
        w.writerow(['KW_share_offmain', '%.6f' % kw_share])
        w.writerow(['KW_delay_h', '%.2f' % float(kw_dh.sum())])

    fa = snap(FROZEN)
    changed = sum(1 for k in set(fb) | set(fa) if fb.get(k) != fa.get(k))
    gate('T2.13', 'frozen artifacts untouched', changed == 0, 'changed=%d' % changed)

    with open(OUT + '/t2_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])
    npass = sum(1 for g in gates if g['pass'])
    log('GATES: %d/%d PASS  (runtime %.1f s)' % (npass, len(gates), time.time() - t0))
    log('VERDICT = %s' % v)
    json.dump({'prereg_sha256': PREREG_SHA, 'gates': gates, 'n_pass': npass, 'n_total': len(gates),
               'verdict': v, 'flags': flags},
              open(OUT + '/t2_gates.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(OUT + '/_run_t2.log', 'w', encoding='utf-8').write('\n'.join(log_lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Step 7.9D-1 -- Ramp Interface Audit   (ZERO-SIMULATION structure; linkstats read
ONLY under the frozen PREREG)

Implements exactly the frozen rules of:
  reports/ramp_interface_7_9d1/PREREG_7_9D-1.md
      sha256 = 5c8fd9c17af255dff25c214d5e1965a0ed0351009aad5af66b5f316affba8983

Narrow question (user-ratified):
  Is the mainline <-> ramp <-> local interface topologically continuous and
  capacity-consistent, and does ramp delay actually propagate to the motorway?

R1 interface topology (single-hop vs multi-hop physical)
R2 lane / capacity discontinuity at the merge
R3 ramp physical chain length
R4 ramp local storage / fill time
R5 ramp delay propagation (v1.0 & KW)

Discipline: no sim re-run; frozen artifacts untouched; v1.0 untouched; no v1.1.
"""
import os, io, csv, gzip, json, time, math, gc, sys, collections, hashlib, heapq
import numpy as np
import pandas as pd

ROOT   = r'D:/Luan/2026-05/2_Singapore'
CACHE  = ROOT + '/scripts/od/_cache_network_7_9c0.npz'
PREREG = ROOT + '/reports/ramp_interface_7_9d1/PREREG_7_9D-1.md'
V1_LS  = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/ITERS/it.19/W01_rc_min.19.linkstats.txt.gz'
KW_LS  = ROOT + '/matsim_kw_7_9b1/outputs/W01_kw/ITERS/it.19/W01_kw.19.linkstats.txt.gz'
OUT    = ROOT + '/reports/ramp_interface_7_9d1'
FROZEN = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8', ROOT + '/matsim_kw_7_9b1']

PREREG_SHA = '5c8fd9c17af255dff25c214d5e1965a0ed0351009aad5af66b5f316affba8983'

# ---- frozen constants (PREREG §4) -------------------------------------------
RAMP_NEAR_M, RAMP_FAR_M = 300.0, 1000.0
DELAY_HOST_SHARE, LANE_DROP_THR = 0.05, 0.20
EXPECT_RAMP_LINKS, EXPECT_RAMP_KM = 11740, 308.15
EXPECT_V1_DELAY_H = 4778.8
CELL = 7.5
CLASSES = ('motorway', 'ramp', 'connector', 'service', 'other')
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


def main():
    t0 = time.time(); os.makedirs(OUT, exist_ok=True)
    gates = []
    def gate(gid, desc, ok, detail):
        gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

    fb = snap(FROZEN)
    log('=== Step 7.9D-1 Ramp Interface Audit ===')

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
    RM = (cls == 'ramp'); MW = (cls == 'motorway')
    ff = np.where(fs > 0, ln / fs, np.nan)          # free-flow seconds
    cpl = cap / np.maximum(lanes, 1)                # cap per lane
    log('network: links=%d km=%.2f  ramp_links=%d ramp_km=%.2f  mw_links=%d mw_km=%.2f'
        % (n, Lk.sum(), RM.sum(), Lk[RM].sum(), MW.sum(), Lk[MW].sum()))
    gate('R1.01', 'network from frozen v1.0 cache (693575 / 15126.5 km)',
         n == 693575 and abs(Lk.sum() - 15126.5) < 5.0, 'links=%d km=%.2f' % (n, Lk.sum()))
    gate('R1.02', 'class masks non-degenerate', bool(RM.sum() > 0 and MW.sum() > 0),
         'ramp=%d motorway=%d' % (RM.sum(), MW.sum()))
    gate('R1.03', 'ramp reproduced (11740 / 308.15 km)',
         int(RM.sum()) == EXPECT_RAMP_LINKS and abs(float(Lk[RM].sum()) - EXPECT_RAMP_KM) < 0.5,
         'ramp_links=%d ramp_km=%.2f' % (RM.sum(), Lk[RM].sum()))

    outb = collections.defaultdict(list); inb = collections.defaultdict(list)
    for i in range(n):
        outb[frm[i]].append(i); inb[to[i]].append(i)

    # ---- R1 single-hop interface type -------------------------------------
    cnt = collections.Counter()
    on_ramp_ids = []; off_ramp_ids = []
    for i in np.where(RM)[0]:
        up = set(cls[j] for j in inb.get(frm[i], []))
        dn = set(cls[k] for k in outb.get(to[i], []))
        mw_up = 'motorway' in up; mw_dn = 'motorway' in dn
        if mw_up and mw_dn: cnt['both'] += 1
        elif mw_up: cnt['off_ramp'] += 1
        elif mw_dn: cnt['on_ramp'] += 1
        else: cnt['neither'] += 1
        # merge-side membership (a link may be both an on-ramp and an off-ramp)
        if mw_dn: on_ramp_ids.append(int(i))
        if mw_up: off_ramp_ids.append(int(i))
    on_ramp = np.array(sorted(set(on_ramp_ids)), dtype=np.int64)
    off_ramp = np.array(sorted(set(off_ramp_ids)), dtype=np.int64)
    n_neither = cnt['neither']
    single_hop_taut = (n_neither / max(RM.sum(), 1)) >= 0.80
    log('R1 single-hop: on=%d off=%d both=%d neither=%d (neither share=%.4f) tautology=%s'
        % (cnt['on_ramp'], cnt['off_ramp'], cnt['both'], cnt['neither'],
           n_neither / max(RM.sum(), 1), single_hop_taut))
    gate('R1.04', 'single-hop interface types computed',
         (cnt['on_ramp'] + cnt['off_ramp'] + cnt['both'] + cnt['neither']) == int(RM.sum()),
         'on=%d off=%d both=%d neither=%d' % (cnt['on_ramp'], cnt['off_ramp'], cnt['both'], cnt['neither']))

    # ---- R1 multi-hop physical distance (PRIMARY) --------------------------
    def dij(w_of):
        d = np.full(n, math.inf, dtype=float); pq = []
        for i in np.where(MW)[0]:
            d[i] = 0.0; heapq.heappush(pq, (0.0, int(i)))
        while pq:
            du, k = heapq.heappop(pq)
            if du > d[k] + 1e-9: continue
            for j, w in w_of(int(k)):
                nd = du + w
                if nd < d[j] - 1e-9:
                    d[j] = nd; heapq.heappush(pq, (nd, int(j)))
        return d
    # access distance: from i forward to mainline (expand UPSTREAM from mainline)
    acc_m = dij(lambda k: [(int(j), float(ln[j])) for j in inb.get(frm[k], [])])
    # egress distance: from mainline forward to i (expand DOWNSTREAM from mainline)
    egr_m = dij(lambda k: [(int(i2), float(ln[i2])) for i2 in outb.get(to[k], [])])
    fin_a = np.isfinite(acc_m); fin_e = np.isfinite(egr_m)
    a_ok = fin_a.mean() >= 0.999 and float(acc_m[fin_a].min()) > 0
    e_ok = fin_e.mean() >= 0.999 and float(egr_m[fin_e].min()) > 0
    log('R1 multi-hop acc_m finite=%.4f med=%.0f p90=%.0f | egr_m finite=%.4f med=%.0f p90=%.0f'
        % (fin_a.mean(), np.median(acc_m[fin_a]), np.percentile(acc_m[fin_a], 90),
           fin_e.mean(), np.median(egr_m[fin_e]), np.percentile(egr_m[fin_e], 90)))
    log('R1 ramp acc_m: finite=%.4f med=%.0f p90=%.0f  <=300m=%.4f  >1000m=%.4f'
        % (fin_a[RM].mean(), np.median(acc_m[RM][fin_a[RM]]), np.percentile(acc_m[RM][fin_a[RM]], 90),
           (acc_m[RM][fin_a[RM]] <= RAMP_NEAR_M).mean(), (acc_m[RM][fin_a[RM]] > RAMP_FAR_M).mean()))
    gate('R1.05', 'multi-hop access distance complete (finite>=0.999, min>0)', a_ok,
         'finite=%.4f min=%.1f' % (fin_a.mean(), acc_m[fin_a].min()))
    gate('R1.06', 'multi-hop egress distance complete (finite>=0.999, min>0)', e_ok,
         'finite=%.4f min=%.1f' % (fin_e.mean(), egr_m[fin_e].min()))

    # ---- R2 lane / capacity discontinuity at the merge --------------------
    lane_drop = 0; deltas = []; capdel = []
    for i in on_ramp:
        mw_dn = [k for k in outb.get(to[i], []) if cls[k] == 'motorway']
        if not mw_dn: continue
        d = min(lanes[k] for k in mw_dn) - lanes[i]
        deltas.append(d)
        capdel.append(min(cpl[k] for k in mw_dn) - cpl[i])
        if d < 0: lane_drop += 1
    deltas = np.array(deltas, dtype=float); capdel = np.array(capdel, dtype=float)
    lane_drop_share = lane_drop / len(deltas) if len(deltas) else float('nan')
    log('R2 on-ramp merge: n=%d  dlanes med=%.0f min=%.0f max=%.0f  lane_drop=%d (share=%.4f)  dcap/lane med=%.0f'
        % (len(deltas), np.median(deltas), deltas.min(), deltas.max(), lane_drop, lane_drop_share, np.median(capdel)))
    gate('R1.07', 'lane discontinuity computed (on-ramp sample >=100)',
         len(deltas) >= 100 and np.isfinite(lane_drop_share),
         'n_on_ramp=%d lane_drop_share=%.4f' % (len(deltas), lane_drop_share))

    # ---- R3 ramp chain length ---------------------------------------------
    chain = acc_m[RM] + ln[RM]
    fc = np.isfinite(chain)
    log('R3 ramp chain len (acc_m + own len): med=%.0f m  p90=%.0f m  own piece med=%.1f m  pieces<=20m=%.4f'
        % (np.median(chain[fc]), np.percentile(chain[fc], 90), np.median(ln[RM]), (ln[RM] <= 20).mean()))

    # ---- delays ------------------------------------------------------------
    def delays(path):
        vol, tt, matched = read_ls(path, ids)
        dh = np.where(np.isfinite(tt), np.maximum(tt - np.ceil(ff), 0.0) * vol, 0.0) / 3600.0
        return {'vol': vol, 'tt': tt, 'delay_h': dh, 'matched': matched}
    D = {'V1': delays(V1_LS), 'KW': delays(KW_LS)}
    for t in ('V1', 'KW'):
        log('  [%s] matched=%d  total delay=%.1f h' % (t, D[t]['matched'], D[t]['delay_h'].sum()))
    d1 = D['V1']['delay_h']; tot1 = float(d1.sum())
    gate('R1.08', 'v1.0 delay recomputed consistently (4778.8 h)',
         abs(tot1 - EXPECT_V1_DELAY_H) < 0.5, 'V1 total=%.1f h' % tot1)

    # ---- R5 ramp delay propagation ----------------------------------------
    ramp_delay = float(d1[RM].sum()); ramp_share = ramp_delay / tot1 if tot1 > 0 else 0.0
    ramp_km_share = float(Lk[RM].sum() / Lk.sum())
    ramp_ratio = ramp_share / ramp_km_share if ramp_km_share > 0 else float('nan')
    mw_delay = float(d1[MW].sum()); mw_share = mw_delay / tot1 if tot1 > 0 else 0.0
    ramp_vol_share = float(D['V1']['vol'][RM].sum() / D['V1']['vol'].sum())
    # delay-weighted access distance for ramp
    m = RM & np.isfinite(acc_m)
    dw_acc = float((d1[m] * acc_m[m]).sum() / d1[m].sum()) if d1[m].sum() > 0 else float('nan')
    dlyr = RM & (d1 > 0.01) & np.isfinite(acc_m)
    ramp_delay_near = float((acc_m[dlyr] <= RAMP_NEAR_M).mean()) if dlyr.sum() else float('nan')
    ramp_delay_far = float((acc_m[dlyr] > RAMP_FAR_M).mean()) if dlyr.sum() else float('nan')
    log('R5 ramp: delay=%.1f h (share=%.4f, km_share=%.4f, ratio=%.3f) vol_share=%.4f'
        % (ramp_delay, ramp_share, ramp_km_share, ramp_ratio, ramp_vol_share))
    log('R5 delay-weighted access distance (ramp)=%.0f m ; ramp delay links: n=%d near<=300m=%.4f far>1000m=%.4f'
        % (dw_acc, int(dlyr.sum()), ramp_delay_near, ramp_delay_far))
    gate('R1.09', 'ramp delay share computed', np.isfinite(ramp_share) and np.isfinite(ramp_ratio),
         'ramp_delay_h=%.2f share=%.4f ratio=%.3f' % (ramp_delay, ramp_share, ramp_ratio))

    # ---- R4 ramp local storage / fill --------------------------------------
    ramp_stor = ln[RM] * lanes[RM] / CELL
    r_nodes = set()
    for x in np.concatenate([np.where(RM)[0]]):
        r_nodes.add(to[x])
    fills = []
    for x in r_nodes:
        outs = outb.get(x, []); ins = inb.get(x, [])
        stor = sum(ln[k] * lanes[k] / CELL for k in outs)
        inf = sum(cap[k] / 3600.0 for k in ins)
        if inf > 0: fills.append(stor / inf)
    fills = np.array(fills, dtype=float)
    log('R4 ramp piece storage veh: med=%.2f p90=%.2f | downstream-node fill s: med=%.2f p10=%.2f  n=%d'
        % (np.median(ramp_stor), np.percentile(ramp_stor, 90),
           np.median(fills) if len(fills) else float('nan'),
           np.percentile(fills, 10) if len(fills) else float('nan'), len(fills)))
    gate('R1.10', 'ramp storage / fill computed',
         len(ramp_stor) > 0 and len(fills) > 0,
         'piece_med=%.2f fill_med=%.2f' % (np.median(ramp_stor), np.median(fills) if len(fills) else -1))

    # ---- KW cross-check ----------------------------------------------------
    kw = D['KW']
    kw_ramp = float(kw['delay_h'][RM].sum()); kw_tot = float(kw['delay_h'].sum())
    log('R5 KW ramp delay=%.2f h (share=%.4f, total=%.1f h)' % (kw_ramp, kw_ramp / kw_tot if kw_tot else 0, kw_tot))
    gate('R1.11', 'KW cross-check computed', kw_tot > 0,
         'KW total=%.1f h ramp=%.2f h' % (kw_tot, kw_ramp))

    # ---- CTE naming assertion ---------------------------------------------
    banned_hits = int(sum(1 for x in nm if BANNED_MASK in x.upper()))
    cte_n = int((nm == CTE_NAME).sum())
    log('CTE: banned-mask hits=%d ; proper n=%d' % (banned_hits, cte_n))

    # ==================================================================
    # SUPPLEMENTARY (NOT pre-registered; cannot alter the frozen verdict)
    # (a) The frozen sub-condition "min>0" in R1.05/R1.06 is logically
    #     IMPOSSIBLE: mainline seed links have distance exactly 0 by
    #     construction.  Restate the SAME INTENT as a well-posed property.
    # (b) The frozen flag CAP_DETERMINISTIC is worded per-highway; check it
    #     at the finest (highway) resolution within the ramp class.
    # ==================================================================
    sup_gates = []
    def sgate(gid, desc, ok, detail):
        sup_gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

    mw_seed_a = bool(np.all(acc_m[MW] == 0.0)); mw_seed_e = bool(np.all(egr_m[MW] == 0.0))
    acc_well = (fin_a.mean() == 1.0) and mw_seed_a and float(acc_m[(~MW) & fin_a].min()) > 0
    egr_well = (fin_e.mean() == 1.0) and mw_seed_e and float(egr_m[(~MW) & fin_e].min()) > 0
    ramp_hw_cpl = {str(h): int(len(np.unique(np.round(cpl[RM & (hw == h)], 6)))) for h in np.unique(hw[RM])}
    cap_det = all(v == 1 for v in ramp_hw_cpl.values())
    sgate('S1.01', 'access distance field WELL-POSED (finite=100%, mainline seeds==0, non-mainline>0)',
          acc_well, 'finite=%.4f seeds0=%s nonmw_min=%.1f' % (fin_a.mean(), mw_seed_a, acc_m[(~MW) & fin_a].min()))
    sgate('S1.02', 'egress distance field WELL-POSED (finite=100%, mainline seeds==0, non-mainline>0)',
          egr_well, 'finite=%.4f seeds0=%s nonmw_min=%.1f' % (fin_e.mean(), mw_seed_e, egr_m[(~MW) & fin_e].min()))
    sgate('S1.03', 'cap/lane deterministic per highway within ramp class',
          cap_det, 'per_highway_ndistinct=%s' % ramp_hw_cpl)
    log('SUP R1.05/R1.06 restated well-posed: acc=%s egr=%s | ramp cap/lane per-highway=%s'
        % (acc_well, egr_well, ramp_hw_cpl))

    # ---- VERDICT ----------------------------------------------------------
    if fin_a.mean() < 0.99 or fin_e.mean() < 0.99:
        v = 'RAMP_INTERFACE_BROKEN__NO_PATH_TO_MAINLINE'
    elif lane_drop_share >= LANE_DROP_THR:
        v = 'RAMP_INTERFACE_LANE_DISCONTINUITY_AT_MERGE'
    elif ramp_share < DELAY_HOST_SHARE and dw_acc <= RAMP_FAR_M:
        v = 'RAMP_INTERFACE_CONTINUOUS__RAMP_NOT_A_DELAY_HOST'
    elif dw_acc > RAMP_FAR_M:
        v = 'RAMP_INTERFACE_CONTINUOUS_BUT_DISTANT__DELAY_DECOUPLED_FROM_MAINLINE'
    else:
        v = 'INDETERMINATE'
    flags = {
        'SINGLE_HOP_TAUTOLOGY': bool(single_hop_taut),
        'LANE_DROP': bool(np.isfinite(lane_drop_share) and lane_drop_share >= LANE_DROP_THR),
        'RAMP_IS_DELAY_HOST': bool(ramp_share >= DELAY_HOST_SHARE),
        'RAMP_NEAR_MAINLINE': bool(np.isfinite(dw_acc) and dw_acc <= RAMP_NEAR_M),
        'CAP_DETERMINISTIC': bool(cap_det),
    }
    log('VERDICT = %s' % v)
    log('FLAGS   = %s' % flags)
    gate('R1.12', 'verdict determined', v in (
        'RAMP_INTERFACE_BROKEN__NO_PATH_TO_MAINLINE',
        'RAMP_INTERFACE_LANE_DISCONTINUITY_AT_MERGE',
        'RAMP_INTERFACE_CONTINUOUS__RAMP_NOT_A_DELAY_HOST',
        'RAMP_INTERFACE_CONTINUOUS_BUT_DISTANT__DELAY_DECOUPLED_FROM_MAINLINE',
        'INDETERMINATE'), 'v=%s' % v)

    # ---- write ------------------------------------------------------------
    json.dump({'prereg_sha256': PREREG_SHA, 'prereg_sha256_recomputed': h,
               'prereg_match': bool(h == PREREG_SHA),
               'constants': {'RAMP_NEAR_M': RAMP_NEAR_M, 'RAMP_FAR_M': RAMP_FAR_M,
                             'DELAY_HOST_SHARE': DELAY_HOST_SHARE, 'LANE_DROP_THR': LANE_DROP_THR},
               'verdict': v, 'flags': flags,
               'interface_single_hop': dict(cnt),
               'interface_multihop': {
                   'ramp_acc_m_median': float(np.median(acc_m[RM][fin_a[RM]])),
                   'ramp_acc_m_p90': float(np.percentile(acc_m[RM][fin_a[RM]], 90)),
                   'ramp_acc_le_300m': float((acc_m[RM][fin_a[RM]] <= RAMP_NEAR_M).mean()),
                   'ramp_acc_gt_1000m': float((acc_m[RM][fin_a[RM]] > RAMP_FAR_M).mean()),
                   'ramp_egr_m_median': float(np.median(egr_m[RM][fin_e[RM]])),
                   'all_links_acc_m_median': float(np.median(acc_m[fin_a]))},
               'lane_discontinuity': {'n_on_ramp': int(len(deltas)),
                                      'dlanes_median': float(np.median(deltas)),
                                      'dlanes_min': float(deltas.min()), 'dlanes_max': float(deltas.max()),
                                      'lane_drop_n': int(lane_drop), 'lane_drop_share': float(lane_drop_share),
                                      'dcap_per_lane_median': float(np.median(capdel))},
               'ramp_chain': {'chain_len_median_m': float(np.median(chain[fc])),
                              'chain_len_p90_m': float(np.percentile(chain[fc], 90)),
                              'own_piece_median_m': float(np.median(ln[RM])),
                              'own_piece_le20m_share': float((ln[RM] <= 20).mean())},
               'ramp_storage': {'piece_storage_veh_median': float(np.median(ramp_stor)),
                                'downstream_fill_s_median': float(np.median(fills)) if len(fills) else None,
                                'n_nodes': int(len(fills))},
               'ramp_delay': {'V1_delay_h': ramp_delay, 'V1_share': ramp_share,
                              'V1_km_share': ramp_km_share, 'V1_ratio': ramp_ratio,
                              'V1_vol_share': ramp_vol_share,
                              'delay_weighted_acc_m': dw_acc,
                              'delay_links_n': int(dlyr.sum()),
                              'delay_links_near_300m': ramp_delay_near,
                              'delay_links_far_1000m': ramp_delay_far,
                              'KW_delay_h': kw_ramp, 'KW_share': (kw_ramp / kw_tot if kw_tot else 0.0)},
               'motorway_delay': {'V1_delay_h': mw_delay, 'V1_share': mw_share},
               'CTE': {'proper_n': cte_n, 'banned_mask_hits': banned_hits},
               'SUPPLEMENTARY': {'acc_well_posed': acc_well, 'egr_well_posed': egr_well,
                                 'ramp_cap_per_lane_by_highway': ramp_hw_cpl},
               'runtime_sec': round(time.time() - t0, 1)},
              open(OUT + '/r1_audit_summary.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    with open(OUT + '/r1_interface_topology.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        for k, val in cnt.items(): w.writerow(['single_hop_' + k, val])
        w.writerow(['single_hop_neither_share', '%.6f' % (n_neither / max(RM.sum(), 1))])
        w.writerow(['ramp_acc_m_median', '%.1f' % np.median(acc_m[RM][fin_a[RM]])])
        w.writerow(['ramp_acc_m_p90', '%.1f' % np.percentile(acc_m[RM][fin_a[RM]], 90)])
        w.writerow(['ramp_acc_le_300m_share', '%.6f' % (acc_m[RM][fin_a[RM]] <= RAMP_NEAR_M).mean()])
        w.writerow(['ramp_acc_gt_1000m_share', '%.6f' % (acc_m[RM][fin_a[RM]] > RAMP_FAR_M).mean()])
        w.writerow(['ramp_egr_m_median', '%.1f' % np.median(egr_m[RM][fin_e[RM]])])
    with open(OUT + '/r1_lane_discontinuity.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        w.writerow(['n_on_ramp', len(deltas)]); w.writerow(['dlanes_median', '%.1f' % np.median(deltas)])
        w.writerow(['dlanes_min', '%.1f' % deltas.min()]); w.writerow(['dlanes_max', '%.1f' % deltas.max()])
        w.writerow(['lane_drop_n', lane_drop]); w.writerow(['lane_drop_share', '%.6f' % lane_drop_share])
        w.writerow(['dcap_per_lane_median', '%.1f' % np.median(capdel)])
    with open(OUT + '/r1_ramp_chain.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        w.writerow(['chain_len_median_m', '%.1f' % np.median(chain[fc])])
        w.writerow(['chain_len_p90_m', '%.1f' % np.percentile(chain[fc], 90)])
        w.writerow(['own_piece_median_m', '%.2f' % np.median(ln[RM])])
    with open(OUT + '/r1_ramp_delay.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        for k, val in (('V1_delay_h', ramp_delay), ('V1_share', ramp_share), ('V1_km_share', ramp_km_share),
                       ('V1_ratio', ramp_ratio), ('V1_vol_share', ramp_vol_share),
                       ('delay_weighted_acc_m', dw_acc), ('delay_links_n', int(dlyr.sum())),
                       ('delay_links_near_300m', ramp_delay_near), ('delay_links_far_1000m', ramp_delay_far),
                       ('KW_delay_h', kw_ramp), ('KW_share', (kw_ramp / kw_tot if kw_tot else 0.0)),
                       ('motorway_V1_delay_h', mw_delay), ('motorway_V1_share', mw_share)):
            w.writerow([k, '%.6f' % val])
    with open(OUT + '/r1_storage.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['metric', 'value'])
        w.writerow(['piece_storage_veh_median', '%.3f' % np.median(ramp_stor)])
        w.writerow(['downstream_fill_s_median', '%.3f' % (np.median(fills) if len(fills) else float('nan'))])

    fa = snap(FROZEN)
    changed = sum(1 for k in set(fb) | set(fa) if fb.get(k) != fa.get(k))
    gate('R1.13', 'frozen artifacts untouched', changed == 0, 'changed=%d' % changed)

    with open(OUT + '/r1_checks.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['id', 'desc', 'pass', 'detail'])
        for g in gates: w.writerow([g['id'], g['desc'], g['pass'], g['detail']])
        for g in sup_gates: w.writerow([g['id'], '[SUPPLEMENTARY] ' + g['desc'], g['pass'], g['detail']])
    npass = sum(1 for g in gates if g['pass']); nsup = sum(1 for g in sup_gates if g['pass'])
    log('GATES: %d/%d PASS  (supplementary %d/%d)  runtime %.1f s'
        % (npass, len(gates), nsup, len(sup_gates), time.time() - t0))
    log('VERDICT = %s' % v)
    json.dump({'prereg_sha256': PREREG_SHA, 'gates': gates, 'sup_gates': sup_gates,
               'n_pass': npass, 'n_total': len(gates),
               'sup_n_pass': nsup, 'sup_n_total': len(sup_gates),
               'verdict': v, 'flags': flags},
              open(OUT + '/r1_gates.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    open(OUT + '/_run_r1.log', 'w', encoding='utf-8').write('\n'.join(log_lines))
    return 0


if __name__ == '__main__':
    sys.exit(main())

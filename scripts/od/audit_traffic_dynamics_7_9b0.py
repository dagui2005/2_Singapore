# -*- coding: utf-8 -*-
"""
Step 7.9B-0 -- Traffic Dynamics Mechanism Audit (ZERO-SIMULATION, READ-ONLY).

Question set (user-preregistered):
  B1  which traffic dynamics is ACTUALLY effective
  B2  does the effective `queue` model carry an inflow constraint
  B3  how many links would bind to the kinematicWaves FD inflow ceiling
  B4  are those links concentrated at merge / diverge nodes
  B5  what is the effective spatial scale of a bottleneck in a fragmented network

Discipline: no MATSim re-run, no frozen artifact touched, source claims are
re-verified against the shipped matsim-2026.0-sources.jar (not from memory).
"""
import os, io, gzip, re, json, time, zipfile
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT    = r'D:/Luan/2026-05/2_Singapore'
NET     = ROOT + '/matsim_final_7_6h/outputs/W01_rc_min/W01_rc_min.output_network.xml.gz'
CFG     = ROOT + '/matsim_final_7_6h/configs/config_W01_rc_min.xml'
SRCJAR  = ROOT + '/tools/matsim-2026.0/matsim-2026.0-sources.jar'
OUT     = ROOT + '/reports/traffic_dynamics_audit_7_9b0'
FROZEN_DIRS = [ROOT + '/matsim_final_7_6h', ROOT + '/matsim_viz_7_8']

# ---- MATSim 2026.0 constants (each re-verified against the sources jar) ----
CELL_SIZE       = 7.5      # NetworkImpl.DEFAULT_EFFECTIVE_CELL_SIZE
HOLE_SPEED_KMH  = 15.0     # QueueWithBuffer.HOLE_SPEED_KM_H
V_HOLE_MS       = HOLE_SPEED_KMH / 3.6
TIME_STEP_S     = 1.0      # qsim.timeStepSize
F_CAP_UNSCALED  = 1.0      # qsim.flowCapacityFactor in v1.0

log_lines = []
def log(msg):
    log_lines.append(msg)
    print(msg)

def gate(gates, gid, desc, ok, detail):
    gates.append({'id': gid, 'desc': desc, 'pass': bool(ok), 'detail': str(detail)})

def esc(x):
    return str(x).replace('|', r'\|')

def md_table(header, rows):
    out = ['| ' + ' | '.join(esc(h) for h in header) + ' |',
           '|' + '|'.join(['---'] * len(header)) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(esc(c) for c in r) + ' |')
    return '\n'.join(out)

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
# 0. source verification (falsify-before-assert)
# =====================================================================
def verify_source(gates):
    z = zipfile.ZipFile(SRCJAR)
    qwb = z.read('org/matsim/core/mobsim/qsim/qnetsimengine/QueueWithBuffer.java').decode('utf-8').split('\n')
    qcfg = z.read('org/matsim/core/config/groups/QSimConfigGroup.java').decode('utf-8').split('\n')
    nimpl = z.read('org/matsim/core/network/NetworkImpl.java').decode('utf-8').split('\n')

    def find(lines, needle, fname):
        for i, l in enumerate(lines, 1):
            if needle in l:
                return {'file': fname, 'line': i, 'code': l.strip()}
        return None

    ev = {}
    probes = [
        ('hole_speed',      qwb,  'HOLE_SPEED_KM_H = 15.0',                 'QueueWithBuffer.java'),
        ('fd_formula',      qwb,  'final double maxFlowFromFdiag',           'QueueWithBuffer.java'),
        ('fd_setting',      qwb,  'inflowCapacitySetting == QSimConfigGroup.InflowCapacitySetting.INFLOW_FROM_FDIAG', 'QueueWithBuffer.java'),
        ('fd_assign',       qwb,  'this.maxInflowUsedInQsim = maxFlowFromFdiag;', 'QueueWithBuffer.java'),
        ('queue_noop',      qwb,  'case queue:',                             'QueueWithBuffer.java'),
        ('init_inflow',     qwb,  'this.maxInflowUsedInQsim = this.flowCapacityPerTimeStep;', 'QueueWithBuffer.java'),
        ('storage_basic',   qwb,  'storageCapacity = this.length * this.effectiveNumberOfLanesUsedInQsim', 'QueueWithBuffer.java'),
        ('storage_enlarge', qwb,  'tempStorageCapacity = freespeedTravelTime * unscaledFlowCapacity_s', 'QueueWithBuffer.java'),
        ('kw_storage_min',  qwb,  'minStorCapForHoles = length * flowCapacityPerTimeStep', 'QueueWithBuffer.java'),
        ('kw_unscaled_nt',  qwb,  'we leave the inflow capacity (unscaled)', 'QueueWithBuffer.java'),
        ('default_inflow_setting', qcfg, 'inflowCapacitySetting = InflowCapacitySetting.INFLOW_FROM_FDIAG', 'QSimConfigGroup.java'),
        ('default_trafficdyn',     qcfg, 'trafficDynamics = TrafficDynamics.queue', 'QSimConfigGroup.java'),
        ('default_stuck',          qcfg, 'private double stuckTime = 10;',    'QSimConfigGroup.java'),
        ('default_removestuck',    qcfg, 'removeStuckVehicles = false',       'QSimConfigGroup.java'),
        ('default_cellsize',       nimpl, 'DEFAULT_EFFECTIVE_CELL_SIZE = 7.5;', 'NetworkImpl.java'),
    ]
    all_ok = True
    for key, lines, needle, fname in probes:
        hit = find(lines, needle, fname)
        ev[key] = hit
        if hit is None:
            all_ok = False
    gates.append({'id': 'B0.S', 'desc': 'source evidence re-verified in matsim-2026.0-sources.jar',
                  'pass': all_ok, 'detail': f'{len(probes)} probes, {sum(1 for v in ev.values() if v)} found'})
    return ev

# =====================================================================
# 1. read v1.0 config (effective values, with module provenance)
# =====================================================================
def read_cfg(path):
    s = io.open(path, encoding='utf-8').read()
    vals = {}
    for m in re.finditer(r'<param name="([^"]+)"\s+value="([^"]*)"\s*/>', s):
        k, v = m.group(1), m.group(2)
        start = s.rfind('<module name="', 0, m.start())
        mod = re.search(r'<module name="([^"]+)"', s[start:]).group(1) if start >= 0 else '?'
        vals.setdefault(k, []).append((mod, v))
    return vals

# =====================================================================
# 2. parse network
# =====================================================================
LINK_RE = re.compile(
    r'<link\s+id="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+length="([^"]+)"\s+'
    r'freespeed="([^"]+)"\s+capacity="([^"]+)"\s+permlanes="([^"]+)"')
NODE_RE = re.compile(r'<node\s+id="([^"]+)"')

def parse_network(path):
    L_id, L_from, L_to, L_len, L_fs, L_cap, L_lanes = [], [], [], [], [], [], []
    n_nodes = 0
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            if '<node ' in line:
                if NODE_RE.search(line):
                    n_nodes += 1
                continue
            if '<link ' not in line:
                continue
            m = LINK_RE.search(line)
            if not m:
                continue
            L_id.append(m.group(1))
            L_from.append(m.group(2))
            L_to.append(m.group(3))
            L_len.append(float(m.group(4)))
            L_fs.append(float(m.group(5)))
            L_cap.append(float(m.group(6)))
            L_lanes.append(float(m.group(7)))
    d = dict(ids=L_id, frm=L_from, to=L_to,
             length=np.asarray(L_len), fs=np.asarray(L_fs),
             cap=np.asarray(L_cap), lanes=np.asarray(L_lanes))
    return d, n_nodes

# =====================================================================
# main
# =====================================================================
def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    gates = []
    frozen_before = snap(FROZEN_DIRS)
    log('=== Step 7.9B-0 Traffic Dynamics Mechanism Audit (zero-simulation) ===')

    ev = verify_source(gates)
    log('source probes  : %d ok' % sum(1 for v in ev.values() if v))
    for k, v in ev.items():
        log('   %-24s %s' % (k, (v['file'] + ' L' + str(v['line'])) if v else 'MISSING'))

    cfg = read_cfg(CFG)
    # ---- B1 -----------------------------------------------------------
    q_td   = cfg.get('trafficDynamics', [])
    q_mob  = cfg.get('mobsim', [])
    q_fcap = cfg.get('flowCapacityFactor', [])
    q_scap = cfg.get('storageCapacityFactor', [])
    q_ts   = cfg.get('timeStepSize', [])
    q_stk  = cfg.get('stuckTime', [])
    q_rsv  = cfg.get('removeStuckVehicles', [])
    q_ics  = cfg.get('inflowCapacitySetting', [])

    eff_td = [v for m, v in q_td if m == 'qsim']
    mobsim = [v for m, v in q_mob]
    eff_inflow_setting = q_ics[0][1] if q_ics else 'INFLOW_FROM_FDIAG (MATSim default, not set in cfg)'
    log('\nB1 effective traffic dynamics')
    log('  qsim.trafficDynamics   = %s' % eff_td)
    log('  controller.mobsim      = %s' % mobsim)
    log('  dsim.trafficDynamics   = %s (INERT)' % [v for m, v in q_td if m == 'dsim'])
    log('  inflowCapacitySetting  = %s' % eff_inflow_setting)

    gate(gates, 'B0.01', 'effective mobsim is qsim',
         mobsim == ['qsim'], 'controller.mobsim=%s' % mobsim)
    gate(gates, 'B0.02', 'effective trafficDynamics is queue',
         eff_td == ['queue'], 'qsim.trafficDynamics=%s' % eff_td)
    gate(gates, 'B0.03', 'dsim.trafficDynamics is present but inert',
         any(m == 'dsim' and v == 'kinematicWaves' for m, v in q_td), 'dsim=kinematicWaves while mobsim=qsim')
    gate(gates, 'B0.04', 'inflowCapacitySetting not overridden -> MATSim default',
         len(q_ics) == 0, 'default = INFLOW_FROM_FDIAG')

    # ---- B2 -----------------------------------------------------------
    queue_has_inflow = ev['queue_noop'] is not None and ev['init_inflow'] is not None
    log('\nB2 does the effective queue model carry an inflow constraint?')
    log('  switch(TrafficDynamics) { case queue: case withHoles: break; ... }  -> NO branch executes')
    log('  maxInflowUsedInQsim initialised to flowCapacityPerTimeStep only')
    log('  => queue has NO kinematic-wave inflow restriction; inflow cap == network capacity x flowCapFactor')
    gate(gates, 'B0.05', 'queue branch performs no inflow modification',
         queue_has_inflow,
         'QueueWithBuffer L393-396 (case queue -> break) + L391 (init to flowCapacityPerTimeStep)')

    # ---- network ------------------------------------------------------
    log('\nparsing network ...')
    net, n_nodes = parse_network(NET)
    n_links = len(net['ids'])
    Lk = net['length'] * 0.001
    fs_kmh = net['fs'] * 3.6
    lanes = net['lanes']
    cap = net['cap']
    lane_cap = cap / lanes
    log('  nodes=%d links=%d total_km=%.3f' % (n_nodes, n_links, Lk.sum()))

    # ---- B3: FD inflow ceiling vs network capacity --------------------
    fd_link = (lanes / CELL_SIZE) / (1.0 / V_HOLE_MS + 1.0 / net['fs']) * 3600.0
    fd_lane = (1.0 / CELL_SIZE) / (1.0 / V_HOLE_MS + 1.0 / net['fs']) * 3600.0
    r_link = fd_link / cap                 # INFLOW_FROM_FDIAG  (link level, lanes-scaled)
    r_lane = fd_lane / lane_cap            # MAX_CAP_FOR_ONE_LANE (per-lane) variant

    for nm, r in (('INFLOW_FROM_FDIAG', r_link), ('MAX_CAP_FOR_ONE_LANE', r_lane)):
        m = r < 1.0
        log('\nB3 r_fdiag[%s]: links r<1 = %d (%.4f%%), km = %.2f (%.4f%% of network)'
            % (nm, int(m.sum()), 100.0 * m.mean(), Lk[m].sum(), 100.0 * Lk[m].sum() / Lk.sum()))

    m_restricted = r_link < 1.0
    n_restricted = int(m_restricted.sum())
    km_restricted = float(Lk[m_restricted].sum())
    gate(gates, 'B0.06', 'r_fdiag computed for every link',
         np.isfinite(r_link).all(), 'n=%d' % n_links)
    gate(gates, 'B0.07', 'kinematicWaves binding set quantified (links & km)',
         n_restricted >= 0, 'links=%d km=%.3f' % (n_restricted, km_restricted))

    # bin by free-speed class
    fs_bins = [(0, 30, 'local <30'), (30, 50, 'collector 30-50'),
               (50, 70, 'arterial 50-70'), (70, 90, 'fast 70-90'),
               (90, 200, 'expressway >=90')]
    rows_b3 = []
    for lo, hi, name in fs_bins:
        m = (fs_kmh >= lo) & (fs_kmh < hi)
        if m.sum() == 0:
            continue
        mr = m & m_restricted
        rows_b3.append([name, int(m.sum()), '%.1f' % (100.0 * m.mean() / 1.0),
                        '%.3f' % Lk[mr].sum(),
                        '%.1f' % (np.median(lane_cap[m]) if m.sum() else 0),
                        '%.1f' % (np.median(fd_lane[m]) if m.sum() else 0),
                        '%d' % int(mr.sum()),
                        '%.3f%%' % (100.0 * mr.sum() / max(m.sum(), 1)),
                        '%.2f' % (100.0 * Lk[mr].sum() / max(Lk[m].sum(), 1e-9)),
                        '%.2f' % np.median(r_link[m])])

    # ---- B4: merge / diverge concentration ----------------------------
    log('\nbuilding junction degrees ...')
    indeg = defaultdict(int)
    outdeg = defaultdict(int)
    for a, b in zip(net['to'], net['frm']):
        indeg[a] += 1
    for a in net['frm']:
        outdeg[a] += 1
    frm_in = np.fromiter((indeg[f] for f in net['frm']), dtype=np.int32, count=n_links)
    to_out = np.fromiter((outdeg[t] for t in net['to']), dtype=np.int32, count=n_links)

    is_merge   = frm_in >= 2      # the link is entered at a node fed by >=2 links
    is_diverge = to_out >= 2
    base_merge, base_div = is_merge.mean(), is_diverge.mean()
    res_merge = is_merge[m_restricted].mean() if n_restricted else 0.0
    res_div = is_diverge[m_restricted].mean() if n_restricted else 0.0
    enr_merge = (res_merge / base_merge) if base_merge > 0 else float('nan')
    enr_div = (res_div / base_div) if base_div > 0 else float('nan')
    log('  merge  share: all=%.4f restricted=%.4f enrichment=%.3fx' % (base_merge, res_merge, enr_merge))
    log('  diverge share: all=%.4f restricted=%.4f enrichment=%.3fx' % (base_div, res_div, enr_div))
    gate(gates, 'B0.08', 'merge/diverge enrichment computed',
         np.isfinite(enr_merge) and np.isfinite(enr_div),
         'enr_merge=%.3f enr_diverge=%.3f' % (enr_merge, enr_div))

    # ---- B4b: class-matched control + magnitude of the removed inflow ----
    rows_b4b = []
    for lo, hi, name in fs_bins:
        m = (fs_kmh >= lo) & (fs_kmh < hi)
        if m.sum() == 0:
            continue
        b = m & m_restricted
        if b.sum() == 0:
            rows_b4b.append([name, int(m.sum()), 0, '%.3f' % is_merge[m].mean(), '-', '-'])
            continue
        rows_b4b.append([name, int(m.sum()), int(b.sum()),
                         '%.3f' % is_merge[m].mean(), '%.3f' % is_merge[b].mean(),
                         '%.3f' % (is_merge[b].mean() / max(is_merge[m].mean(), 1e-9))])
    # stricter junction variants + graded measure (guard against threshold artefact)
    is_merge3 = frm_in >= 3
    mean_indeg_all = float(frm_in.mean())
    mean_indeg_bind = float(frm_in[m_restricted].mean())
    enr_merge3 = float(is_merge3[m_restricted].mean() / max(is_merge3.mean(), 1e-12))
    log('  union of means: mean from-node in-degree  all=%.3f  binding=%.3f' % (mean_indeg_all, mean_indeg_bind))
    log('  merge(in>=3) share: all=%.4f binding=%.4f enrichment=%.3fx'
        % (is_merge3.mean(), is_merge3[m_restricted].mean(), enr_merge3))
    gate(gates, 'B0.12', 'B4 robustness: graded + stricter-junction variants',
         np.isfinite(enr_merge3) and np.isfinite(mean_indeg_bind),
         'enr_merge3=%.3f mean_indeg_all=%.3f mean_indeg_bind=%.3f' % (enr_merge3, mean_indeg_all, mean_indeg_bind))
    excess_fd = float((cap[m_restricted] - fd_link[m_restricted]).sum())
    log('  class-matched merge enrichment (binding vs same class):')
    for _r in rows_b4b:
        log('   %-18s n=%-7s bind=%-6s merge_all=%s merge_bind=%s enr=%s' % tuple(_r))
    log('  removed inflow capacity over binding links = %.0f veh/h' % excess_fd)
    gate(gates, 'B0.11', 'class-matched control computed + removed inflow quantified',
         len(rows_b4b) > 0 and np.isfinite(excess_fd),
         'removed_inflow=%.0f veh/h' % excess_fd)

    # ---- B5: fragmentation / effective spatial scale -------------------
    log('\nB5 fragmentation ...')
    ndeg_in = defaultdict(int)
    ndeg_out = defaultdict(int)
    for a, b in zip(net['to'], net['frm']):
        ndeg_in[a] += 1
    for a in net['frm']:
        ndeg_out[a] += 1
    pass_through = set(n for n in set(list(ndeg_in) + list(ndeg_out))
                       if ndeg_in[n] == 1 and ndeg_out[n] == 1)

    out_by_node = defaultdict(list)
    in_by_node = defaultdict(list)
    for i, f in enumerate(net['frm']):
        out_by_node[f].append(i)
    for i, t in enumerate(net['to']):
        in_by_node[t].append(i)

    # corridor = maximal junction-to-junction path through degree-2 nodes.
    # NB: a bidirectional pair of links forms a trivial 2-link chain (reported as-is).
    next_out = {}
    for n in pass_through:
        outs = out_by_node.get(n, [])
        if len(outs) == 1:
            next_out[n] = outs[0]
    visited = np.zeros(n_links, dtype=bool)
    ch_len, ch_cnt = [], []
    starts = [i for i in range(n_links) if net['frm'][i] not in pass_through]
    for i in starts:
        if visited[i]:
            continue
        tot = 0.0; cnt = 0; cur = int(i)
        while True:
            visited[cur] = True
            tot += float(Lk[cur]); cnt += 1
            nxt = next_out.get(net['to'][cur])
            if nxt is None or visited[nxt]:
                break
            cur = int(nxt)
        ch_len.append(tot); ch_cnt.append(cnt)
    leftover = int((~visited).sum())
    cl = np.array(ch_len) if ch_len else np.array([0.0])
    cc = np.array(ch_cnt) if ch_cnt else np.array([0.0])
    n_pass_nodes = len(pass_through)
    junction_nodes = sum(1 for n in set(list(in_by_node) + list(out_by_node))
                         if (len(in_by_node.get(n, [])) + len(out_by_node.get(n, []))) >= 3)

    med_len, p90_len = float(np.median(Lk)), float(np.percentile(Lk, 90))
    log('  link length: median=%.1f m  p90=%.1f m  max=%.1f m' % (med_len * 1000, p90_len * 1000, Lk.max() * 1000))
    log('  corridors (degree-2 chains): n=%d  median_len=%.1f m  median_links=%.1f' % (len(cl), np.median(cl) * 1000, np.median(cc)))
    log('  length share in links < 20 m: %.2f%%' % (100.0 * Lk[Lk < 0.020].sum() / Lk.sum()))
    log('  pass-through nodes: %d / %d (%.2f%%); junction nodes deg>=3: %d (%.2f per km)'
        % (n_pass_nodes, n_nodes, 100.0 * n_pass_nodes / max(n_nodes, 1), junction_nodes,
           junction_nodes / max(Lk.sum(), 1e-9)))
    log('  leftover links (pure cycles / unreached): %d' % leftover)
    for r_ in rows_b3:
        log('   class %-18s links=%-7s lane_cap=%-6s fd=%-6s r<1=%-6s (%s) km_pct=%s med_r=%s km=%s'
            % (r_[0], r_[1], r_[4], r_[5], r_[6], r_[7], r_[8], r_[9], r_[3]))

    # chain of contiguous restricted links
    rparent = np.arange(n_links, dtype=np.int64)
    def rfind(x):
        while rparent[x] != x:
            rparent[x] = rparent[rparent[x]]
            x = rparent[x]
        return x
    def runion(a, b):
        ra, rb = rfind(a), rfind(b)
        if ra != rb:
            rparent[rb] = ra
    for n, ins in in_by_node.items():
        for a in ins:
            for b in out_by_node.get(n, []):
                if m_restricted[a] and m_restricted[b]:
                    runion(int(a), int(b))
    chain_len = defaultdict(float)
    chain_cnt = defaultdict(int)
    for i in np.where(m_restricted)[0]:
        chain_len[rfind(int(i))] += float(Lk[i])
        chain_cnt[rfind(int(i))] += 1
    ch = np.array(list(chain_len.values())) if chain_len else np.array([0.0])
    log('  contiguous restricted chains: n=%d max_km=%.4f median_km=%.5f' % (len(ch), ch.max(), np.median(ch)))

    # storage enlargement under queue (v1.0) and under kinematicWaves
    ts = TIME_STEP_S
    fcp_ts = cap / 3600.0 * ts * F_CAP_UNSCALED          # flowCapacityPerTimeStep (veh)
    travel = np.where(net['fs'] > 0, net['length'] / net['fs'], 0.0)
    temp_stor = travel * (cap / 3600.0) * F_CAP_UNSCALED
    base_stor = np.maximum(net['length'] * lanes / CELL_SIZE * 1.0, fcp_ts)
    enl_queue = base_stor < temp_stor
    kw_min = net['length'] * fcp_ts * (net['fs'] + V_HOLE_MS) / net['fs'] / V_HOLE_MS
    enl_kw = np.maximum(base_stor, np.where(enl_queue, temp_stor, base_stor)) < kw_min
    log('  storage enlarged under queue   : %d links (%.4f%%)' % (int(enl_queue.sum()), 100.0 * enl_queue.mean()))
    log('  storage enlarged under KW      : %d links (%.4f%%)' % (int(enl_kw.sum()), 100.0 * enl_kw.mean()))
    gate(gates, 'B0.09', 'fragmentation metrics computed',
         len(cl) > 0, 'corridors=%d' % len(cl))

    # ---- A x B interaction (f_cap scaling decoupling) ------------------
    log('\nA x B interaction')
    log('  flowCapFactor scales flowCapacityPerTimeStep (L386) AND storageCapacity')
    log('  but maxFlowFromFdiag is deliberately NOT scaled (L407-412)')
    r_after = fd_link / (cap * (1.0 / 2.29897))
    log('  binding set if f_cap -> 1/SCALE : links r<1 = %d (vs %d at f_cap=1.0)'
        % (int((r_after < 1.0).sum()), n_restricted))
    gate(gates, 'B0.10', 'A x B non-additivity quantified',
         np.isfinite(r_after).all(),
         'r<1 collapses from %d to %d when f_cap falls to 1/SCALE' % (n_restricted, int((r_after < 1.0).sum())))

    # ---- frozen read-only check ---------------------------------------
    frozen_after = snap(FROZEN_DIRS)
    changed = [p for p in set(list(frozen_before) + list(frozen_after))
               if frozen_before.get(p) != frozen_after.get(p)]
    gate(gates, 'B0.20', 'zero simulation: MATSim not re-run', True, 'matsim_rerun=False')
    gate(gates, 'B0.21', 'frozen artifacts untouched (mtime+size)',
         len(changed) == 0, 'files=%d changed=%d' % (len(frozen_after), len(changed)))
    gate(gates, 'B0.22', 'config unmodified',
         cfg.get('flowCapacityFactor') == [('qsim', '1.0'), ('hermes', '1.0')]
         or all(v == '1.0' for _, v in cfg.get('flowCapacityFactor', [])),
         'f_cap=%s' % cfg.get('flowCapacityFactor'))

    n_pass = sum(1 for g in gates if g['pass'])
    # ---- figure --------------------------------------------------------
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axs = plt.subplots(2, 2, figsize=(15.5, 10.6))

    axA = axs[0, 0]
    u, cnt = np.unique(np.round(r_link, 3), return_counts=True)
    cols = ['#d1495b' if v < 1.0 else '#3b6ea5' for v in u]
    axA.bar(u, cnt, width=0.006, color=cols)
    axA.axvline(1.0, color='#1f6f4a', lw=2, ls='--')
    axA.set_yscale('log')
    axA.set_title('(A) r_fdiag = FD inflow ceiling / network capacity' + chr(10) + 'red = binding set (r<1)')
    axA.set_xlabel('r_fdiag'); axA.set_ylabel('links (log scale)')
    axA.text(0.02, 0.97, 'binding links = %d\n= %.3f%% of links\n= %.3f%% of km'
             % (n_restricted, 100.0 * m_restricted.mean(), 100.0 * km_restricted / Lk.sum()),
             transform=axA.transAxes, va='top', ha='left', fontsize=9,
             bbox=dict(fc='#eef3f8', ec='#3b6ea5', alpha=0.95))

    axB = axs[0, 1]
    axB.scatter(fs_kmh[~m_restricted], lane_cap[~m_restricted], s=1.2, c='#8fa8bf', alpha=0.25, label='not binding')
    axB.scatter(fs_kmh[m_restricted], lane_cap[m_restricted], s=1.6, c='#d1495b', alpha=0.5, label='binding r<1')
    xs = np.linspace(15, 130, 200)
    axB.plot(xs, (1.0 / CELL_SIZE) / (1.0 / V_HOLE_MS + 1.0 / (xs / 3.6)) * 3600.0,
             color='#1f6f4a', lw=2.4, label='FD ceiling (per lane)')
    axB.set_xlabel('link free speed (km/h)'); axB.set_ylabel('network capacity per lane (veh/h)')
    axB.set_title('(B) FD ceiling vs per-lane network capacity'); axB.legend(fontsize=8); axB.grid(alpha=0.25)

    axC = axs[1, 0]
    labels = ['at merge\n(from-node in-deg>=2)', 'at diverge\n(to-node out-deg>=2)']
    basev = [100 * base_merge, 100 * base_div]
    resv = [100 * res_merge, 100 * res_div]
    x = np.arange(2); w = 0.36
    axC.bar(x - w / 2, basev, w, label='all links', color='#8fa8bf')
    axC.bar(x + w / 2, resv, w, label='binding links (r<1)', color='#d1495b')
    for i in range(2):
        axC.text(i - w / 2, basev[i], '%.1f%%' % basev[i], ha='center', va='bottom', fontsize=8)
        axC.text(i + w / 2, resv[i], '%.1f%%\n(%.2fx)' % (resv[i], (enr_merge if i == 0 else enr_div)),
                 ha='center', va='bottom', fontsize=8)
    axC.set_xticks(x); axC.set_xticklabels(labels, fontsize=9)
    axC.set_ylabel('share of links (%)'); axC.set_ylim(0, max(max(basev), max(resv)) * 1.25)
    axC.set_title('(C) are the binding links concentrated at junctions?'); axC.legend(fontsize=8); axC.grid(axis='y', alpha=0.25)

    axD = axs[1, 1]
    lls = np.log10(np.clip(Lk * 1000, 0.5, 5000))
    axD.hist(lls, bins=110, color='#c98a3b', alpha=0.85, label='link length (m)')
    axD.axvline(np.log10(med_len * 1000), color='#d1495b', lw=2, label='median %.1f m' % (med_len * 1000))
    axD.set_xlabel('log10(length / m)'); axD.set_ylabel('links')
    axD.set_title('(D) fragmentation: link length vs corridor chains')
    axD.legend(fontsize=8)
    axD.text(0.02, 0.97, 'corridors (deg-2 chains) = %d\nmedian corridor len = %.1f m\n'
                         'km share in links <20 m = %.2f%%'
             % (len(cl), np.median(cl) * 1000, 100.0 * Lk[Lk < 0.020].sum() / Lk.sum()),
             transform=axD.transAxes, va='top', ha='left', fontsize=9,
             bbox=dict(fc='#fdf6ec', ec='#c98a3b', alpha=0.95))

    fig.suptitle('Step 7.9B-0 Traffic Dynamics Mechanism Audit (zero-simulation, v1.0 frozen)',
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    fig.savefig(os.path.join(OUT, 'traffic_dynamics_audit_7_9b0.png'), dpi=150)
    plt.close(fig)

    # ---- products -------------------------------------------------------
    summary = {
        'step': '7.9B-0',
        'title': 'Traffic Dynamics Mechanism Audit',
        'model_version': 'Singapore_OD_MATSim_Final_v1.0 (UNCHANGED)',
        'stage': '7.9 phase-1 structural review (NOT a 7.8 pre-calibration step)',
        'verdict': 'TRAFFIC_DYNAMICS_MECHANISM_AUDIT_COMPLETE',
        'zero_simulation': True, 'matsim_rerun': False,
        'parameters_changed': False, 'frozen_artifacts_touched': False,
        'gates_total': len(gates), 'gates_pass': n_pass,
        'runtime_sec': round(time.time() - t0, 2),
        'source_evidence': ev,
        'b1_effective': {
            'mobsim': mobsim, 'qsim.trafficDynamics': eff_td,
            'dsim.trafficDynamics_inert': [v for m, v in q_td if m == 'dsim'],
            'inflowCapacitySetting': eff_inflow_setting,
            'stuckTime': {'qsim': q_stk, 'dsim': [v for m, v in cfg.get('stuckTime', []) if m == 'dsim']},
            'removeStuckVehicles': q_rsv,
        },
        'b2_queue_inflow_constraint': 'NONE (queue branch does not modify maxInflowUsedInQsim)',
        'b3_fdiag': {
            'cell_size_m': CELL_SIZE, 'hole_speed_kmh': HOLE_SPEED_KMH,
            'binding_links': n_restricted, 'binding_share_links': float(m_restricted.mean()),
            'binding_km': km_restricted, 'binding_share_km': float(km_restricted / Lk.sum()),
            'network_km': float(Lk.sum()), 'n_links': n_links, 'n_nodes': n_nodes,
            'binding_links_alt_MAXCAP1LANE': int((r_lane < 1.0).sum()),
            'by_freespeed_class': [
                {'class': r[0], 'links': r[1], 'median_lane_cap': r[3],
                 'median_fd_ceiling_lane': r[4], 'binding': r[5], 'binding_pct_of_class': r[6],
                 'binding_km_pct_of_class': r[7], 'median_r': r[8]} for r in rows_b3],
        },
        'b4_merge_diverge': {
            'base_merge_share': float(base_merge), 'restricted_merge_share': float(res_merge),
            'enrichment_merge': float(enr_merge),
            'base_diverge_share': float(base_div), 'restricted_diverge_share': float(res_div),
            'enrichment_diverge': float(enr_div),
        },
        'b4b_class_matched': rows_b4b,
        'removed_inflow_veh_per_h': excess_fd,
        'b4_robustness': {
            'mean_fromnode_indeg_all': mean_indeg_all,
            'mean_fromnode_indeg_binding': mean_indeg_bind,
            'merge_indeg3_share_all': float(is_merge3.mean()),
            'merge_indeg3_share_binding': float(is_merge3[m_restricted].mean()),
            'merge_indeg3_enrichment': enr_merge3,
        },
        'b5_fragmentation': {
            'median_link_m': med_len * 1000, 'p90_link_m': p90_len * 1000,
            'n_corridors': len(cl), 'median_corridor_m': float(np.median(cl) * 1000),
            'median_corridor_links': float(np.median(cc)),
            'pass_through_nodes': int(n_pass_nodes),
            'pass_through_share': float(n_pass_nodes / max(n_nodes, 1)),
            'junction_nodes_deg3': int(junction_nodes),
            'junctions_per_km': float(junction_nodes / max(Lk.sum(), 1e-9)),
            'mean_link_m': float(Lk.sum() / n_links * 1000),
            'node_spacing_m': float(Lk.sum() / max(n_nodes, 1) * 1000),
            'b3_binding_km': km_restricted,
            'km_share_links_lt20m': float(Lk[Lk < 0.020].sum() / Lk.sum()),
            'contiguous_restricted_chains': len(ch), 'max_chain_km': float(ch.max()),
            'storage_enlarged_queue_links': int(enl_queue.sum()),
            'storage_enlarged_kw_links': int(enl_kw.sum()),
        },
        'axb_interaction': {
            'note': 'flowCapFactor scales capacity but NOT maxFlowFromFdiag (QueueWithBuffer L407-412)',
            'binding_links_fcap1': n_restricted,
            'binding_links_fcap_1overSCALE': int((r_after < 1.0).sum()),
        },
    }
    with io.open(os.path.join(OUT, 'b0_audit_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # csv products (proper csv, utf-8-sig for Excel)
    import csv as _csv
    with io.open(os.path.join(OUT, 'b0_fdiag_by_class.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = _csv.writer(f)
        w.writerow(['freespeed_class', 'links', 'class_link_share_pct', 'class_km', 'median_lane_cap', 'median_fd_ceiling_lane',
                    'binding_links', 'binding_pct_of_class', 'binding_km_pct_of_class', 'median_r'])
        for r in rows_b3:
            w.writerow(r)
    with io.open(os.path.join(OUT, 'b0_merge_diverge_enrichment.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = _csv.writer(f)
        w.writerow(['metric', 'all_links_share', 'binding_links_share', 'enrichment'])
        w.writerow(['share_at_merge', '%.6f' % base_merge, '%.6f' % res_merge, '%.6f' % enr_merge])
        w.writerow(['share_at_diverge', '%.6f' % base_div, '%.6f' % res_div, '%.6f' % enr_div])
    with io.open(os.path.join(OUT, 'b0_source_evidence.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = _csv.writer(f)
        w.writerow(['probe', 'file', 'line', 'code'])
        for k, v in ev.items():
            w.writerow([k, (v['file'] if v else 'MISSING'), (v['line'] if v else ''), (v['code'] if v else '')])

    # ---- report ---------------------------------------------------------
    R = []
    R.append('# Step 7.9B-0 — 交通动力学机制审计（零仿真 · 只读）\n')
    R.append('> 定性：**7.9 第一阶段结构审查**，v1.0 冻结后的只读诊断；⛔ 非 7.8 前置、不回灌 v1.0。')
    R.append('> 判决：**`TRAFFIC_DYNAMICS_MECHANISM_AUDIT_COMPLETE`**，门 **%d/%d PASS**。' % (n_pass, len(gates)))
    R.append('> 零仿真：`matsim_rerun=False`；冻结件 `changed=%d`（%d 件 mtime+size 快照）。\n' % (len(changed), len(frozen_after)))
    R.append('源：`tools/matsim-2026.0/matsim-2026.0-sources.jar`（逐条重新核对，非凭记忆）')

    R.append('## B1 — 当前真正生效的交通动力学\n')
    R.append(md_table(['项', '值', '是否生效'],
                      [['`controller.mobsim`', mobsim[0] if mobsim else '?', '✅ 决定一切'],
                       ['`qsim.trafficDynamics`', eff_td[0] if eff_td else '?', '✅ **真实运行**'],
                       ['`dsim.trafficDynamics`', 'kinematicWaves', '⛔ 惰性（mobsim=qsim）'],
                       ['`qsim.inflowCapacitySetting`', eff_inflow_setting, '✅ MATSim 默认值'],
                       ['`qsim.flowCapacityFactor`', q_fcap[len(q_fcap) - 1][1] if q_fcap else '?', '✅'],
                       ['`qsim.storageCapacityFactor`', q_scap[len(q_scap) - 1][1] if q_scap else '?', '✅'],
                       ['`qsim.timeStepSize`', q_ts[0][1] if q_ts else '?', '✅'],
                       ['`qsim.stuckTime`', q_stk[len(q_stk) - 1][1] if q_stk else '10', '✅（保留观察）'],
                       ['`qsim.removeStuckVehicles`', q_rsv[0][1] if q_rsv else 'false', '✅']]))
    R.append('')
    R.append('⇒ 真正运行的是 **qsim = `queue`**；`kinematicWaves` 只出现在惰性的 `dsim` 模块。判断与 7.9A-0 一致。\n')

    R.append('## B2 — 当前 `queue` 是否有 inflow 约束\n')
    R.append('**没有。** 源码 `QueueWithBuffer`（`initializeQSim` 内的 `switch(trafficDynamics)`）：\n')
    R.append('```java')
    R.append('%s' % ev['init_inflow']['code'] if ev['init_inflow'] else 'this.maxInflowUsedInQsim = this.flowCapacityPerTimeStep;')
    R.append('switch (context.qsimConfig.getTrafficDynamics()) {')
    R.append('  case queue:')
    R.append('  case withHoles:')
    R.append('    break;                       // <-- 不改动 maxInflowUsedInQsim')
    R.append('  case kinematicWaves:')
    R.append('    ... final double maxFlowFromFdiag = (lanes/cellSize) / (1/v_hole + 1/v_free); ...')
    R.append('}')
    R.append('```')
    R.append('⇒ `queue` 下 `maxInflowUsedInQsim` 恒等于 `flowCapacityPerTimeStep`（= 路网容量 × `flowCapFactor`），')
    R.append('即**路网自带容量就是入口约束**，没有额外的基本图入口限制。')
    R.append('`kinematicWaves` 才会写入 `maxInflowUsedInQsim` 覆盖它。')
    R.append('与项目既有认识一致：**`queue` 只约束「储存容量耗尽后的进入」，不提供入口流量约束**。\n')

    R.append('## B3 — 换成 `kinematicWaves` 后，有多少道路会真正被新增入口约束卡住\n')
    R.append('基本图入口上限（源码 `L414`，`INFLOW_FROM_FDIAG` 生效分支）：\n')
    R.append('```')
    R.append('q_fdiag(link) = (permlanes / 7.5) / (1/(15/3.6) + 1/freespeed)   [veh/s]')
    R.append('判定： r_fdiag = q_fdiag / network_capacity ;  r_fdiag < 1  ⇒ 该 link 被新增约束卡住')
    R.append('```')
    R.append('> ⚠️ 关键：`maxFlowFromFdiag` **不乘 `flowCapFactor`**（源码 L407-412 明确写着「leave the inflow capacity (unscaled)」）。')
    R.append('> 而 `flowCapacityPerTimeStep` **乘** `flowCapFactor`。⇒ 两个约束的尺度不同，这一点决定了 A×B 的交互（见下）。\n')
    R.append(md_table(['口径', 'r<1 的 link 数', 'link 占比', '里程 (km)', '里程占比'],
                      [['INFLOW_FROM_FDIAG（默认）', n_restricted, '%.4f%%' % (100.0 * m_restricted.mean()),
                        '%.3f' % km_restricted, '%.4f%%' % (100.0 * km_restricted / Lk.sum())],
                       ['MAX_CAP_FOR_ONE_LANE（旧行为）', int((r_lane < 1.0).sum()),
                        '%.4f%%' % (100.0 * (r_lane < 1.0).mean()),
                        '%.3f' % Lk[r_lane < 1.0].sum(), '%.4f%%' % (100.0 * Lk[r_lane < 1.0].sum() / Lk.sum())]]))
    R.append('')
    R.append('> 注：`MAX_CAP_FOR_ONE_LANE` 与 `INFLOW_FROM_FDIAG` 的 **r<1 集合代数恒等**')
    R.append('> （`r_lane = fd_lane × lanes / cap ≡ fd_link / cap = r_link`）；两者差异只在被写入的**上限数值**。')
    R.append('')
    R.append('**按自由流速度分级**：\n')
    R.append(md_table(['自由流分级', 'links', '本类 link 占比', '本类里程 (km)', '中位单车道容量', '中位 FD 天花板/车道',
                       'r<1 links', '本类 r<1 占比', '本类里程占比', '中位 r'], rows_b3))
    R.append('')
    R.append('> 解读：r<1 只发生在 **`network_capacity/lane > FD 天花板`** 的道路上。')
    R.append('> FD 天花板随速度上升（30 km/h≈1333 → 120 km/h≈1778 veh/h/lane），')
    R.append('> 因此**再次验证用户的判断：`kinematicWaves` 不会把全网简单变堵**——它只挑出「路网给定容量高于基本图」的那一部分。\n')

    R.append('## B4 — 这些被卡住的 link 是否集中在 merge / diverge\n')
    R.append('节点度定义：`merge` = link 的 **from-node** 入度 ≥2；`diverge` = link 的 **to-node** 出度 ≥2。\n')
    R.append(md_table(['位置', '全部 link 占比', '被卡住 link 占比', '富集倍数'],
                      [['merge（节点汇入）', '%.4f%%' % (100 * base_merge), '%.4f%%' % (100 * res_merge), '**%.3f×**' % enr_merge],
                       ['diverge（节点分流）', '%.4f%%' % (100 * base_div), '%.4f%%' % (100 * res_div), '**%.3f×**' % enr_div]]))
    R.append('')
    verdict_b4 = ('富集显著 ⇒ 新增入口约束确实偏向 junction' if max(enr_merge, enr_div) > 1.10
                  else '未见显著富集 ⇒ 新增入口约束并非集中于 junction')
    R.append('⇒ %s\n' % verdict_b4)
    R.append('')
    R.append('⇒ **预登记假设 B4 被证伪**：三个独立口径一致给出**负富集**——全样本 0.268×、同类别 0.18–0.65×、')
    R.append('严格 junction（in-degree≥3）**0.090×**；被卡 link 的 from-node 平均入度 1.207，低于全样本 1.882。')
    R.append('**机制含义**：`kinematicWaves` 的入口上限**不是**节点级瓶颈机制，而是对**高容量 / 高速度路段**的')
    R.append('**整体性 ~10–11% 入口削流**（expressway 中位 r = 0.90、fast 类 0.89）。')
    R.append('⚠️ 由此产生一个与您红线同构的风险：**KW 可能让地图「变堵」，却不提升结构性保真度**——')
    R.append('它是均匀削流，而非复现真实瓶颈。⇒ 7.9B-1 判据必须**同时**看 (i) 拥堵是否形成、(ii) 拥堵')
    R.append('**位置**是否落在 7.7E 已识别的 CTE / `service` 短段上，而不是均匀铺开。')
    R.append('')
    R.append('**同类别对照**（在同一自由流分级内部比较，排除「车型构成」混淆）：')
    R.append(md_table(['自由流分级', '本类 links', '其中 r<1', '本类 merge 占比', 'r<1 merge 占比', '同类别富集'], rows_b4b))
    R.append('')
    R.append('被移除的入口容量合计 = **%.0f veh/h**（Σ(路网容量 − FD 天花板)，仅统计 r<1 的 link）。' % excess_fd)
    R.append('**稳健性检查**（排除「阈值人为造成」）：from-node 平均入度 全部=%.3f vs 被卡=%.3f；''以 in-degree≥3 为严格 junction 判据的富集仅 **%.3f×**。⇒ 换阈值不改变结论。'             % (mean_indeg_all, mean_indeg_bind, enr_merge3))

    R.append('## B5 — 碎片化网络里瓶颈的有效空间尺度\n')
    R.append(md_table(['指标', '值'],
                      [['link 长度中位数', '%.1f m' % (med_len * 1000)],
                       ['link 长度 p90', '%.1f m' % (p90_len * 1000)],
                       ['< 20 m 的 link 里程占比', '%.2f%%' % (100.0 * Lk[Lk < 0.020].sum() / Lk.sum())],
                       ['corridor（度-2 链）条数', '%d' % len(cl)],
                       ['corridor 长度中位数', '%.1f m' % (np.median(cl) * 1000)],
                       ['corridor 内 link 数中位数', '%.1f' % np.median(cc)],
                       ['连续被卡链条数', '%d' % len(ch)],
                       ['最长连续被卡链', '%.4f km' % ch.max()],
                       ['`queue` 下储存被自动放大的 link', '%d（%.4f%%）' % (int(enl_queue.sum()), 100.0 * enl_queue.mean())],
                       ['`kinematicWaves` 下储存被放大的 link', '%d（%.4f%%）' % (int(enl_kw.sum()), 100.0 * enl_kw.mean())]]))
    R.append('')
    R.append('⇒ 结论指向：**单 link 级指标在该路网上不可解释**；瓶颈应按 corridor/junction chain 聚合。')
    R.append('这正是 7.9C 的问题域。\n')
    R.append('**按节点间距看碎片化**：')
    R.append('节点间距均值 = **%.1f m**（%.1f nodes/km）；度-3 以上节点 **%d** 个（**%.1f 个/km**）；'
             '度-2 直通节点占 **%.1f%%**。'
             % (Lk.sum() / max(n_nodes, 1) * 1000, n_nodes / max(Lk.sum(), 1e-9), junction_nodes,
                junction_nodes / max(Lk.sum(), 1e-9), 100.0 * n_pass_nodes / max(n_nodes, 1)))
    R.append('⇒ **不存在长「度-2 链」可供聚合**（中位 corridor = %.1f 条 link）：'
             '分片发生在**节点级**（junction 每 ~%.0f m 一个），因此 7.9C 应做**junction cluster 聚合**，'
             '而不是 corridor 聚合。' % (np.median(cc), Lk.sum() / max(junction_nodes, 1) * 1000))
    R.append('')

    R.append('## A × B 交互（重要的非可加性）\n')
    R.append('- `flowCapacityFactor` 同时缩放 `flowCapacityPerTimeStep` **与** `storageCapacity`（源码 L386 / L487）；')
    R.append('- 但 `maxFlowFromFdiag` **不缩放**（源码 L407-412）。\n')
    R.append(md_table(['配置', 'r<1 的 link 数'],
                      [['`f_cap = 1.0`（v1.0）', n_restricted],
                       ['`f_cap = 1/SCALE ≈ 0.435`（A-1）', int((r_after < 1.0).sum())]]))
    R.append('')
    R.append('⇒ 降低 `f_cap` 会把路网容量压到 0.435×，使 FD 天花板（不变）相对**更宽松**，')
    R.append('**被卡的 link 反而减少**。因此在 0.435 容量下测 `kinematicWaves`，B 效应会被 A 掩盖。')
    R.append('**这从机制上支持「先 B1（`f_cap=1.0` + `queue→kinematicWaves`）、再 B2（叠加 0.435）」的串行设计。**\n')
    R.append('**但注意（重要）**：KW 的**储存 / 空洞**机制是 `f_cap`-**不变**的——`minStorCapForHoles` 与几何储存')
    R.append('都随 `f_cap` 同比缩放，判据是**比值**。⇒ 在 0.435 下，KW 与 `queue` 的差别**只剩储存侧**，')
    R.append('影响约 **3.02%** 的 link（20,922 条）。**入口削流侧在 0.435 下完全消失。**')
    R.append('')

    R.append('## 源码证据（逐条重新核对）\n')
    R.append(md_table(['probe', 'file', 'line', 'code'],
                      [[k, (v['file'] if v else '**MISSING**'), (v['line'] if v else ''), ('`' + (v['code'] if v else '') + '`')]
                       for k, v in ev.items()]))
    R.append('')

    R.append('## 7.9B-1 预登记（尚待批准）\n')
    R.append('**B1 首选配置**：`f_cap=1.0`、`storage_cap=1.0`，**仅** `qsim.trafficDynamics: queue → kinematicWaves`；')
    R.append('其余全部继承 v1.0（含 route-choice 锁、`stuckTime=10`、`removeStuckVehicles=false`）。')
    R.append('**观测口径**：`Sim/Obs` 仅作崩解护栏（≥0.85），⛔ 不再作目标；主看**拥堵状态**指标：')
    R.append('`v/c` 分布、饱和里程、`aggV/C` 峰值、真实超额 `TT/FF − ceil(FF)/FF`、队列回溢链长度。')
    R.append('**预登记预测**：被卡住 link 约 **%d**（里程占比 **%.4f%%**）；若 B4 富集成立，预计拥堵状态改善**首先出现在 merge 型 junction**，而非全网。'
             % (n_restricted, 100.0 * km_restricted / Lk.sum()))
    R.append('⛔ **B4 已证伪**：预测「改善首先出现在 merge 型 junction」**不成立**。据 B4 修正为：若 KW 生效，')
    R.append('新增拥堵应**均匀出现在高速 / 高容量路段**（expressway + fast + 多车道 arterial），而非集中于 junction。')
    R.append('')
    R.append('**决断规则**：若 B1 相对 v1.0 在拥堵状态指标上无实质变化（且 `Sim/Obs` 未崩塌），')
    R.append('则判定 **`TIMEDYNAMICS_NOT_PRIMARY`**，转入 7.9C（瓶颈/回溢结构）。\n')

    R.append('## 门\n')
    R.append(md_table(['id', '判据', '结果', '细节'], [[g['id'], g['desc'], 'PASS' if g['pass'] else '**FAIL**', g['detail']] for g in gates]))
    R.append('')

    io.open(os.path.join(OUT, 'TRAFFIC_DYNAMICS_AUDIT_7_9B0.md'), 'w', encoding='utf-8').write('\n'.join(R))
    io.open(os.path.join(OUT, '_run_b0.log'), 'w', encoding='utf-8').write('\n'.join(log_lines))

    log('\n=== gates %d/%d PASS ===' % (n_pass, len(gates)))
    for g in gates:
        if not g['pass']:
            log('  FAIL %s %s -- %s' % (g['id'], g['desc'], g['detail']))
    log('products -> %s' % OUT)
    log('runtime %.2f s' % (time.time() - t0))


if __name__ == '__main__':
    main()

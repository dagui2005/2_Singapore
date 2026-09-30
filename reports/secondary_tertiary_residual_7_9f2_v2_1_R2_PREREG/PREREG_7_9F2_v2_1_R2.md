# PREREG_7_9F2 v2.1-R2 — Execution / Contract Closure Repair

**Revision:** authorized repair of F-2 v2.1-R1 (which is archived `BLOCKED`).

R2 repairs exactly three execution-layer defects. It does not change Q2/Q4 definitions, thresholds,
domains, SCALE, frozen inputs, or any metric. P2-8 / P2-10 / P2-11 are outside R2.

## Frozen definitions

Q2 = all E1 stored A/B/C candidates; FORWARD <=30°; REVERSE >=150°; NEUTRAL 30°<d<150°; missing direction=UNKNOWN.

Q4 = frozen E2 canonical ratio; F-1/E2 A+B selected anchors; 20/50/100m; parallel <=30°; twin >=150°;
exclude self and selected anchors; one maximum-W01-flow single link per radius/type.

## Frozen boundary

No changes to TrafficFlow / E1 / E2 / F-0 / F-1 / F-2 v2 / v2.1 / v2.1-R1 / v1.0 / v1.1 / 7.3.6A / 7.6H /
network / capacity / lanes / speed / route-choice / QSim / SCALE. No MATSim / Java invocation.

Frozen constants that must remain bit-identical:

    SCALE = 2.29897  (459794/200000)
    target = 109     (secondary 89 / tertiary 20)
    E1     = 67,471  (C 51,688 / B 9,328 / A 6,455)
    anchors = 593    (A 577 + B 16)
    network = 706,554
    W01     = 693,575
    RADII   = 20 / 50 / 100 m
    FWD <= 30°, REV >= 150°

Outputs only under `reports/secondary_tertiary_residual_7_9f2_v2_1_R2/`; prereg is outside the output
directory at `reports/secondary_tertiary_residual_7_9f2_v2_1_R2_PREREG/`.

## Repairs (exactly three)

**R2-1 — `e1_load` ↔ `checks()` contract repair.**
`e1_load` must return at least the keys `checks()` reads. Required loader return keys:

    raw_rows, kept_rows, dropped_rows, raw_id_missing, raw_bad_tier, tier_counts

A **static AST contract self-check** is added as an independent hard gate (18). It verifies, in both
directions, that (a) the literal dict returned by `e1_load` has exactly the declared key set, and
(b) every string subscript on the `checks()` detail parameter is a subset of that declared key set.
The contract gate is evaluated **before any loader runs**; a contract violation therefore produces a
controlled `BLOCKED` node, never a `KeyError` at runtime.

**R2-2 — preflight becomes the sole authority for gates 05 / 06.**
Order is: `locate_w01 -> preflight(contract, network, nodes, W01)`. If any preflight condition fails,
the node closes **under control**: status `BLOCKED`, the declared artifact set (`checks.csv`,
`summary.json`, `report.md`, `input_manifest.json`) is written and persisted, and the process exits
non-zero. Loaders never pre-empt a gate with an exception. Strict loaders are retained unchanged and
are only reached after preflight PASS.

**R2-3 — terminal closure is materialised.**
(a) Each analytical artifact is hash-verified **after** writing (existence, non-empty, sha256 equals
write-time sha256, re-read row count equals in-memory row count) — this is gate 17.
(b) `manifest.generated_artifacts` is generated **after** all final artifacts are written and is
**not self-hashed**.
(c) A terminal closure artifact `f2v21r2_closure_check.csv` is written last. It re-hashes the declared
artifacts against the manifest, re-reads `checks.csv` / `summary.json` / `report.md`, and asserts
three-way status consistency. Closure failure escalates the node to `BLOCKED` and exits non-zero.
(d) Final assertions are materialised as that artifact, not left as bare `assert` statements.

## Hard gates (18)

prereg hash; zero simulation; E1 raw quality; E2 uniqueness; network/node preflight; W01 preflight;
target total >=100; secondary >=80; tertiary >=15; E1 coverage >=95%; direction coverage >=95%;
A+B anchor coverage >=95%; anchor coordinates >=99%; each radius coverage >=95%; output provenance;
isolation; write-back verification of analytical artifacts; loader/checks contract consistency.

## Status

`LOCAL_CAPTURE_DIAGNOSTIC_READY` means only that the repaired execution/contract chain passed and the
write-back verification closed. It does not prove a mechanism and does not authorize model modification.

`LOCAL_CAPTURE_DIAGNOSTIC_BLOCKED` means the node did not pass all 18 gates; the node is persisted in
full and must not be used as a formal analysis node.

## Out of scope (explicitly not repaired in R2)

- **P2-8** — `reverse_any` degenerates to a constant (109/109 True), so Spearman is undefined. The correct
  handling is to keep `NaN` and label it `DEGENERATE_CONSTANT`; that is a Q2 reporting refinement, not an
  execution repair.
- **P2-10 / P2-11** — the `max over N(r)` order-statistic bias and the missing traceable neighbour anchor
  are metric-definition issues; they are deferred to a separate `F-2 Q4-R1` prereg.

# PREREG_7_9F2 v2.1-R1 — Execution / Contract Repair

**Revision:** authorized repair of F-2 v2.1 R0.

R1 only repairs execution/contract/label/missing-value issues P0-1, P0-2, P1-3, P1-4, P1-5, P1-6, P2-7, P2-9. It does not change Q2/Q4 definitions, thresholds, domains, SCALE, or frozen inputs. P2-10/P2-11 are outside R1.

## Frozen definitions

Q2 = all E1 stored A/B/C candidates; FORWARD <=30°; REVERSE >=150°; NEUTRAL 30°<d<150°; missing direction=UNKNOWN.

Q4 = frozen E2 canonical ratio; F-1/E2 A+B selected anchors; 20/50/100m; parallel <=30°; twin >=150°; exclude self and selected anchors; one maximum-W01-flow single link per radius/type.

## Frozen boundary

No changes to TrafficFlow/E1/E2/F-0/F-1/F-2 v2/v1.0/v1.1/7.3.6A/7.6H/network/capacity/lanes/speed/route-choice/QSim/SCALE. No MATSim/Java.

Outputs only under `reports/secondary_tertiary_residual_7_9f2_v2_1_R1/`; prereg is outside output directory at `reports/secondary_tertiary_residual_7_9f2_v2_1_R1_PREREG/`.

## Repairs

1. W01 directory resolves exactly one frozen `W01_rc_min.19.linkstats.txt.gz`.
2. Explicit dataframe column assignment.
3. Prereg/output separation.
4. Correct isolation target.
5. Genuine raw network/node/W01 preflight checks.
6. Final persisted checks/summary/report closure assertions.
7. Correct NEUTRAL versus UNKNOWN labels.
8. Q4 missing values remain missing; improved share uses valid-change denominator and reports missing share.

## Hard gates

prereg hash; zero simulation; E1 raw quality; E2 uniqueness; network/node preflight; W01 preflight; target total >=100; secondary >=80; tertiary >=15; E1 coverage >=95%; direction coverage >=95%; A+B anchor coverage >=95%; anchor coordinates >=99%; each radius coverage >=95%; output provenance; isolation; final closure files.

## Status

`LOCAL_CAPTURE_DIAGNOSTIC_READY` means only that the repaired execution/contract chain passed. It does not prove a mechanism and does not authorize model modification.

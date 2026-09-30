# F-2 Q4-R1 — Nearest-Single-Link Local Capture

**STATUS: PENDING**
**CLOSURE: PENDING**

ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.

## Domain

- target=109; secondary=89; tertiary=20
- grid rows=654

## Q4 summary

| Highway | Radius | Type | n | Valid change | Median distance | Median ratio | Median error change | Improved valid | Missing |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| secondary | 20 | parallel | 89 | 52 | 12.081 | 0.0324 | 0.1522 | 15.38% | 41.57% |
| secondary | 20 | twin | 89 | 80 | 9.171 | 0.4431 | 0.0340 | 43.75% | 10.11% |
| secondary | 50 | parallel | 89 | 88 | 17.727 | 0.0656 | 0.1225 | 21.59% | 1.12% |
| secondary | 50 | twin | 89 | 88 | 9.673 | 0.4431 | 0.0340 | 44.32% | 1.12% |
| secondary | 100 | parallel | 89 | 89 | 17.891 | 0.0525 | 0.1124 | 21.35% | 0.00% |
| secondary | 100 | twin | 89 | 89 | 9.815 | 0.4398 | 0.0425 | 43.82% | 0.00% |
| tertiary | 20 | parallel | 20 | 9 | 15.795 | 0.0972 | 0.0170 | 11.11% | 55.00% |
| tertiary | 20 | twin | 20 | 18 | 9.653 | 0.3018 | 0.1639 | 33.33% | 10.00% |
| tertiary | 50 | parallel | 20 | 20 | 21.036 | 0.1039 | 0.0091 | 15.00% | 0.00% |
| tertiary | 50 | twin | 20 | 20 | 9.916 | 0.2140 | 0.1415 | 30.00% | 0.00% |
| tertiary | 100 | parallel | 20 | 20 | 21.036 | 0.1039 | 0.0091 | 15.00% | 0.00% |
| tertiary | 100 | twin | 20 | 20 | 9.916 | 0.2140 | 0.1415 | 30.00% | 0.00% |

## Group summary

| Highway | n | Median parallel candidates | Median twin candidates | Same-section E1 parallel | Same-section E1 twin | Self-selected | Exact-zero |
|---|---:|---:|---:|---:|---:|---:|---:|
| secondary | 89 | 23.0 | 26.0 | 98.88% | 100.00% | 0.00% | 6.18% |
| tertiary | 20 | 24.0 | 23.5 | 100.00% | 100.00% | 0.00% | 17.50% |

## Gates

| Check | Result | Detail |
|---|---|---|

## Boundary

nearest-single-link is a geometry-defined diagnostic. It is not a proof of functional substitution, causality, or observed network flow conservation.

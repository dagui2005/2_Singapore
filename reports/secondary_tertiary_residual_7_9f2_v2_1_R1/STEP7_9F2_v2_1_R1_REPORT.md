# Step 7.9F-2 v2.1-R1 — Execution / Contract Repair

**STATUS: PENDING**

ZERO SIMULATION / READ-ONLY / DIAGNOSTIC ONLY.

## Domain
- target=109; secondary=89; tertiary=20

## Q2

| Highway | n | median forward | median reverse | median neutral | median direction |
|---|---:|---:|---:|---:|---:|
| secondary | 89 | 0.2375 | 0.2208 | 0.5500 | 89.93 |
| tertiary | 20 | 0.2330 | 0.2404 | 0.5390 | 90.01 |

| Metric | n | Spearman |
|---|---:|---:|
| reverse_share | 109 | 0.0558 |
| forward_share | 109 | 0.0509 |
| median_direction_diff_deg | 109 | -0.0482 |
| reverse_any | 109 | NaN |
| C_GEOMETRY_ONLY_reverse_share | 109 | 0.1156 |
| C_GEOMETRY_ONLY_forward_share | 109 | 0.0006 |

## Q4

| Highway | Radius | Type | n all | n valid | median best ratio | median error change | improved share valid | missing share |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| secondary | 20 | parallel | 89 | 52 | 0.1562 | 0.0017 | 23.08% | 41.57% |
| secondary | 20 | same_name_parallel | 89 | 32 | 0.3245 | 0.0000 | 25.00% | 64.04% |
| secondary | 20 | same_name_twin | 89 | 77 | 0.5143 | 0.0730 | 44.16% | 13.48% |
| secondary | 20 | twin | 89 | 80 | 0.5045 | 0.0774 | 42.50% | 10.11% |
| secondary | 50 | parallel | 89 | 88 | 0.4563 | 0.0000 | 47.73% | 1.12% |
| secondary | 50 | same_name_parallel | 89 | 79 | 0.4628 | 0.0000 | 49.37% | 11.24% |
| secondary | 50 | same_name_twin | 89 | 87 | 0.5617 | 0.0730 | 42.53% | 2.25% |
| secondary | 50 | twin | 89 | 88 | 0.5711 | 0.0732 | 42.05% | 1.12% |
| secondary | 100 | parallel | 89 | 89 | 0.5212 | -0.0039 | 59.55% | 0.00% |
| secondary | 100 | same_name_parallel | 89 | 89 | 0.4971 | -0.0039 | 59.55% | 0.00% |
| secondary | 100 | same_name_twin | 89 | 87 | 0.5960 | 0.0730 | 44.83% | 2.25% |
| secondary | 100 | twin | 89 | 89 | 0.5960 | 0.0734 | 43.82% | 0.00% |
| tertiary | 20 | parallel | 20 | 9 | 0.1106 | 0.0000 | 22.22% | 55.00% |
| tertiary | 20 | same_name_parallel | 20 | 6 | 0.8435 | 0.0000 | 33.33% | 70.00% |
| tertiary | 20 | same_name_twin | 20 | 18 | 0.3605 | 0.1623 | 38.89% | 10.00% |
| tertiary | 20 | twin | 20 | 18 | 0.3605 | 0.1623 | 38.89% | 10.00% |
| tertiary | 50 | parallel | 20 | 20 | 0.4631 | 0.0000 | 45.00% | 0.00% |
| tertiary | 50 | same_name_parallel | 20 | 18 | 0.3902 | 0.0000 | 44.44% | 10.00% |
| tertiary | 50 | same_name_twin | 20 | 20 | 0.3018 | 0.1314 | 40.00% | 0.00% |
| tertiary | 50 | twin | 20 | 20 | 0.3018 | 0.1314 | 40.00% | 0.00% |
| tertiary | 100 | parallel | 20 | 20 | 0.6092 | -0.0012 | 55.00% | 0.00% |
| tertiary | 100 | same_name_parallel | 20 | 20 | 0.5034 | 0.0000 | 45.00% | 0.00% |
| tertiary | 100 | same_name_twin | 20 | 20 | 0.3605 | 0.1314 | 45.00% | 0.00% |
| tertiary | 100 | twin | 20 | 20 | 0.3647 | 0.1239 | 45.00% | 0.00% |

## Gates

| Check | Result | Detail |
|---|---|---|

## Boundary

R1 仅修复执行/契约/标签/缺失值问题；P2-10/P2-11 不在本版本中重定义。Q4 仍为 diagnostic single-link capture，不是网络守恒或因果证明。

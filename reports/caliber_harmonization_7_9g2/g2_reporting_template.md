# 7.9G-2 统一报告模板（物化）

## 一、规则句（O9，固定句式）

> **`service` 端点链对仿真延误具有显著的时间暴露特征，但其影响并不与交通流量占比同步增长；
> 因此应分别从时间、数量、距离和交通量四个维度表征，而不能以单一 `delay share`
> 作为系统性拥堵归因依据。**

## 二、四要素强制（O6 / 门 12）

任何「某类占 X%」的断言必须写全四元组：`face` + `scope` + `Dk` + `universe`。

## 三、四面数值表（scope × face，universe = U_loaded；12 值）

| Scope | Face | Role | Value | Units | Denom | Share[D0] |
|---|---|---|---:|---|---|---:|
| ALL_LOADED | count | EXPOSURE | 224432.000000 | links | D0 | 100.000000% |
| ALL_LOADED | distance | EXPOSURE | 5185.704197 | km | D0 | 100.000000% |
| ALL_LOADED | volume | EXPOSURE | 40008184.000000 | veh | D0 | 100.000000% |
| ALL_LOADED | time | IMPACT | 4778.773666 | h_delay | D0 | 100.000000% |
| SERVICE_LOADED | count | EXPOSURE | 62407.000000 | links | D0 | 27.806641% |
| SERVICE_LOADED | distance | EXPOSURE | 962.715006 | km | D0 | 18.564788% |
| SERVICE_LOADED | volume | EXPOSURE | 1725544.000000 | veh | D0 | 4.312978% |
| SERVICE_LOADED | time | IMPACT | 4509.087344 | h_delay | D0 | 94.356579% |
| ENDPOINT_SERVICE_LOADED | count | EXPOSURE | 7083.000000 | links | D0 | 3.155967% |
| ENDPOINT_SERVICE_LOADED | distance | EXPOSURE | 203.384816 | km | D0 | 3.922029% |
| ENDPOINT_SERVICE_LOADED | volume | EXPOSURE | 168637.000000 | veh | D0 | 0.421506% |
| ENDPOINT_SERVICE_LOADED | time | IMPACT | 3410.521558 | h_delay | D0 | 71.368133% |

## 四、强度表（time 面基准，3 档 × 3 scope = 9 值）

| Scope | s/link | s/km | s/veh |
|---|---:|---:|---:|
| ALL_LOADED | 76.653887 | 3317.502222 | 0.430002 |
| SERVICE_LOADED | 260.110475 | 16861.391313 | 9.407303 |
| ENDPOINT_SERVICE_LOADED | 1733.429000 | 60367.719919 | 72.806547 |

## 五、禁令

- ⛔ 不得以单一 `delay share` 作头部结论（除非 Q4 判为 `SINGLE_HEADLINE_ADMISSIBLE`）。
- ⛔ 不得跨面加权 / 归一 / 求和；四面不合成总分。
- ⛔ 不得以 Gini 或常数 `top-k` 作集中度判据；集中度一律用覆盖率分数 `f_t`。
- ⛔ 不得混用 `U_any` 与 `U_loaded`；`U_any` 量字段名必须带 `_any` 后缀。
- 本轮判决：Q1 `DENOMINATOR_SPLIT` / Q2 `EXPOSURE_IMPACT_DECOUPLED` / Q3 `CONCENTRATION_ATTENUATED`（SVC：`CONCENTRATION_ATTENUATED`）/ Q4 `FOUR_FACE_PARALLEL_REPORTING`


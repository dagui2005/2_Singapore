# MATSim 清理事后校验报告

```
====================================================================================
FINAL VERIFICATION — MATSim cleanup 2026-09-21
generated 2026-09-21 11:44:16
====================================================================================

[A1] reports/**/events.xml.gz remaining on D = 0   PASS
[A2] _smoke_R01_rc_min      removed=True
[A2] _smoke_S100k_rc_min    removed=True
[A3] E06    linkstats 20/20  PASS
[A3] D02    linkstats 20/20  PASS
[A3] D03    linkstats 20/20  PASS
[A3] D04    linkstats 20/20  PASS
[A3] S100c  linkstats 20/20  PASS
[A4] exists=True  reports/matsim_assignment/lambda_0p050/ITERS/it.0/step6_3_lambda_0p050.0.plans.xml.gz
[A4] exists=True  reports/matsim_assignment_6_3_3b/lambda_0p050/ITERS/it.0/step6_3_3b_lambda_0p050.0.plans.xml.gz
[A5] frozen dirs (bytes / files):
      matsim_final_7_6h         0.667 GB     107 files
      matsim_viz_7_8            3.806 GB      94 files
      matsim_kw_7_9b1           4.060 GB      94 files

[A6] MANIFEST_before vs K : OK=30  MISSING=0  DIFF=0   PASS

[A7] D: free 32.91 GB / total 476.93 GB (93.1% used)
     K: free 319.98 GB / total 439.87 GB (27.3% used)

[B] gzip full-stream + CRC validation: 50 files, 30.77 GB compressed
     workers = 28 (cpu=28)
     elapsed 570.4 s   invalid=0

====================================================================================
VERDICT: ALL_CHECKS_PASS
====================================================================================
```

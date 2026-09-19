import traceback, runpy, sys, io
buf = io.StringIO()
try:
    runpy.run_path(r"D:\Luan\2026-05\2_Singapore\scripts\od\analyze_cata_spatial_correspondence_7_3_2c.py", run_name="__main__")
    buf.write("OK\n")
except Exception:
    buf.write("TRACEBACK:\n")
    buf.write(traceback.format_exc())
open(r"D:\Luan\2026-05\2_Singapore\reports\od_route_diagnosis_7_3_2c\_wrap_out.txt","w",encoding="utf-8").write(buf.getvalue())

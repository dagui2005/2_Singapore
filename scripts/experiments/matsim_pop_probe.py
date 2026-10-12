#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
matsim_pop_probe.py — **真解析门**：用 MATSim 官方 `PopulationReader` 实际解析 population 文件。
================================================================================
为什么需要它（教训）
--------------------
E-SB-02C 的运行前门禁 R-06 只校验「文件存在 + 文件名」，于是放行了一个
**从根节点就 FATAL** 的 population（ElementTree 写出：缺 `<!DOCTYPE ...>` +
`<attribute ... value="..."/>` 自闭合形式）。这是本项目第 8 次「假门禁」。

本探针不是结构近似，而是**直接调用 MATSim 失败时所用的同一个类**
（`org.matsim.core.population.io.PopulationReader`），因此
「探针通过 ⇔ MATSim 后面能读进去」。

用法
----
    python scripts/experiments/matsim_pop_probe.py <pop.xml.gz> [more...]
输出：每文件一行 `PROBE_OK=1 persons=... sumEF=...`；失败返回码非 0 并打印异常头部。
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\Luan\2026-05\2_Singapore")
sys.path.insert(0, str(ROOT / "scripts" / "matsim"))
import matsim_env  # noqa: E402

JAVA_SRC = r'''
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.scenario.ScenarioUtils;
import org.matsim.core.population.io.PopulationReader;

public class PopProbe {
    public static void main(String[] args) throws Exception {
        Scenario sc = ScenarioUtils.createScenario(ConfigUtils.createConfig());
        new PopulationReader(sc).readFile(args[0]);
        long n = sc.getPopulation().getPersons().size();
        double ef = 0.0; long withEf = 0; long missing = 0;
        for (Person p : sc.getPopulation().getPersons().values()) {
            Object v = p.getAttributes().getAttribute("expansionFactor");
            if (v == null) { missing++; continue; }
            try { ef += Double.parseDouble(v.toString()); withEf++; }
            catch (Exception e) { missing++; }
        }
        System.out.println("PROBE_PERSONS=" + n);
        System.out.printf("PROBE_SUMEF=%.6f%n", ef);
        System.out.println("PROBE_WITH_EF=" + withEf);
        System.out.println("PROBE_MISSING_EF=" + missing);
    }
}
'''


def _javac_exe() -> str:
    j = Path(matsim_env.java_exe())
    cand = j.with_name("javac.exe" if os.name == "nt" else "javac")
    return str(cand)


def build_probe(work: Path) -> tuple[bool, str]:
    work.mkdir(parents=True, exist_ok=True)
    src = work / "PopProbe.java"
    src.write_text(JAVA_SRC, encoding="utf-8")
    cp = matsim_env.classpath()
    r = subprocess.run([_javac_exe(), "-cp", cp, "-d", str(work), str(src)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def probe_one(pop: Path, work: Path) -> dict:
    cp = matsim_env.classpath() + os.pathsep + str(work)
    cmd = [matsim_env.java_exe(), "-Xmx4g", "-Xms1g",
           "--enable-native-access=ALL-UNNAMED", "-cp", cp, "PopProbe", str(pop.resolve())]
    r = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    res = {"file": str(pop), "rc": r.returncode, "ok": False}
    for line in out.splitlines():
        if line.startswith("PROBE_PERSONS="):
            res["persons"] = int(line.split("=")[1])
        elif line.startswith("PROBE_SUMEF="):
            res["sumEF"] = float(line.split("=")[1])
        elif line.startswith("PROBE_WITH_EF="):
            res["withEF"] = int(line.split("=")[1])
        elif line.startswith("PROBE_MISSING_EF="):
            res["missingEF"] = int(line.split("=")[1])
    res["ok"] = (r.returncode == 0 and "PROBE_PERSONS=" in out)
    if not res["ok"]:
        # 只留最有信息量的片段
        head = [ln for ln in out.splitlines()
                if ("Exception" in ln or "FATAL" in ln or "Caused by" in ln
                    or "at org.matsim" in ln)][:6]
        res["err_head"] = "\n".join(head) if head else out[:400]
    return res


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    work = ROOT / "experiments" / "E-SB-02_night_freeflow" / "_probe"
    ok, log = build_probe(work)
    if not ok:
        print("[FATAL] PopProbe 编译失败:\n" + log)
        return 3
    allok = True
    for p in sys.argv[1:]:
        r = probe_one(Path(p), work)
        allok &= r["ok"]
        if r["ok"]:
            print(f"PROBE_OK=1  persons={r.get('persons')}  sumEF={r.get('sumEF')}  "
                  f"withEF={r.get('withEF')}  missingEF={r.get('missingEF')}  {p}")
        else:
            print(f"PROBE_OK=0  rc={r['rc']}  {p}\n{r.get('err_head','')}")
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())

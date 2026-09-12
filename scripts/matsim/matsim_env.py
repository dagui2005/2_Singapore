#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
matsim_env.py — 定位项目本地 MATSim 运行时并构建 Java 启动环境。

设计要点
--------
* 不使用 Maven / Gradle。MATSim 官方 release zip 已经自带 `matsim-2026.0.jar`
  与 `libs/`（164 个依赖 jar），因此只需要一个 JDK。
* MATSim 2026.0 的发行包是用 **Java 25** 编译的（manifest `Java-Version: 25`，
  class file major version 69）。用 Java 24 会直接
  `UnsupportedClassVersionError`，所以运行时固定使用 `tools/jdk-25*/`。
* 所有路径都在项目 `tools/` 下，便携、免管理员权限、不污染系统环境。

典型用法
--------
    from matsim_env import java_exe, classpath, run_java
    run_java(["org.matsim.run.RunMatsim", "config.xml"], heap="12g")
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "tools"


class MatsimEnvError(RuntimeError):
    pass


def _first_dir(pattern: str) -> Path:
    hits = sorted(p for p in TOOLS_DIR.glob(pattern) if p.is_dir())
    if not hits:
        raise MatsimEnvError(
            f"未找到匹配 {pattern} 的目录，请检查 {TOOLS_DIR}"
        )
    return hits[-1]


def java_exe() -> str:
    """返回项目本地 JDK 的 java 可执行文件（java.exe on Windows）。"""
    override = os.environ.get("MATSIM_JAVA")
    if override:
        return override
    jdk_dir = _first_dir("jdk-25*")
    exe = jdk_dir / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not exe.exists():
        raise MatsimEnvError(f"未找到 java 可执行文件: {exe}")
    return str(exe)


def matsim_dir() -> Path:
    """返回 MATSim 发行目录（含 matsim-2026.0.jar 与 libs/）。"""
    override = os.environ.get("MATSIM_HOME")
    if override:
        return Path(override)
    d = _first_dir("matsim-*")
    jars = list(d.glob("matsim-*.jar"))
    jars = [j for j in jars if "sources" not in j.name]
    if not jars:
        raise MatsimEnvError(f"{d} 下未找到 matsim-*.jar")
    return d


def matsim_jar() -> Path:
    d = matsim_dir()
    jars = [j for j in d.glob("matsim-*.jar") if "sources" not in j.name]
    if not jars:
        raise MatsimEnvError(f"{d} 下未找到主 jar")
    return jars[0]


def classpath() -> str:
    """主 jar + libs/*（Java 支持目录通配符 libs/*）。"""
    d = matsim_dir()
    sep = os.pathsep  # Windows ';'
    return f"{matsim_jar()}{sep}{d / 'libs'}{os.sep}*"


def run_java(
    args: list[str],
    heap: str = "12g",
    cwd: Path | str | None = None,
    extra_flags: list[str] | None = None,
    capture: bool = False,
) -> int:
    """以项目本地 JDK 启动一个 MATSim 主类。"""
    cmd = [java_exe(), f"-Xmx{heap}", "-Xms2g"]
    # 让 MATSim 的反射 / 依赖在较新 JVM 上保持安静
    cmd += ["--enable-native-access=ALL-UNNAMED"]
    if extra_flags:
        cmd += list(extra_flags)
    cmd += ["-cp", classpath()]
    cmd += list(args)

    env = dict(os.environ)
    env["MALLOC_ARENA_MAX"] = "4"
    if capture:
        p = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        return p
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env)
    return p.returncode


def run_java_streaming(
    args: list[str],
    log_path: Path | str | None = None,
    heap: str = "12g",
    cwd: Path | str | None = None,
    extra_flags: list[str] | None = None,
) -> int:
    """启动主类并把 stdout 同时写到控制台与日志文件（长任务可实时看进度）。"""
    cmd = [java_exe(), f"-Xmx{heap}", "-Xms2g",
           "--enable-native-access=ALL-UNNAMED"]
    if extra_flags:
        cmd += list(extra_flags)
    cmd += ["-cp", classpath()]
    cmd += list(args)

    env = dict(os.environ)
    env["MALLOC_ARENA_MAX"] = "4"
    fh = None
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        fh = open(log_path, "w", encoding="utf-8")
    try:
        p = subprocess.Popen(
            cmd, cwd=str(cwd) if cwd else None, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        assert p.stdout is not None
        for line in p.stdout:
            print(line, end="")
            if fh:
                fh.write(line)
        p.wait()
        return p.returncode
    finally:
        if fh:
            fh.close()


def describe() -> dict:
    d = matsim_dir()
    return {
        "project_root": str(PROJECT_ROOT),
        "java": java_exe(),
        "matsim_home": str(d),
        "matsim_jar": str(matsim_jar()),
        "classpath": classpath(),
        "libs_count": len(list((d / "libs").glob("*.jar"))),
    }


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        sys.exit(run_java(["-version"] if False else ["org.matsim.run.ReleaseInfo"]))
    print(json.dumps(describe(), indent=2, ensure_ascii=False))

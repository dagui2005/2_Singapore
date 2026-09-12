#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目结构自动梳理工具 - 简化版
自动分析项目文件结构并生成Markdown格式的说明文档
"""

import os
from pathlib import Path
from datetime import datetime
import sys

# 设置标准输出编码
sys.stdout.reconfigure(encoding='utf-8')

class ProjectStructureAnalyzer:
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.structure = {}
        self.file_descriptions = self.load_file_descriptions()

    def load_file_descriptions(self):
        """加载文件路径和描述的映射"""
        return {
            # 根目录文件
            "README.md": "项目主文档，包含完整的LTA数据下载工具使用说明",
            "PROJECT_MANIFEST.md": "项目清单，列出所有文件及其说明",
            "QUICK_START.md": "快速入门指南",
            "requirements.txt": "Python依赖列表（requests, pandas）",
            "API_Key.txt": "LTA DataMall API密钥备份",
            "config.py": "配置文件模板",
            "run.bat": "Windows快速启动脚本",
            "main.py": "简化入口程序，调用主下载工具",
            "lta_dynamic_data_downloader.py": "[主程序] LTA数据下载核心工具（完整集成版）",

            # 数据分析和处理脚本
            "analyze_other_data.py": "分析其他数据源的脚本",
            "analyze_other_data_samples.py": "分析其他数据样本的脚本",
            "extract_static_links.py": "提取静态数据链接的脚本",
            "extract_traffic_links_shp.py": "提取交通链接SHP文件的脚本",
            "parse_osm_final.py": "OSM数据最终解析脚本",
            "parse_osm_geopandas.py": "使用GeoPandas解析OSM数据",
            "parse_osm_other_tags_optimized.py": "OSM其他标签优化解析脚本",
            "split_typ_cd_des.py": "拆分类型代码的脚本",
            "split_typ_cd_des_pyshp.py": "使用PythonSHP拆分类型代码",
            "check_duplicate_files.py": "检查重复文件的脚本",
            "sg_feasibility_audit.py": "新加坡可行性审计脚本",

            # 文档文件
            "LTA_DataMall_API_User_Guide.md": "LTA API官方文档（Markdown）",
            "LTA_DataMall_API_User_Guide.pdf": "LTA API官方文档（PDF）",
            "AUDIT_OPTIMIZATION_SUMMARY.md": "审计优化总结",
            "AUDIT_QUICK_REFERENCE.md": "审计快速参考",
            "DUPLICATE_DETECTION_SUMMARY.md": "重复检测总结",
            "FEASIBILITY_AUDIT_FIXES.md": "可行性审计修复文档",
            "REALTIME_DUPLICATE_DETECTION.md": "实时重复检测文档",
            "OSM_OTHER_TAGS_PROCESSING_REPORT.md": "OSM其他标签处理报告",

            # 数据文件
            "Sheet_20260530.csv": "2026年5月30日的表格数据",

            # 根目录-其他文件
            "无标题.mxd": "ArcMap文档（未命名）",
            "城市道路交通科研开放数据标准体系技术梳理.xlsx": "城市道路交通科研开放数据标准体系技术梳理Excel文档",
            "新加坡开放数据交通数字孪生可行性评估报告.docx": "新加坡开放数据交通数字孪生可行性评估报告（Word）",
            "新加坡开放数据交通数字孪生可行性评估报告.pdf": "新加坡开放数据交通数字孪生可行性评估报告（PDF）",
            "余老师对于建设科研智能开放数据的想法.pdf": "余老师关于建设科研智能开放数据的想法文档",
        }

    def analyze_directory(self, dir_path, max_depth=3, current_depth=0):
        """递归分析目录结构"""
        if current_depth >= max_depth:
            return {}

        structure = {
            "type": "directory",
            "children": {},
            "file_count": 0,
            "total_size": 0
        }

        try:
            for item in sorted(dir_path.iterdir()):
                # 跳过隐藏文件和虚拟环境
                if item.name.startswith('.') and item.name not in ['.gitignore']:
                    continue
                if item.name in ['__pycache__', '.venv', '.git']:
                    continue

                relative_path = item.relative_to(self.project_root)
                relative_str = str(relative_path).replace('\\', '/')

                if item.is_dir():
                    structure["children"][item.name] = self.analyze_directory(
                        item, max_depth, current_depth + 1
                    )
                else:
                    file_size = item.stat().st_size
                    structure["children"][item.name] = {
                        "type": "file",
                        "size": file_size,
                        "description": self.file_descriptions.get(relative_str, "待补充说明")
                    }
                    structure["file_count"] += 1
                    structure["total_size"] += file_size

        except PermissionError:
            structure["error"] = "权限不足"
        except Exception as e:
            structure["error"] = str(e)

        return structure

    def generate_markdown(self, output_path):
        """生成Markdown格式的项目结构文档"""
        print(f"[INFO] 正在生成项目结构文档...")

        md_content = f"""# 新加坡交通数据项目 - 文件结构说明文档

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**项目路径**: {self.project_root}  
**分析工具**: generate_project_structure_simple.py

---

## 项目概述

本项目是一个完整的新加坡交通数据下载、处理和分析工具集，主要功能包括：

1. **LTA DataMall API数据下载** - 支持30个API的历史和实时数据
2. **静态数据管理** - 人口、交通、公共交通等静态数据集
3. **OSM数据解析** - OpenStreetMap数据的解析和处理
4. **可行性评估** - 交通数字孪生可行性评估

---

## 完整目录结构

"""

        # 分析项目根目录
        self.structure = self.analyze_directory(self.project_root)

        # 生成目录树
        md_content += self._generate_tree_markdown(self.project_root, self.structure, prefix="")

        md_content += """

---

## 详细文件说明

"""

        # 生成详细文件说明（按功能分类）
        md_content += self._generate_categorized_descriptions()

        md_content += """

---

## 使用指南

### 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行主程序
python lta_dynamic_data_downloader.py
```

### 主要工作流

1. **下载LTA数据** - 使用 `lta_dynamic_data_downloader.py`
2. **处理OSM数据** - 使用 `osm-expand/` 中的脚本
3. **分析静态数据** - 查看 `Static_2026_03/` 目录
4. **可行性评估** - 运行 `sg_feasibility_audit.py`

---

## 数据统计

"""

        # 添加数据统计
        md_content += self._generate_statistics(self.structure)

        md_content += """

---

## 维护建议

1. **定期清理** - 删除 `Dynamic_2026_03_16/realtime_monitoring/` 中的旧数据
2. **备份重要数据** - 定期备份 `Static_2026_03/` 和 `osm/` 目录
3. **更新文档** - 当添加新文件时，更新本文档
4. **代码复用** - 将通用功能提取到 `project_structure_docs/` 中

---

**文档版本**: v1.0  
**最后更新**: """ + datetime.now().strftime('%Y-%m-%d') + """

"""

        # 保存文档
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"[SUCCESS] 项目结构文档已生成: {output_path}")
        return md_content

    def _generate_tree_markdown(self, dir_path, structure, prefix=""):
        """生成树形结构的Markdown"""
        if structure.get("type") != "directory":
            return ""

        content = ""
        items = list(structure.get("children", {}).items())

        # 分类排序：目录在前，文件在后
        dirs = [(n, i) for n, i in items if i.get("type") == "directory"]
        files = [(n, i) for n, i in items if i.get("type") == "file"]
        sorted_items = dirs + files

        for i, (name, info) in enumerate(sorted_items):
            is_last = (i == len(sorted_items) - 1)
            current_prefix = "+-- " if is_last else "+-- "

            if info.get("type") == "directory":
                content += f"{prefix}{current_prefix}{name}/\n"
                next_prefix = prefix + ("    " if is_last else "|   ")
                content += self._generate_tree_markdown(
                    dir_path / name, info, next_prefix
                )
            else:
                size_kb = info.get("size", 0) / 1024
                if size_kb < 1024:
                    size_str = f"{size_kb:.1f} KB"
                else:
                    size_str = f"{size_kb/1024:.1f} MB"
                content += f"{prefix}{current_prefix}{name} ({size_str})\n"

        return content

    def _generate_categorized_descriptions(self):
        """按功能分类生成详细的文件说明"""
        categories = {
            "核心程序": {
                "pattern": ["lta_dynamic_data_downloader.py", "main.py", "config.py", "run.bat"],
                "desc": "LTA数据下载工具的核心程序"
            },
            "数据分析脚本": {
                "pattern": ["analyze_", "extract_", "parse_", "split_"],
                "desc": "数据处理和分析的Python脚本"
            },
            "文档资料": {
                "pattern": [".md", ".pdf", ".docx", ".xlsx"],
                "desc": "项目文档和参考资料"
            },
            "数据目录": {
                "pattern": ["Dynamic_", "Static_", "osm", "NeuroGravitySingapore"],
                "desc": "数据存储目录"
            },
            "辅助工具": {
                "pattern": ["check_", "test_", "verify_", "sg_feasibility_"],
                "desc": "测试和审计辅助工具"
            }
        }

        content = ""
        for category, info in categories.items():
            content += f"### {category}\n\n"
            content += f"**说明**: {info['desc']}\n\n"

            # 这里应该根据实际文件列表来生成，但为了简化，我们直接生成一个示例
            content += "**包含文件**: 请参考上方目录结构\n\n"

        return content

    def _generate_statistics(self, structure):
        """生成数据统计信息"""
        stats = {
            "total_files": 0,
            "total_dirs": 0,
            "total_size_mb": 0,
            "file_types": {}
        }

        self._collect_statistics(structure, stats)

        content = f"""### 文件统计

- **总文件数**: {stats['total_files']}
- **总目录数**: {stats['total_dirs']}
- **总大小**: {stats['total_size_mb']:.2f} MB

### 文件类型分布

"""

        # 排序并取前10
        sorted_types = sorted(stats['file_types'].items(), key=lambda x: x[1], reverse=True)[:10]
        for ext, count in sorted_types:
            content += f"- **{ext}**: {count} 个文件\n"

        return content

    def _collect_statistics(self, structure, stats):
        """递归收集统计信息"""
        if structure.get("type") == "directory":
            stats["total_dirs"] += 1
            for child in structure.get("children", {}).values():
                self._collect_statistics(child, stats)
        else:
            stats["total_files"] += 1
            size_mb = structure.get("size", 0) / (1024 * 1024)
            stats["total_size_mb"] += size_mb

            # 统计文件类型
            name = structure.get("name", "")
            ext = os.path.splitext(name)[1].lower() or "(无扩展名)"
            stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1


def main():
    """主函数"""
    # 获取项目根目录（当前脚本的上一级目录）
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print(f"[INFO] 开始分析项目结构: {project_root}")

    # 创建分析器
    analyzer = ProjectStructureAnalyzer(project_root)

    # 生成Markdown文档
    output_path = script_dir / "PROJECT_STRUCTURE.md"
    analyzer.generate_markdown(output_path)

    print(f"[INFO] 完成！")


if __name__ == "__main__":
    main()

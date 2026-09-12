"""
分析 OSM expanded SHP 文件和 relations.csv 的属性表结构，
生成 Markdown 文档，包含每个文件的字段定义和取值范围。
"""
import os
import csv
from pathlib import Path
from collections import Counter
import shapefile


OSM_DIR = Path(r"D:\Luan\2026-05\2_Singapore\osm")
OUTPUT_MD = OSM_DIR / "OSM_属性表结构说明.md"

SHP_FILES = [
    "osm-lines_expanded.shp",
    "osm-multiline_expanded.shp",
    "osm-points_expanded.shp",
    "osm-polygon_expanded.shp",
]

CSV_FILES = [
    "relations.csv",
]

# 几何类型映射
GEOM_TYPE_MAP = {
    1: "Point",
    3: "Polyline",
    5: "Polygon",
    8: "MultiPoint",
    11: "PointZ",
    13: "PolylineZ",
    15: "PolygonZ",
}

# DBF 字段类型映射
FIELD_TYPE_MAP = {
    'C': '字符 (Character)',
    'N': '数值 (Numeric)',
    'F': '浮点 (Float)',
    'L': '逻辑 (Logical)',
    'D': '日期 (Date)',
}


def analyze_shp_file(shp_path):
    """分析单个SHP文件的结构和字段取值"""
    sf = shapefile.Reader(str(shp_path), encoding='utf-8')
    fields = sf.fields[1:]  # 跳过删除标记
    num_records = sf.numRecords
    geom_type = sf.shapeTypeName

    result = {
        'file': shp_path.name,
        'geom_type': geom_type,
        'num_records': num_records,
        'num_fields': len(fields),
        'fields': [],
    }

    # 读取所有记录
    records = sf.records()

    for field in fields:
        fname = field[0]
        ftype = field[1]
        fsize = field[2]
        fdecimal = field[3]

        type_desc = FIELD_TYPE_MAP.get(ftype, ftype)

        # 获取该字段的所有非空值
        fidx = [f[0] for f in fields].index(fname)
        values = []
        for rec in records:
            val = rec[fidx]
            if val is not None and str(val).strip() != '':
                values.append(val)

        non_null_count = len(values)
        null_count = num_records - non_null_count
        fill_rate = (non_null_count / num_records * 100) if num_records > 0 else 0

        field_info = {
            'name': fname,
            'type': ftype,
            'type_desc': type_desc,
            'size': fsize,
            'decimal': fdecimal,
            'non_null': non_null_count,
            'null_count': null_count,
            'fill_rate': fill_rate,
        }

        # 分析取值范围
        if ftype in ('N', 'F'):
            if values:
                numeric_vals = []
                for v in values:
                    try:
                        numeric_vals.append(float(v))
                    except (ValueError, TypeError):
                        pass
                if numeric_vals:
                    field_info['min'] = min(numeric_vals)
                    field_info['max'] = max(numeric_vals)
                    # 统计唯一值数量
                    unique_count = len(set(numeric_vals))
                    field_info['unique'] = unique_count
                    if unique_count <= 10:
                        sorted_unique = sorted(set(numeric_vals))
                        field_info['unique_values'] = [
                            int(v) if v == int(v) else v for v in sorted_unique
                        ]
            else:
                field_info['min'] = None
                field_info['max'] = None
                field_info['unique'] = 0
        else:
            # 字符型字段
            unique_count = len(set(values))
            field_info['unique'] = unique_count

            if unique_count <= 20 and values:
                # 列出所有唯一值
                counter = Counter(values)
                top = counter.most_common(20)
                field_info['top_values'] = top
            elif values:
                # 只显示前10个最频繁值
                counter = Counter(values)
                top = counter.most_common(10)
                field_info['top_values'] = top

            # 计算最大/最小长度
            if values:
                lengths = [len(str(v)) for v in values]
                field_info['min_len'] = min(lengths)
                field_info['max_len'] = max(lengths)

        result['fields'].append(field_info)

    sf.close()
    return result


def analyze_csv_file(csv_path):
    """分析CSV文件的结构和字段取值"""
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    num_records = len(rows)

    result = {
        'file': csv_path.name,
        'num_records': num_records,
        'num_fields': len(fieldnames),
        'fields': [],
    }

    for fname in fieldnames:
        values = []
        null_count = 0
        for row in rows:
            val = row.get(fname, '')
            if val is not None and str(val).strip() != '':
                values.append(val)
            else:
                null_count += 1

        non_null_count = len(values)
        fill_rate = (non_null_count / num_records * 100) if num_records > 0 else 0

        field_info = {
            'name': fname,
            'type': 'String',
            'type_desc': '字符 (String)',
            'size': '-',
            'decimal': '-',
            'non_null': non_null_count,
            'null_count': null_count,
            'fill_rate': fill_rate,
        }

        # 尝试判断是否为数值型
        is_numeric = False
        numeric_vals = []
        if values:
            for v in values[:100]:
                try:
                    float(v)
                    is_numeric = True
                except ValueError:
                    is_numeric = False
                    break
            if is_numeric:
                for v in values:
                    try:
                        numeric_vals.append(float(v))
                    except ValueError:
                        pass

        if is_numeric and numeric_vals:
            field_info['type'] = 'Numeric'
            field_info['type_desc'] = '数值 (Numeric)'
            field_info['min'] = min(numeric_vals)
            field_info['max'] = max(numeric_vals)
            unique_count = len(set(numeric_vals))
            field_info['unique'] = unique_count
            if unique_count <= 10:
                sorted_unique = sorted(set(numeric_vals))
                field_info['unique_values'] = [
                    int(v) if v == int(v) else v for v in sorted_unique
                ]
        else:
            unique_count = len(set(values))
            field_info['unique'] = unique_count
            if unique_count <= 20 and values:
                counter = Counter(values)
                top = counter.most_common(20)
                field_info['top_values'] = top
            elif values:
                counter = Counter(values)
                top = counter.most_common(10)
                field_info['top_values'] = top

            if values:
                lengths = [len(str(v)) for v in values]
                field_info['min_len'] = min(lengths)
                field_info['max_len'] = max(lengths)

        result['fields'].append(field_info)

    return result


def format_value(val):
    """格式化显示值"""
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f"{val:.4f}".rstrip('0').rstrip('.')
    return str(val)


def generate_markdown(shp_results, csv_results):
    """生成 Markdown 文档"""
    lines = []
    lines.append("# OSM 数据属性表结构说明")
    lines.append("")
    lines.append("> 本文档描述新加坡 OpenStreetMap 数据的属性表结构，包括 4 个 expanded SHP 文件和 relations.csv。")
    lines.append("")
    lines.append("## 目录")
    lines.append("")
    for r in shp_results:
        anchor = r['file'].replace('.', '-').replace('_', '-').lower()
        lines.append(f"- [{r['file']}](#{anchor})")
    for r in csv_results:
        anchor = r['file'].replace('.', '-').replace('_', '-').lower()
        lines.append(f"- [{r['file']}](#{anchor})")
    lines.append("")

    # SHP 文件
    for r in shp_results:
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"## {r['file']}")
        lines.append(f"")
        lines.append(f"| 属性 | 值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 几何类型 | {r['geom_type']} |")
        lines.append(f"| 记录数 | {r['num_records']:,} |")
        lines.append(f"| 字段数 | {r['num_fields']} |")
        lines.append(f"")

        for fi in r['fields']:
            lines.append(f"### 字段: `{fi['name']}`")
            lines.append(f"")
            lines.append(f"| 属性 | 值 |")
            lines.append(f"|------|------|")
            lines.append(f"| 字段类型 | {fi['type_desc']} |")

            if fi['size'] != '-':
                lines.append(f"| 字段长度 | {fi['size']} |")
            if fi['decimal'] != '-' and fi['decimal'] > 0:
                lines.append(f"| 小数位数 | {fi['decimal']} |")

            lines.append(f"| 非空记录 | {fi['non_null']:,} |")
            lines.append(f"| 空值记录 | {fi['null_count']:,} |")
            lines.append(f"| 填充率 | {fi['fill_rate']:.1f}% |")
            lines.append(f"| 唯一值数 | {fi['unique']:,} |")

            if 'min' in fi and fi['min'] is not None:
                lines.append(f"| 最小值 | {format_value(fi['min'])} |")
                lines.append(f"| 最大值 | {format_value(fi['max'])} |")

            if 'min_len' in fi:
                lines.append(f"| 值长度范围 | {fi['min_len']} ~ {fi['max_len']} 字符 |")

            if 'unique_values' in fi:
                uv = ', '.join([format_value(v) for v in fi['unique_values']])
                lines.append(f"| 取值枚举 | {uv} |")

            if 'top_values' in fi:
                lines.append(f"| 高频取值 (计数) | |")
                lines.append(f"")
                for val, cnt in fi['top_values']:
                    val_str = str(val)
                    if len(val_str) > 60:
                        val_str = val_str[:57] + "..."
                    # 转义管道符
                    val_str = val_str.replace('|', '\\|')
                    lines.append(f"| | `{val_str}` ({cnt:,}) |")

            lines.append(f"")

    # CSV 文件
    for r in csv_results:
        lines.append(f"---")
        lines.append(f"")
        lines.append(f"## {r['file']}")
        lines.append(f"")
        lines.append(f"| 属性 | 值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 记录数 | {r['num_records']:,} |")
        lines.append(f"| 字段数 | {r['num_fields']} |")
        lines.append(f"")

        for fi in r['fields']:
            lines.append(f"### 字段: `{fi['name']}`")
            lines.append(f"")
            lines.append(f"| 属性 | 值 |")
            lines.append(f"|------|------|")
            lines.append(f"| 字段类型 | {fi['type_desc']} |")
            lines.append(f"| 非空记录 | {fi['non_null']:,} |")
            lines.append(f"| 空值记录 | {fi['null_count']:,} |")
            lines.append(f"| 填充率 | {fi['fill_rate']:.1f}% |")
            lines.append(f"| 唯一值数 | {fi['unique']:,} |")

            if 'min' in fi and fi['min'] is not None:
                lines.append(f"| 最小值 | {format_value(fi['min'])} |")
                lines.append(f"| 最大值 | {format_value(fi['max'])} |")

            if 'min_len' in fi:
                lines.append(f"| 值长度范围 | {fi['min_len']} ~ {fi['max_len']} 字符 |")

            if 'unique_values' in fi:
                uv = ', '.join([format_value(v) for v in fi['unique_values']])
                lines.append(f"| 取值枚举 | {uv} |")

            if 'top_values' in fi:
                lines.append(f"| 高频取值 (计数) | |")
                lines.append(f"")
                for val, cnt in fi['top_values']:
                    val_str = str(val)
                    if len(val_str) > 60:
                        val_str = val_str[:57] + "..."
                    val_str = val_str.replace('|', '\\|')
                    lines.append(f"| | `{val_str}` ({cnt:,}) |")

            lines.append(f"")

    return '\n'.join(lines)


def main():
    print("=" * 70)
    print("OSM 数据属性表结构分析")
    print("=" * 70)

    shp_results = []
    csv_results = []

    for fname in SHP_FILES:
        fpath = OSM_DIR / fname
        if not fpath.exists():
            print(f"[SKIP] {fname} 不存在")
            continue
        print(f"\n分析 {fname} ...")
        r = analyze_shp_file(fpath)
        print(f"  记录数: {r['num_records']:,}, 字段数: {r['num_fields']}")
        shp_results.append(r)

    for fname in CSV_FILES:
        fpath = OSM_DIR / fname
        if not fpath.exists():
            print(f"[SKIP] {fname} 不存在")
            continue
        print(f"\n分析 {fname} ...")
        r = analyze_csv_file(fpath)
        print(f"  记录数: {r['num_records']:,}, 字段数: {r['num_fields']}")
        csv_results.append(r)

    print(f"\n生成文档: {OUTPUT_MD}")
    md_content = generate_markdown(shp_results, csv_results)

    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"[OK] 文档已生成，共 {len(md_content.splitlines())} 行")
    print("=" * 70)


if __name__ == "__main__":
    main()

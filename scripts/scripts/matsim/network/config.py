"""
config.py

MATSim Network Builder 配置文件
Author : Xuechen Luan
"""

from pathlib import Path

# ----------------------------------------------------
# 工程根目录（自动定位）
# ----------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ----------------------------------------------------
# OSM 数据目录
# ----------------------------------------------------

OSM_DIR = PROJECT_ROOT / "osm"

# 你的道路Shapefile
ROAD_SHP = OSM_DIR / "osm_lines_expanded.shp"

# （以后可扩展）
NODE_SHP = OSM_DIR / "osm_points.shp"

# ----------------------------------------------------
# 输出目录
# ----------------------------------------------------

OUTPUT_DIR = PROJECT_ROOT / "matsim" / "network"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NETWORK_NODE_CSV = OUTPUT_DIR / "network_nodes.csv"

NETWORK_LINK_CSV = OUTPUT_DIR / "network_links.csv"

NETWORK_XML = OUTPUT_DIR / "network.xml"

NETWORK_XML_GZ = OUTPUT_DIR / "network.xml.gz"

NETWORK_REPORT = OUTPUT_DIR / "network_report.md"

# ----------------------------------------------------
# 坐标系
# ----------------------------------------------------

# OSM通常是WGS84
SOURCE_CRS = "EPSG:4326"

# 新加坡SVY21
TARGET_CRS = "EPSG:3414"

# ----------------------------------------------------
# 保留道路类型
# ----------------------------------------------------

VALID_HIGHWAYS = {

    "motorway",
    "motorway_link",

    "trunk",
    "trunk_link",

    "primary",
    "primary_link",

    "secondary",
    "secondary_link",

    "tertiary",
    "tertiary_link",

    "residential",

    "living_street",

    "unclassified"

}

# ----------------------------------------------------
# 默认参数
# ----------------------------------------------------

DEFAULT_LANES = 1

DEFAULT_SPEED = 50

DEFAULT_CAPACITY = 1000
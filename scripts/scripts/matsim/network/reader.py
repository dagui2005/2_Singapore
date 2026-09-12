"""
reader.py

读取并标准化OSM道路Shapefile

Author : Xuechen Luan
"""

from pathlib import Path
import geopandas as gpd
import pandas as pd

from config import (
    ROAD_SHP,
    SOURCE_CRS,
    TARGET_CRS,
    VALID_HIGHWAYS
)


class OSMRoadReader:
    """
    读取OSM道路Shapefile，并转换为MATSim可用的数据结构
    """

    def __init__(self, shp_file=None):

        if shp_file is None:
            shp_file = ROAD_SHP

        self.shp_file = Path(shp_file)

    # --------------------------------------------------
    # 主函数
    # --------------------------------------------------

    def read(self):

        print("=" * 60)
        print("Reading OSM Road Shapefile...")
        print(self.shp_file)
        print("=" * 60)

        gdf = gpd.read_file(self.shp_file)

        print(f"Total Features : {len(gdf)}")

        gdf = self._check_crs(gdf)

        gdf = self._filter_highway(gdf)

        gdf = self._clean_attributes(gdf)

        print(f"Valid Road Links : {len(gdf)}")

        print("Finished.\n")

        return gdf

    # --------------------------------------------------
    # 坐标系检查
    # --------------------------------------------------

    def _check_crs(self, gdf):

        if gdf.crs is None:

            print("CRS Missing. Assign EPSG:4326")

            gdf = gdf.set_crs(SOURCE_CRS)

        if str(gdf.crs) != TARGET_CRS:

            print(f"Transform CRS -> {TARGET_CRS}")

            gdf = gdf.to_crs(TARGET_CRS)

        return gdf

    # --------------------------------------------------
    # 保留机动车道路
    # --------------------------------------------------

    def _filter_highway(self, gdf):

        if "highway" not in gdf.columns:

            raise Exception("Cannot find field: highway")

        gdf = gdf[gdf["highway"].isin(VALID_HIGHWAYS)]

        gdf = gdf.reset_index(drop=True)

        return gdf

    # --------------------------------------------------
    # 属性标准化
    # --------------------------------------------------

    def _clean_attributes(self, gdf):

        # -------------------------
        # lanes
        # -------------------------

        if "lanes" not in gdf.columns:
            gdf["lanes"] = 1

        gdf["lanes"] = (
            gdf["lanes"]
            .fillna(1)
            .astype(str)
            .str.extract(r"(\d+)")
        )

        gdf["lanes"] = pd.to_numeric(
            gdf["lanes"],
            errors="coerce"
        ).fillna(1).astype(int)

        # -------------------------
        # maxspeed
        # -------------------------

        if "maxspeed" not in gdf.columns:
            gdf["maxspeed"] = None

        # -------------------------
        # oneway
        # -------------------------

        if "oneway" not in gdf.columns:
            gdf["oneway"] = "no"

        gdf["oneway"] = (
            gdf["oneway"]
            .fillna("no")
            .astype(str)
            .str.lower()
        )

        # -------------------------
        # railway
        # -------------------------

        if "railway" not in gdf.columns:
            gdf["railway"] = None

        # -------------------------
        # road name
        # -------------------------

        if "name" not in gdf.columns:
            gdf["name"] = ""

        return gdf

    # --------------------------------------------------
    # 打印字段
    # --------------------------------------------------

    @staticmethod
    def print_columns(gdf):

        print("\nCurrent Fields:")

        for c in gdf.columns:
            print(c)

        print()


# ------------------------------------------------------
# 调试
# ------------------------------------------------------

if __name__ == "__main__":

    reader = OSMRoadReader()

    roads = reader.read()

    reader.print_columns(roads)

    print(roads.head())
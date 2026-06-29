import hashlib
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from netpulse.config import settings

OPENCELLID_COLUMNS = [
    "radio", "mcc", "net", "area", "cell", "unit",
    "lon", "lat", "range", "samples", "changeable",
    "created", "updated", "averageSignal",
]

# Target MNCs for operator diversity (Telkomsel, Indosat, XL Axiata)
TARGET_MNCS = {1, 8, 11, 21}

ISLAND_GROUP_MAP = {
    "Aceh": "Sumatera",
    "Sumatera Utara": "Sumatera",
    "Sumatera Barat": "Sumatera",
    "Riau": "Sumatera",
    "Jambi": "Sumatera",
    "Sumatera Selatan": "Sumatera",
    "Bengkulu": "Sumatera",
    "Lampung": "Sumatera",
    "Kepulauan Bangka Belitung": "Sumatera",
    "Kepulauan Riau": "Sumatera",
    "DKI Jakarta": "Jawa",
    "Jawa Barat": "Jawa",
    "Jawa Tengah": "Jawa",
    "DI Yogyakarta": "Jawa",
    "Jawa Timur": "Jawa",
    "Banten": "Jawa",
    "Bali": "Bali Nusa",
    "Nusa Tenggara Barat": "Bali Nusa",
    "Nusa Tenggara Timur": "Bali Nusa",
    "Kalimantan Barat": "Kalimantan",
    "Kalimantan Tengah": "Kalimantan",
    "Kalimantan Selatan": "Kalimantan",
    "Kalimantan Timur": "Kalimantan",
    "Kalimantan Utara": "Kalimantan",
    "Sulawesi Utara": "Sulawesi",
    "Gorontalo": "Sulawesi",
    "Sulawesi Tengah": "Sulawesi",
    "Sulawesi Barat": "Sulawesi",
    "Sulawesi Selatan": "Sulawesi",
    "Sulawesi Tenggara": "Sulawesi",
    "Maluku": "Maluku",
    "Maluku Utara": "Maluku",
    "Papua": "Papua",
    "Papua Barat": "Papua",
    "Papua Selatan": "Papua",
    "Papua Tengah": "Papua",
    "Papua Pegunungan": "Papua",
    "Papua Barat Daya": "Papua",
}


def generate_tower_id(radio: str, mcc: int, net: int, area: int, cell: int) -> str:
    composite = f"{radio}|{mcc}|{net}|{area}|{cell}"
    return hashlib.sha256(composite.encode()).hexdigest()[:12]


def classify_cell_type(range_m: Optional[float]) -> str:
    if range_m is None or range_m == 0:
        return "suburban"
    if range_m < 1000:
        return "urban"
    if range_m <= 5000:
        return "suburban"
    return "rural"


def load_opencellid_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path, names=OPENCELLID_COLUMNS, header=None)
    return df


def filter_indonesia_slice(df: pd.DataFrame) -> pd.DataFrame:
    filtered = df[
        (df["mcc"] == 510)
        & (df["samples"] >= 2)
        & df["lat"].notna()
        & df["lon"].notna()
    ].copy()
    filtered["updated"] = pd.to_numeric(filtered["updated"], errors="coerce")
    return filtered.sort_values("updated", ascending=False)


def sample_towers(df: pd.DataFrame, n: int = None, seed: int = None) -> pd.DataFrame:
    n = n or settings.tower_sample_size
    seed = seed or settings.random_seed

    # Prefer target MNCs and radio diversity
    lte_umts_gsm = []
    for radio in ["LTE", "UMTS", "GSM"]:
        radio_df = df[df["radio"] == radio]
        if radio_df.empty:
            continue
        mnc_df = radio_df[radio_df["net"].isin(TARGET_MNCS)]
        source = mnc_df if len(mnc_df) >= n // 3 else radio_df
        lte_umts_gsm.append(source)

    if not lte_umts_gsm:
        return df.sample(n=min(n, len(df)), random_state=seed)

    combined = pd.concat(lte_umts_gsm).drop_duplicates(
        subset=["radio", "mcc", "net", "area", "cell"]
    )
    if len(combined) >= n:
        return combined.sample(n=n, random_state=seed)

    remaining = df[~df.index.isin(combined.index)]
    extra = remaining.sample(n=min(n - len(combined), len(remaining)), random_state=seed)
    return pd.concat([combined, extra]).head(n)


def assign_provinces(df: pd.DataFrame, geojson_path) -> pd.DataFrame:
    gdf = gpd.read_file(geojson_path)
    name_col = next(
        (c for c in ["nama", "name", "NAME_1", "province", "Provinsi"] if c in gdf.columns),
        gdf.columns[0],
    )
    gdf = gdf[[name_col, "geometry"]].rename(columns={name_col: "province_name"})

    points = gpd.GeoDataFrame(
        df.copy(),
        geometry=[Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, gdf, how="left", predicate="within")
    joined = joined.reset_index(drop=True)
    joined["island_group"] = joined["province_name"].map(ISLAND_GROUP_MAP)
    return joined


def build_tower_master_df(sampled: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in sampled.iterrows():
        tower_id = generate_tower_id(
            row["radio"], int(row["mcc"]), int(row["net"]), int(row["area"]), int(row["cell"])
        )
        range_m = int(row["range"]) if pd.notna(row["range"]) else None
        last_updated = (
            pd.to_datetime(int(row["updated"]), unit="s")
            if pd.notna(row["updated"])
            else None
        )
        rows.append({
            "tower_id": tower_id,
            "radio": row["radio"],
            "mcc": int(row["mcc"]),
            "mnc": int(row["net"]),
            "area": int(row["area"]),
            "cell": int(row["cell"]),
            "lon": float(row["lon"]),
            "lat": float(row["lat"]),
            "range_m": range_m,
            "samples": int(row["samples"]) if pd.notna(row["samples"]) else None,
            "changeable": int(row["changeable"]) if pd.notna(row["changeable"]) else None,
            "cell_type": classify_cell_type(range_m),
            "province_name": row.get("province_name"),
            "island_group": row.get("island_group"),
            "last_updated": last_updated,
        })
    return pd.DataFrame(rows)


def get_island_group(province_name: str) -> Optional[str]:
    return ISLAND_GROUP_MAP.get(province_name)

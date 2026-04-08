from __future__ import annotations

from pathlib import Path

import pandas as pd


class FilesystemDataLoader:
    """Load Stage 2 and Stage 3 CSV outputs into DataFrames."""

    @staticmethod
    def load_polar_data(polars_dir: Path) -> pd.DataFrame:
        rows: list[pd.DataFrame] = []
        if not polars_dir.exists():
            return pd.DataFrame()

        for csv_path in polars_dir.glob("*.csv"):
            stem = csv_path.stem
            section = None
            condition = None
            for suffix in ("mid_span", "root", "tip"):
                if stem.endswith(f"_{suffix}"):
                    section = suffix
                    condition = stem[: -(len(suffix) + 1)].lower()
                    break
            if condition is None or section is None:
                continue

            df = pd.read_csv(csv_path)
            df["condition"] = condition
            df["section"] = section
            rows.append(df)

        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    @staticmethod
    def load_compressibility_data(stage3_dir: Path) -> pd.DataFrame:
        rows: list[pd.DataFrame] = []
        if not stage3_dir.exists():
            return pd.DataFrame()

        for csv_path in stage3_dir.glob("*/*/corrected_polar.csv"):
            condition = csv_path.parent.parent.name.lower()
            section = csv_path.parent.name
            df = pd.read_csv(csv_path)
            df["condition"] = condition
            df["section"] = section
            rows.append(df)

        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


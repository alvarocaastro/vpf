"""Centralised LaTeX table export for the VPF analysis pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_table(
    df: pd.DataFrame,
    output_path: Path,
    caption: str,
    label: str,
    float_format: str = ":.4f",
) -> None:
    """Write *df* as a LaTeX booktabs table to *output_path*.

    Parameters
    ----------
    df:
        DataFrame whose columns become table columns.
    output_path:
        Destination ``.tex`` file (parent directory must exist).
    caption:
        LaTeX caption string (no trailing period).
    label:
        LaTeX label string (without ``tab:`` prefix — added automatically).
    float_format:
        Python format spec (without ``{`` / ``}``) applied to numeric cells.
    """
    col_spec = "c" * len(df.columns)
    header = " & ".join(str(c) for c in df.columns) + r" \\"

    def _fmt(v: object) -> str:
        if isinstance(v, float):
            return f"{v:{float_format.lstrip(':')}}"
        return str(v)

    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        f"  \\caption{{{caption}}}",
        f"  \\label{{tab:{label}}}",
        f"  \\begin{{tabular}}{{{col_spec}}}",
        r"    \toprule",
        f"    {header}",
        r"    \midrule",
    ]
    for _, row in df.iterrows():
        lines.append("    " + " & ".join(_fmt(v) for v in row) + r" \\")
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    output_path.write_text("\n".join(lines), encoding="utf-8")

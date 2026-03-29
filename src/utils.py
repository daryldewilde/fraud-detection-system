"""General utility helpers used across the project."""

from io import BytesIO
from pathlib import Path
from typing import Union

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages


def ensure_directory(path: Union[str, Path]) -> Path:
    """Create a directory path if it does not exist and return it as Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Fraud Report") -> bytes:
    """Convert a DataFrame into XLSX bytes."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer.getvalue()


def dataframe_to_pdf_bytes(df: pd.DataFrame, title: str = "Fraud Detection Report") -> bytes:
    """Render a DataFrame into a paginated PDF table and return bytes."""
    if df.empty:
        safe_df = pd.DataFrame([{"message": "No records available."}])
    else:
        safe_df = df.copy()

    display_df = safe_df.astype(str)
    rows_per_page = 25
    total_pages = max(1, (len(display_df) + rows_per_page - 1) // rows_per_page)

    buffer = BytesIO()
    with PdfPages(buffer) as pdf:
        for page in range(total_pages):
            start = page * rows_per_page
            end = start + rows_per_page
            page_df = display_df.iloc[start:end]

            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.axis("off")
            ax.set_title(f"{title} (Page {page + 1}/{total_pages})", fontsize=12, pad=10)

            table = ax.table(
                cellText=page_df.values,
                colLabels=page_df.columns,
                loc="center",
                cellLoc="left",
            )
            table.auto_set_font_size(False)
            table.set_fontsize(7)
            table.scale(1, 1.2)

            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()

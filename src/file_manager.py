"""File storage manager for uploaded files and reports."""

import shutil
from pathlib import Path
from datetime import datetime

STORAGE_DIR = Path(__file__).parent.parent / "data" / "uploads"
REPORTS_DIR = Path(__file__).parent.parent / "outputs" / "reports"


def init_storage() -> None:
    """Initialize storage directories."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(user_id: int, uploaded_file) -> str:
    """
    Save an uploaded file to storage.
    Returns the file path (relative to project root).
    """
    init_storage()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_dir = STORAGE_DIR / f"user_{user_id}"
    user_dir.mkdir(exist_ok=True)

    filename = f"{timestamp}_{uploaded_file.name}"
    file_path = user_dir / filename

    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Return relative path
    return str(file_path.relative_to(Path(__file__).parent.parent))


def save_report_file(user_id: int, analysis_id: int, file_bytes: bytes, ext: str) -> str:
    """
    Save a report file to storage.
    ext should be 'xlsx', 'pdf', 'csv', etc.
    Returns the file path (relative to project root).
    """
    init_storage()
    user_dir = REPORTS_DIR / f"user_{user_id}"
    user_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"analysis_{analysis_id}_{timestamp}.{ext}"
    file_path = user_dir / filename

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Return relative path
    return str(file_path.relative_to(Path(__file__).parent.parent))


def get_file_bytes(file_path: str) -> bytes:
    """Read file from storage."""
    full_path = Path(__file__).parent.parent / file_path
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return full_path.read_bytes()


def file_exists(file_path: str) -> bool:
    """Check if file exists."""
    full_path = Path(__file__).parent.parent / file_path
    return full_path.exists()


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    full_path = Path(__file__).parent.parent / file_path
    if full_path.exists():
        return full_path.stat().st_size
    return 0


def get_filename_from_path(file_path: str) -> str:
    """Extract filename from path."""
    return Path(file_path).name

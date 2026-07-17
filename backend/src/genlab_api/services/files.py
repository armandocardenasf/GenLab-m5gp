from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile

from ..config import get_settings

SAFE = re.compile(r"[^A-Za-z0-9._-]+")
DATASET_SEPARATORS = {
    ".csv": ",",
    ".tsv": "\t",
}


def dataset_separator(path: str | Path) -> str:
    """Return the delimiter associated with a supported dataset extension."""
    suffix = Path(path).suffix.lower()
    try:
        return DATASET_SEPARATORS[suffix]
    except KeyError as exc:
        raise ValueError("Formato de dataset no soportado; use CSV o TSV") from exc


def resolve_dataset_path(
    path: str | Path,
    user_id: str | None = None,
) -> Path:
    """Resolve current and legacy dataset paths to one absolute location.

    New uploads are stored with absolute paths. The additional candidates keep
    datasets uploaded by previous versions usable when their database record
    contains a relative path such as ``data/uploads/<user>/<file>``.
    """
    stored = Path(path).expanduser()
    if stored.is_absolute():
        return stored.resolve()

    settings = get_settings()
    candidates: list[Path] = []

    # Legacy path resolved from the directory where the API process started.
    candidates.append((Path.cwd() / stored).resolve())

    # Legacy path beginning with the configured data directory name, e.g.
    # data/uploads/<user>/<filename>.
    if stored.parts and stored.parts[0] == settings.data_dir.name:
        candidates.append(
            settings.data_dir.joinpath(*stored.parts[1:]).resolve()
        )

    # Rebuild the canonical upload path from the dataset owner and filename.
    if user_id:
        candidates.append(
            (settings.upload_dir / user_id / stored.name).resolve()
        )

    # Generic path relative to the project directory containing data_dir.
    candidates.append((settings.data_dir.parent / stored).resolve())

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    # Return the first deterministic candidate so the resulting exception
    # reports a stable absolute path.
    return candidates[0]


def read_dataset(
    path: str | Path,
    *,
    user_id: str | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Read a CSV or TSV dataset using a stable absolute path."""
    resolved_path = resolve_dataset_path(path, user_id=user_id)
    return pd.read_csv(
        resolved_path,
        sep=dataset_separator(resolved_path),
        **kwargs,
    )


def save_dataset(upload: UploadFile, user_id: str):
    settings = get_settings()
    filename = SAFE.sub(
        "_", Path(upload.filename or "dataset.csv").name
    )
    if Path(filename).suffix.lower() not in DATASET_SEPARATORS:
        raise HTTPException(
            415,
            "Solo se admiten archivos CSV o TSV",
        )

    directory = (settings.upload_dir / user_id).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = (directory / filename).resolve()
    digest = hashlib.sha256()
    size = 0

    with path.open("wb") as output:
        while chunk := upload.file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                output.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, "Archivo demasiado grande")
            digest.update(chunk)
            output.write(chunk)

    try:
        frame = read_dataset(path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(
            422,
            f"Archivo CSV/TSV inválido: {exc}",
        ) from exc

    if frame.empty or len(frame.columns) < 2:
        path.unlink(missing_ok=True)
        raise HTTPException(
            422,
            "El dataset debe contener datos y al menos dos columnas",
        )
    if len(set(frame.columns)) != len(frame.columns):
        path.unlink(missing_ok=True)
        raise HTTPException(
            422,
            "El dataset contiene columnas duplicadas",
        )

    return path, frame, digest.hexdigest()


# Alias retained for compatibility with code that imported the previous name.
save_csv = save_dataset

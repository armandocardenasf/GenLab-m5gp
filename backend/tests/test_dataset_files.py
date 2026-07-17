from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from genlab_api.config import get_settings
from genlab_api.services.files import (
    dataset_separator,
    read_dataset,
    save_dataset,
)


def test_read_csv_dataset(tmp_path: Path):
    path = tmp_path / "sample.csv"
    path.write_text("x,y\n1,2\n3,4\n", encoding="utf-8")

    frame = read_dataset(path)

    assert frame.columns.tolist() == ["x", "y"]
    assert frame.shape == (2, 2)


def test_read_tsv_dataset(tmp_path: Path):
    path = tmp_path / "sample.tsv"
    path.write_text("x\ty\n1\t2\n3\t4\n", encoding="utf-8")

    frame = read_dataset(path)

    assert frame.columns.tolist() == ["x", "y"]
    assert frame.shape == (2, 2)


def test_dataset_separator_is_case_insensitive():
    assert dataset_separator("dataset.CSV") == ","
    assert dataset_separator("dataset.TSV") == "\t"


def test_save_dataset_accepts_tsv(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GENLAB_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    upload = UploadFile(
        filename="experiment.tsv",
        file=BytesIO(b"x\ty\n1\t2\n3\t4\n"),
    )

    path, frame, digest = save_dataset(upload, "user-1")

    assert path.suffix == ".tsv"
    assert path.exists()
    assert frame.shape == (2, 2)
    assert len(digest) == 64
    get_settings.cache_clear()


def test_save_dataset_returns_absolute_path(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GENLAB_DATA_DIR", "data")
    get_settings.cache_clear()
    upload = UploadFile(
        filename="absolute.tsv",
        file=BytesIO(b"x\ty\n1\t2\n"),
    )

    path, _, _ = save_dataset(upload, "user-absolute")

    assert path.is_absolute()
    assert path.is_file()
    get_settings.cache_clear()


def test_legacy_relative_path_survives_worker_chdir(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GENLAB_DATA_DIR", "data")
    get_settings.cache_clear()
    settings = get_settings()

    dataset_path = settings.upload_dir / "legacy-user" / "sample.tsv"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text("x\ty\n1\t2\n3\t4\n", encoding="utf-8")

    artifact_dir = settings.artifact_dir / "legacy-experiment"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(artifact_dir)

    frame = read_dataset(
        "data/uploads/legacy-user/sample.tsv",
        user_id="legacy-user",
    )

    assert frame.shape == (2, 2)
    assert frame.columns.tolist() == ["x", "y"]
    get_settings.cache_clear()

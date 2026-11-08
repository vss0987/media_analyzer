import pandas as pd
import pytest

from app.services import load_data, build_result, human, compute_stats


def test_load_data_reads_file(sample_xlsx):
    data = load_data([sample_xlsx])
    assert len(data) == 2
    assert "pub_dt" in data.columns
    assert "dl_dt" in data.columns
    assert "elapsed" in data.columns


def test_load_data_skips_missing_file(tmp_path):
    data = load_data([str(tmp_path / "nope.xlsx")])
    assert data.empty
    assert "pub_dt" in data.columns
    assert "elapsed" in data.columns


def test_build_result_counts_and_urls(sample_xlsx):
    data = load_data([sample_xlsx])
    result = build_result(data)
    assert len(result) == 2
    assert set(result.columns) >= {"Издание", "Количество скачиваний", "URL страницы файла"}
    assert result.loc[result["Издание"] == "Издание А", "Количество скачиваний"].iloc[0] == 1


def test_human_formats_timedelta():
    assert human(pd.Timedelta(days=400)) == "1 г. 1 мес. 5 дн."
    assert human(pd.Timedelta(hours=5)) == "5 ч."
    assert human(pd.NaT) == "—"


def test_compute_stats_ok(sample_xlsx):
    data = load_data([sample_xlsx])
    stats = compute_stats(data)
    assert stats["total_rows"] == 2
    assert stats["valid_rows"] == 2
    assert "mean_elapsed" in stats
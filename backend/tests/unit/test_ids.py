from __future__ import annotations

import pytest

from app.core.ids import IdPrefix, is_valid_id, new_id, new_ulid


def test_new_id_has_prefix_and_valid_ulid() -> None:
    value = new_id(IdPrefix.CHARACTER)
    assert value.startswith("CHR_")
    assert is_valid_id(value, IdPrefix.CHARACTER)
    assert not is_valid_id(value, IdPrefix.PRODUCT)


def test_ulids_sort_by_time() -> None:
    assert new_ulid(1_000) < new_ulid(2_000) < new_ulid(2**48 - 1)


def test_ulid_rejects_out_of_range_timestamp() -> None:
    with pytest.raises(ValueError):
        new_ulid(2**48)


def test_ids_are_unique() -> None:
    assert len({new_id(IdPrefix.JOB) for _ in range(1_000)}) == 1_000


@pytest.mark.parametrize(
    "value", ["CHR_", "CHR-01ARZ3NDEKTSV4RRFFQ69G5FAV", "CHR_01arz3ndektsv4rrffq69g5fav", "../etc"]
)
def test_is_valid_id_rejects_malformed(value: str) -> None:
    assert not is_valid_id(value, IdPrefix.CHARACTER)

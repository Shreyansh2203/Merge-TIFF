import io

import pytest
from PIL import Image

from api import merge as merge_module
from api.merge import (
    MAX_RESPONSE_BYTES,
    OUTPUT_COMPRESSION,
    MergeError,
    merge_images,
)

TIFF_COMPRESSION = {"tiff_adobe_deflate": 8, "raw": 1}


def _page(name, mode="L", size=(32, 32), compression="raw"):
    image = Image.new(mode, size, 100)
    if mode in ("P", "PA"):
        image.putpalette([0, 0, 0] + [1, 2, 3] * 255)
    return name, image


def _open(data):
    return Image.open(io.BytesIO(data))


def test_rejects_empty_page_list():
    with pytest.raises(MergeError) as excinfo:
        merge_images([])

    assert excinfo.value.status == 400


def test_single_page_round_trips():
    data = merge_images([_page("one.tif")])

    image = _open(data)
    assert image.format == "TIFF"
    assert image.n_frames == 1
    assert image.tag_v2.get(270) == "one.tif"
    assert image.tag_v2.get(285) == "one.tif"
    assert image.tag_v2.get(259) == TIFF_COMPRESSION[OUTPUT_COMPRESSION]


def test_every_page_keeps_its_own_name():
    names = ["alpha.tif", "beta.tif", "gamma.tif", "delta.tif"]

    data = merge_images([_page(name) for name in names])

    image = _open(data)
    assert image.n_frames == 4
    found = []
    for index in range(image.n_frames):
        image.seek(index)
        found.append((image.tag_v2.get(270), image.tag_v2.get(285)))
    assert found == [(name, name) for name in names]


def test_mixed_modes_and_compressions_are_preserved():
    pages = [
        _page("gray.tif", mode="L", compression="raw"),
        _page("color.tif", mode="RGB", compression="tiff_adobe_deflate"),
        _page("alpha.tif", mode="RGBA", compression="tiff_lzw"),
    ]

    data = merge_images(pages)

    image = _open(data)
    assert image.n_frames == 3
    modes = []
    for index in range(image.n_frames):
        image.seek(index)
        image.load()
        modes.append(image.mode)
        assert image.tag_v2.get(259) == TIFF_COMPRESSION[OUTPUT_COMPRESSION]
    assert modes == ["L", "RGB", "RGBA"]


def test_mixed_page_sizes_are_preserved():
    pages = [
        _page("big.tif", mode="L", size=(64, 48)),
        _page("small.tif", mode="L", size=(16, 16)),
        _page("tall.tif", mode="RGB", size=(8, 90)),
    ]

    data = merge_images(pages)

    image = _open(data)
    sizes = []
    for index in range(image.n_frames):
        image.seek(index)
        image.load()
        sizes.append(image.size)
    assert sizes == [(64, 48), (16, 16), (8, 90)]


def test_mixed_bit_depths_are_preserved():
    pages = [
        _page("eight.tif", mode="L", size=(16, 16)),
        _page("sixteen.tif", mode="I;16", size=(16, 16)),
    ]

    data = merge_images(pages)

    image = _open(data)
    depths = []
    for index in range(image.n_frames):
        image.seek(index)
        image.load()
        depths.append((image.mode, image.tag_v2.get(258)))
    assert depths == [("L", (8,)), ("I;16", (16,))]


def test_bilevel_and_palette_pages_are_rejected():
    pages = [
        _page("bilevel.tif", mode="1", size=(16, 16)),
        _page("palette.tif", mode="P", size=(16, 16)),
    ]

    with pytest.raises(MergeError) as excinfo:
        merge_images(pages)

    assert excinfo.value.status == 400
    assert "palette" in excinfo.value.message.lower()
    assert "1, P" in excinfo.value.message


def test_bilevel_pages_alone_are_allowed():
    data = merge_images(
        [
            _page("b1.tif", mode="1", size=(16, 16)),
            _page("b2.tif", mode="1", size=(16, 16)),
        ]
    )

    image = _open(data)
    assert image.n_frames == 2


def test_palette_pages_alone_are_allowed():
    data = merge_images(
        [
            _page("p1.tif", mode="P", size=(16, 16)),
            _page("p2.tif", mode="P", size=(16, 16)),
        ]
    )

    image = _open(data)
    assert image.n_frames == 2


def test_duplicate_pages_are_allowed():
    name, image = _page("same.tif")

    data = merge_images([(name, image), (name, image)])

    assert _open(data).n_frames == 2


def test_unencodable_page_raises_merge_error():
    unencodable = Image.new("HSV", (8, 8))

    with pytest.raises(MergeError) as excinfo:
        merge_images([_page("ok.tif"), ("broken.tif", unencodable)])

    assert excinfo.value.status == 400
    assert "could not be encoded" in excinfo.value.message


def test_response_ceiling_is_below_the_platform_cap():
    assert MAX_RESPONSE_BYTES == 4 * 1024 * 1024
    assert MAX_RESPONSE_BYTES < 4_500_000


def test_oversized_merge_is_rejected_before_it_is_returned(monkeypatch):
    monkeypatch.setattr(merge_module, "OUTPUT_COMPRESSION", "raw")
    pages = [_page(f"page{n}.tif", size=(1200, 1200)) for n in range(3)]

    with pytest.raises(MergeError) as excinfo:
        merge_images(pages)

    assert excinfo.value.status == 413
    assert "4.0 MB" in excinfo.value.message
    assert "fewer pages per request" in excinfo.value.message


def test_merge_at_the_response_ceiling_is_accepted(monkeypatch):
    monkeypatch.setattr(merge_module, "MAX_RESPONSE_BYTES", 8 * 1024 * 1024)

    data = merge_images([_page("small.tif", size=(32, 32))])

    assert _open(data).n_frames == 1

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


def test_control_characters_in_a_name_never_reach_the_output_tags():
    """The tags the merge writes are delivered inside the file the user gets.

    os.path.basename strips a path but not control bytes, so a crafted
    multipart filename could write terminal escapes or NULs into tags 270/285.
    The sanitiser runs at the tag write point, so this exercises merge_images
    directly rather than trusting every caller to clean its names first.
    """
    data = merge_images([_page("bad\x00name\r\n.tif")])

    image = _open(data)
    assert image.tag_v2.get(270) == "badname.tif"
    assert image.tag_v2.get(285) == "badname.tif"


def test_a_name_that_is_only_unsafe_characters_falls_back_to_a_page_label():
    data = merge_images([_page("\x00\x01\x7f")])

    image = _open(data)
    assert image.tag_v2.get(270) == "page"
    assert image.tag_v2.get(285) == "page"


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


# Mode, BitsPerSample, SamplesPerPixel and PhotometricInterpretation of a page
# that has been through merge_images. Photometric is the tag that decides what
# a sample value *means*, so asserting it is what catches a page that is
# structurally valid but has had its polarity or colour meaning changed.
MERGED_PAGE_TAGS = [
    ("L", (8,), None, 1),
    ("RGB", (8, 8, 8), 3, 2),
    ("RGBA", (8, 8, 8, 8), 4, 2),
    ("I;16", (16,), None, 1),
    ("1", (1,), None, 1),
]


@pytest.mark.parametrize("mode,bits,samples,photometric", MERGED_PAGE_TAGS)
def test_every_mode_keeps_its_interpretation(mode, bits, samples, photometric):
    data = merge_images([_page("page.tif", mode=mode, size=(16, 16))])

    image = _open(data)
    image.load()
    assert image.mode == mode
    assert image.tag_v2.get(258) == bits
    assert image.tag_v2.get(277) == samples
    assert image.tag_v2.get(262) == photometric


def test_pixels_of_every_mode_survive_a_mixed_merge():
    originals = {}
    pages = []
    for name, (mode, _bits, _samples, _photometric) in zip(
        ("gray.tif", "rgb.tif", "rgba.tif", "depth.tif", "bilevel.tif"),
        MERGED_PAGE_TAGS,
        strict=True,
    ):
        image = Image.new(mode, (16, 16))
        pixels = image.load()
        for y in range(16):
            for x in range(16):
                if mode == "1":
                    pixels[x, y] = 1 if (x + y) % 2 else 0
                elif mode == "I;16":
                    pixels[x, y] = (x * 4097 + y * 257) % 65536
                elif mode == "RGBA":
                    pixels[x, y] = (x * 16, y * 16, 7, (x * 16 + y) % 256)
                elif mode == "RGB":
                    pixels[x, y] = (x * 16, y * 16, 7)
                else:
                    pixels[x, y] = (x * 16 + y) % 256
        originals[name] = image.tobytes()
        pages.append((name, image))

    image = _open(merge_images(pages))

    for index, name in enumerate(originals):
        image.seek(index)
        image.load()
        assert image.tobytes() == originals[name], name


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


def test_the_response_ceiling_bites_while_the_merge_is_written(monkeypatch):
    """The cap has to stop the writer, not measure it after the fact.

    The ceiling used to be applied to getvalue(), so a merge bound for 400 MB
    assembled all of it and then discovered it was too big, holding the decoded
    pages, the buffer and a full second copy of the output at once. CappedBuffer
    applies the same number while the bytes are produced, so the peak is the
    cap plus at most the one write that would have crossed it.
    """
    monkeypatch.setattr(merge_module, "OUTPUT_COMPRESSION", "raw")
    writes = []
    buffers = []
    capped = merge_module.CappedBuffer

    class Spy(capped):
        def __init__(self, cap):
            super().__init__(cap)
            buffers.append(self)

        def write(self, data):
            written = super().write(data)
            writes.append(len(data))
            return written

    monkeypatch.setattr(merge_module, "CappedBuffer", Spy)
    pages = [_page(f"page{n}.tif", size=(1200, 1200)) for n in range(3)]

    with pytest.raises(MergeError) as excinfo:
        merge_images(pages)

    assert excinfo.value.status == 413
    assert buffers, "merge_images did not write through CappedBuffer"
    peak = buffers[0].peak
    assert peak <= MAX_RESPONSE_BYTES, f"grew to {peak}, over the cap"
    assert MAX_RESPONSE_BYTES - peak <= max(writes), (
        f"stopped {MAX_RESPONSE_BYTES - peak} bytes short, which is more than "
        f"the largest single write ({max(writes)}), so it did not stop at the cap"
    )
    assert peak < 3 * 1200 * 1200, "assembled every page before measuring"


def test_a_merge_under_the_ceiling_is_returned_whole(monkeypatch):
    """The capped writer must not truncate a merge that fits."""
    monkeypatch.setattr(merge_module, "OUTPUT_COMPRESSION", "raw")
    buffers = []
    capped = merge_module.CappedBuffer

    class Spy(capped):
        def __init__(self, cap):
            super().__init__(cap)
            buffers.append(self)

    monkeypatch.setattr(merge_module, "CappedBuffer", Spy)
    pages = [_page("one.tif", size=(32, 32)), _page("two.tif", size=(32, 32))]

    data = merge_images(pages)

    assert len(data) == buffers[0].peak
    assert _open(data).n_frames == 2


def test_merge_at_the_response_ceiling_is_accepted(monkeypatch):
    monkeypatch.setattr(merge_module, "MAX_RESPONSE_BYTES", 8 * 1024 * 1024)

    data = merge_images([_page("small.tif", size=(32, 32))])

    assert _open(data).n_frames == 1

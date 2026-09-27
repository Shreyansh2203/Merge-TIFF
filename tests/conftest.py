import io

import pytest
from PIL import Image

from api.merge import app


def _tiff_bytes(mode="L", size=(32, 32), compression="raw", color=100):
    image = Image.new(mode, size, color)
    if mode in ("P", "PA"):
        image.putpalette([0, 0, 0] + [1, 2, 3] * 255)
    buffer = io.BytesIO()
    image.save(buffer, format="TIFF", compression=compression)
    return buffer.getvalue()


def _png_bytes(size=(16, 16)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def _page_details(data):
    image = Image.open(io.BytesIO(data))
    details = []
    for index in range(getattr(image, "n_frames", 1)):
        image.seek(index)
        image.load()
        details.append(
            {
                "mode": image.mode,
                "size": image.size,
                "name": image.tag_v2.get(270),
                "description": image.tag_v2.get(285),
                "compression": image.tag_v2.get(259),
            }
        )
    return details


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def tiff_bytes():
    return _tiff_bytes


@pytest.fixture
def png_bytes():
    return _png_bytes


@pytest.fixture
def pages():
    return _page_details


@pytest.fixture
def make_tiff(tmp_path):
    counter = {"n": 0}

    def _make(mode="L", size=(32, 32), compression="raw", name=None, **kwargs):
        counter["n"] += 1
        filename = name or f"page{counter['n']}.tif"
        (tmp_path / filename).write_bytes(
            _tiff_bytes(mode, size, compression, **kwargs)
        )
        return tmp_path / filename

    return _make

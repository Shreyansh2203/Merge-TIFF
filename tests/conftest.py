import io

import pytest
from PIL import Image

from api.merge import app


def _tiff_bytes(mode="L", size=(32, 32), compression="raw", color=100, tiffinfo=None):
    image = Image.new(mode, size, color)
    if mode in ("P", "PA"):
        image.putpalette([0, 0, 0] + [1, 2, 3] * 255)
    buffer = io.BytesIO()
    save_kwargs = {} if tiffinfo is None else {"tiffinfo": tiffinfo}
    image.save(buffer, format="TIFF", compression=compression, **save_kwargs)
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
def post_without_content_length():
    """Post a body the way a chunked upload arrives: no Content-Length.

    Werkzeug bounds a stream of unknown length only when the server declares
    `wsgi.input_terminated`, which is what Vercel's runtime and the Werkzeug
    development server both do. With no Content-Length and no such declaration
    it refuses to read the body at all, so every path is bounded.
    """
    app.config["TESTING"] = True
    captured = {}
    written = []

    def start_response(status, response_headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(response_headers)
        return written.append

    def _post(path, chunks, content_type="multipart/form-data"):
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "CONTENT_TYPE": content_type,
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(b"".join(chunks)),
            "wsgi.input_terminated": True,
            "wsgi.errors": io.StringIO(),
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
        }
        assert "CONTENT_LENGTH" not in environ
        app_iter = app(environ, start_response)
        try:
            for data in app_iter:
                captured.setdefault("body", b"")
                captured["body"] += data
        finally:
            app_iter.close()
        return captured

    return _post


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

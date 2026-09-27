import io
from pathlib import Path

import pytest
from PIL import Image
from werkzeug.test import EnvironBuilder

from api import merge as merge_module
from api.merge import (
    MAX_FILES,
    MAX_IMAGE_PIXELS,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    MAX_TOTAL_IMAGE_PIXELS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _multipart(parts):
    builder = EnvironBuilder(
        method="POST",
        data={"files": parts},
        content_type="multipart/form-data",
    )
    environ = builder.get_environ()
    return environ["wsgi.input"].getvalue(), environ["CONTENT_TYPE"]


def test_client_fixture_uses_the_real_limits(client):
    """The test client must run the real merge, not a stand-in.

    tests/conftest.py builds ``mini_app`` by calling ``create_app`` and overwriting
    the two handlers with closures over that same function's constants, so the tests
    that matter here exercise the real route. Assert that rather than assume it: a
    future edit that turned mini_app into a hand-rolled app would otherwise turn the
    whole suite into a tautology.
    """
    rules = {
        rule.rule: client.application.view_functions[rule.endpoint]
        for rule in client.application.url_map.iter_rules()
    }

    assert rules["/api/merge"] is merge_module.merge_tiffs
    assert rules["/health"] is merge_module.health


def test_health_reports_limits(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["max_request_bytes"] == MAX_REQUEST_BYTES
    assert payload["max_response_bytes"] == MAX_RESPONSE_BYTES
    assert payload["max_files"] == MAX_FILES
    assert payload["max_image_pixels"] == MAX_IMAGE_PIXELS
    assert payload["max_total_image_pixels"] == MAX_TOTAL_IMAGE_PIXELS


def test_resource_bounds_match_documented_values():
    assert MAX_REQUEST_BYTES == 4 * 1024 * 1024
    assert MAX_RESPONSE_BYTES == 4 * 1024 * 1024
    assert MAX_FILES == 20
    assert MAX_IMAGE_PIXELS == 50_000_000
    assert MAX_TOTAL_IMAGE_PIXELS == 50_000_000


def test_documented_limits_are_actually_published():
    """The numbers above are compared to literals, not to the documentation.

    Nothing else in the suite reads README.md, so a drift between the published
    limits and the enforced ones is invisible to CI. This closes the obvious half:
    every limit the README's API table quotes.
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert '"max_files": 20' in readme, "README no longer states max_files=20"
    assert "20 pages" in readme, "README no longer states the 20-page cap"
    assert "50M decoded pixels" in readme, "README no longer states the pixel budget"
    for size in ("4 MB in", "4 MB out"):
        assert size in readme, f"README no longer states {size!r}"


def test_a_multipage_upload_contributes_exactly_one_page(client, pages):
    """A 3-frame TIFF is one page of the output, not three.

    Documented in the README as "its frames are not expanded, so a 50-frame scan
    becomes one page". Nothing asserted it: every n_frames assertion in the suite was
    about the output of freshly created single-frame images, so making merge_images
    expand every frame left all 58 tests green.
    """
    buffer = io.BytesIO()
    Image.new("L", (16, 16), 42).save(
        buffer,
        format="TIFF",
        save_all=True,
        append_images=[Image.new("L", (16, 16), 7), Image.new("L", (16, 16), 9)],
    )
    source = buffer.getvalue()
    assert getattr(Image.open(io.BytesIO(source)), "n_frames", 1) == 3

    response = client.post(
        "/api/merge",
        data={"files": [(io.BytesIO(source), "stack.tif")]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert len(pages(response.data)) == 1, "the frames of a multi-page upload were expanded"


def test_merge_multiple_images_into_multipage_tiff(
    client, make_tiff, pages
):
    paths = [make_tiff(name=f"scan{n}.tif", color=10 * n) for n in (1, 2, 3)]

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(p.read_bytes()), p.name) for p in paths
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "image/tiff"
    assert "merged_output.tif" in response.headers["Content-Disposition"]

    merged = pages(response.data)
    assert len(merged) == len(paths)
    assert [page["name"] for page in merged] == [p.name for p in paths]
    assert [page["description"] for page in merged] == [p.name for p in paths]
    assert all(page["size"] == (32, 32) for page in merged)


def test_merge_single_image(client, make_tiff, pages):
    path = make_tiff(name="only.tif")

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    merged = pages(response.data)
    assert len(merged) == 1
    assert merged[0]["name"] == "only.tif"


def test_merge_preserves_page_order(client, make_tiff, pages):
    paths = [
        make_tiff(name="c.tif"),
        make_tiff(name="a.tif"),
        make_tiff(name="b.tif"),
    ]

    response = client.post(
        "/api/merge",
        data={
            "files": [(io.BytesIO(p.read_bytes()), p.name) for p in paths]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert [page["name"] for page in pages(response.data)] == [
        "c.tif",
        "a.tif",
        "b.tif",
    ]


def test_duplicate_uploads_are_kept(client, make_tiff, pages):
    path = make_tiff(name="dup.tif")
    payload = path.read_bytes()

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(payload), "dup.tif"),
                (io.BytesIO(payload), "dup.tif"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    merged = pages(response.data)
    assert len(merged) == 2
    assert [page["name"] for page in merged] == ["dup.tif", "dup.tif"]


def test_uppercase_extension_accepted(client, make_tiff, pages):
    path = make_tiff(name="SCAN.TIFF")

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert pages(response.data)[0]["name"] == "SCAN.TIFF"


def test_path_traversal_filename_is_reduced_to_basename(
    client, make_tiff, pages
):
    path = make_tiff(name="safe.tif")

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(path.read_bytes()), "../../../etc/shadow.tif")
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert pages(response.data)[0]["name"] == "shadow.tif"


def test_rejects_non_tiff_extension(client, make_tiff, png_bytes):
    path = make_tiff(name="real.tif")

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(path.read_bytes()), path.name),
                (io.BytesIO(png_bytes()), "photo.png"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "photo.png" in response.get_json()["error"]


def test_rejects_png_renamed_to_tif(client, png_bytes):
    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(png_bytes()), "disguised.tif")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "disguised.tif" in response.get_json()["error"]


def test_rejects_corrupt_tiff(client, tmp_path):
    corrupt = tmp_path / "corrupt.tif"
    corrupt.write_bytes(b"II*\x00 this is not a real tiff payload")

    response = client.post(
        "/api/merge",
        data={
            "files": (io.BytesIO(corrupt.read_bytes()), corrupt.name)
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "corrupt.tif" in response.get_json()["error"]


def test_rejects_truncated_tiff(client, tmp_path, tiff_bytes):
    truncated = tmp_path / "truncated.tif"
    payload = tiff_bytes()
    truncated.write_bytes(payload[: len(payload) // 2])

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(truncated.read_bytes()), truncated.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "truncated.tif" in response.get_json()["error"]


def test_rejects_empty_file(client, tmp_path):
    empty = tmp_path / "empty.tif"
    empty.write_bytes(b"")

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(empty.read_bytes()), empty.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_rejects_request_without_files_field(client):
    response = client.post(
        "/api/merge", data={}, content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert "no files" in response.get_json()["error"].lower()


def test_rejects_non_multipart_request(client):
    response = client.post("/api/merge", json={"files": []})

    assert response.status_code == 400


def test_rejects_request_with_blank_filename(client, make_tiff):
    path = make_tiff(name="page.tif")

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(path.read_bytes()), path.name),
                (io.BytesIO(b""), ""),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200


def test_rejects_too_many_files(client, make_tiff, tiff_bytes):
    payload = tiff_bytes()
    files = [
        (io.BytesIO(payload), f"f{n}.tif") for n in range(MAX_FILES + 1)
    ]

    response = client.post(
        "/api/merge",
        data={"files": files},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert str(MAX_FILES) in response.get_json()["error"]


def test_accepts_exactly_max_files(client, tiff_bytes, pages):
    payload = tiff_bytes()
    files = [
        (io.BytesIO(payload), f"f{n}.tif") for n in range(MAX_FILES)
    ]

    response = client.post(
        "/api/merge",
        data={"files": files},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert len(pages(response.data)) == MAX_FILES


def test_rejects_oversized_request(client, tiff_bytes):
    oversized = b"\x00" * (MAX_REQUEST_BYTES + 1024)

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(oversized), "huge.tif")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert "too large" in response.get_json()["error"].lower()


def test_response_ceiling_is_enforced_with_guidance(
    client, make_tiff, monkeypatch
):
    path = make_tiff(name="page.tif", size=(64, 64))
    monkeypatch.setattr(merge_module, "MAX_RESPONSE_BYTES", 2 * 1024)
    monkeypatch.setattr(merge_module, "OUTPUT_COMPRESSION", "raw")

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    error = response.get_json()["error"]
    assert "2 KB" in error
    assert "split" in error


def test_a_wrong_extension_is_rejected_by_the_extension_gate(client, tiff_bytes):
    """The advice a user gets for a .png must come from the suffix allowlist.

    Two gates could reject a renamed file: TIFF_SUFFIXES and the `image.format` check
    in _decode_upload. Asserting only that the filename appears in the message let the
    suffix gate be deleted without a single test noticing, and the user then gets
    "'photo.png' is not a TIFF image." instead of the documented "... is not a TIFF
    file. Only .tif and .tiff are accepted."
    """
    png = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(png, format="PNG")

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(tiff_bytes()), "real.tif"),
                (io.BytesIO(png.getvalue()), "photo.png"),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "Only .tif and .tiff are accepted" in error, (
        "the extension guidance is gone, so the format gate is doing the suffix gate's job"
    )


def test_pillows_own_bomb_limit_is_kept_as_a_backstop():
    """The header check in _decode_upload is ours; this one belongs to Pillow.

    api/merge.py sets Image.MAX_IMAGE_PIXELS at import so Pillow's own two-times
    DecompressionBombError still fires behind our own guard. The bomb tests below
    monkeypatch Image.MAX_IMAGE_PIXELS to 128 before the request, so they can only
    ever prove our check works -- deleting the module-level assignment left the whole
    suite green.
    """
    assert Image.MAX_IMAGE_PIXELS == MAX_IMAGE_PIXELS
    assert merge_module.MAX_IMAGE_PIXELS == 50_000_000


def test_rejects_decompression_bomb(
    client, make_tiff, monkeypatch
):
    path = make_tiff(size=(64, 64))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 128)

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "pixels" in response.get_json()["error"]


def test_pixel_budget_is_enforced_before_a_page_is_decoded(
    client, make_tiff, monkeypatch
):
    path = make_tiff(name="big.tif", size=(64, 64))
    monkeypatch.setattr(merge_module, "MAX_IMAGE_PIXELS", 128)

    def explode(*_args, **_kwargs):
        raise AssertionError("decoded a page before checking the pixel budget")

    monkeypatch.setattr(Image.Image, "load", explode)

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "4096 pixels" in response.get_json()["error"]


def test_request_pixel_budget_spans_every_page(client, tiff_bytes, monkeypatch):
    payload = tiff_bytes(size=(32, 32))
    files = [(io.BytesIO(payload), f"f{index}.tif") for index in range(3)]
    monkeypatch.setattr(merge_module, "MAX_TOTAL_IMAGE_PIXELS", 2 * 1024)

    response = client.post(
        "/api/merge",
        data={"files": files},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "f2.tif" in error
    assert "pixel budget" in error


def test_request_within_the_pixel_budget_is_accepted(
    client, pages, tiff_bytes, monkeypatch
):
    payload = tiff_bytes(size=(32, 32))
    files = [(io.BytesIO(payload), f"f{index}.tif") for index in range(3)]
    monkeypatch.setattr(merge_module, "MAX_TOTAL_IMAGE_PIXELS", 3 * 1024)

    response = client.post(
        "/api/merge",
        data={"files": files},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert len(pages(response.data)) == 3


def test_chunked_upload_without_content_length_is_accepted(
    post_without_content_length, tiff_bytes
):
    body, content_type = _multipart([(io.BytesIO(tiff_bytes()), "page.tif")])

    captured = post_without_content_length("/api/merge", [body], content_type)

    assert captured["status"].startswith("200")
    assert captured["headers"]["Content-Type"] == "image/tiff"
    assert captured["body"][:4] in (b"II*\x00", b"MM\x00*")


def test_chunked_upload_without_content_length_is_bounded(
    post_without_content_length, tiff_bytes
):
    body, content_type = _multipart([(io.BytesIO(tiff_bytes()), "page.tif")])
    padding = b"\x00" * (MAX_REQUEST_BYTES + 4096)

    captured = post_without_content_length(
        "/api/merge", [body, padding], content_type
    )

    assert captured["status"].startswith("413")
    assert b"too large" in captured["body"].lower()


def test_rejects_corrupt_tiff_among_valid_files(client, make_tiff, tmp_path):
    good = make_tiff(name="good.tif")
    corrupt = tmp_path / "corrupt.tif"
    corrupt.write_bytes(b"II*\x00 this is not a real tiff payload")

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(good.read_bytes()), good.name),
                (io.BytesIO(corrupt.read_bytes()), corrupt.name),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "corrupt.tif" in response.get_json()["error"]


def test_rejects_decompression_bomb_among_valid_files(
    client, make_tiff, monkeypatch
):
    good = make_tiff(name="good.tif", size=(8, 8))
    bomb = make_tiff(name="bomb.tif", size=(64, 64))
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 128)

    response = client.post(
        "/api/merge",
        data={
            "files": [
                (io.BytesIO(good.read_bytes()), good.name),
                (io.BytesIO(bomb.read_bytes()), bomb.name),
            ]
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "bomb.tif" in response.get_json()["error"]


def test_internal_error_is_not_disclosed(client, make_tiff, monkeypatch):
    path = make_tiff(name="page.tif")

    def explode(_pages):
        raise RuntimeError("secret internal detail: /srv/keys/id_rsa")

    monkeypatch.setattr(merge_module, "merge_images", explode)

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    body = response.get_data(as_text=True)
    assert response.get_json()["error"] == "Failed to merge images."
    assert "secret internal detail" not in body
    assert "id_rsa" not in body


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_merge_endpoint_rejects_other_methods(client, method):
    assert client.open("/api/merge", method=method).status_code == 405

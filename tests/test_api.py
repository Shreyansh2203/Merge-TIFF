import io

import pytest
from PIL import Image

from api import index as merge_module
from api.index import MAX_FILES, MAX_IMAGE_PIXELS, MAX_REQUEST_BYTES


def test_health_reports_limits(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["max_request_bytes"] == MAX_REQUEST_BYTES
    assert payload["max_files"] == MAX_FILES
    assert payload["max_image_pixels"] == MAX_IMAGE_PIXELS


def test_decompression_bomb_limit_is_configured():
    assert Image.MAX_IMAGE_PIXELS == MAX_IMAGE_PIXELS


def test_resource_bounds_match_documented_values():
    assert MAX_REQUEST_BYTES == 4 * 1024 * 1024
    assert MAX_FILES == 20
    assert MAX_IMAGE_PIXELS == 50_000_000


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

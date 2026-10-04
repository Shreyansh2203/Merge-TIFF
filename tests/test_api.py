import io
import re
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

# A number in a client error, with the unit a size is rendered in when it has
# one. Used to check that the 4xx surface quotes nothing /health does not.
QUOTABLE_NUMBER = re.compile(r"\d+(?:\.\d+)?(?:\s?(?:KB|MB|GB))?")

# Tags a source TIFF can carry that the merge has no reason to write. XMP (700)
# is the sharpest of them: it is an arbitrary attacker-supplied byte string
# that the merge used to hand back verbatim.
SOURCE_ONLY_TAGS = (700, 305, 34675, 282, 283, 296, 65000)


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


def test_responses_refuse_mime_sniffing(client):
    """Both response types (JSON and the TIFF itself) must not be sniffed."""
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"


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
    assert len(pages(response.data)) == 1, (
        "the frames of a multi-page upload were expanded"
    )


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


def test_an_uploaded_page_carries_only_the_tags_the_merge_writes(client, make_tiff):
    """The output page must not inherit the upload's own tag directory.

    Pillow chains a source image's whole tag directory into libtiff: the `_save`
    in TiffImagePlugin.py builds `supplied_tags` from `im.tag` and `im.tag_v2`
    and feeds it to the encoder. Nothing in api/merge.py cleared it, so every
    page of the output carried the upload's XMP packet, Software string, ICC
    profile, resolution and custom tags through unchanged -- attacker-supplied
    bytes arriving back in the file handed to the browser. The tags the merge
    means to write are passed per page as `tiffinfo` and must survive.
    """
    path = make_tiff(
        name="scan.tif",
        tiffinfo={
            700: b"<x:xmpmeta>arbitrary payload</x:xmpmeta>",
            305: "Not This Service 9.9",
            34675: b"\x00" * 32,
            282: 300.0,
            283: 300.0,
            296: 2,
            65000: b"attacker controlled",
            270: "the name the source file carried",
            285: "the description the source file carried",
        },
    )

    response = client.post(
        "/api/merge",
        data={"files": (io.BytesIO(path.read_bytes()), path.name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    image = Image.open(io.BytesIO(response.data))
    image.load()
    assert image.tag_v2.get(270) == "scan.tif"
    assert image.tag_v2.get(285) == "scan.tif"
    for tag in SOURCE_ONLY_TAGS:
        assert tag not in image.tag_v2, f"source tag {tag} reached the output page"
    assert "icc_profile" not in image.info


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
    """A part with no filename is refused, not silently dropped.

    The route used to filter blank-filename parts out before merging, so three
    posted parts with two blank came back 200 with one page: a merge reported
    success after quietly returning less than it was given. There is no way to
    name such a page, and no way to report it without inventing a name, so the
    request is refused instead. The browser never sends one -- src/app/page.js
    only appends the FileList entries it has names for.
    """
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

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "1 of 2" in error
    assert "no filename" in error


def test_unnamed_parts_alone_are_refused_too(client):
    response = client.post(
        "/api/merge",
        data={"files": [(io.BytesIO(b""), ""), (io.BytesIO(b""), "")]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "2 of 2" in response.get_json()["error"]


def test_the_file_cap_counts_every_part_not_only_the_named_ones(
    client, tiff_bytes
):
    """Werkzeug has already parsed every part by the time the route runs.

    The cap used to be applied after blank-filename parts were filtered out, so
    70 parts (30 named, 40 blank) reported "Too many files: 30 uploaded" and
    merged 30 pages -- the count in the message described a subset of the work
    the request had actually caused.
    """
    payload = tiff_bytes()
    files = [(io.BytesIO(payload), f"f{n}.tif") for n in range(5)]
    files += [(io.BytesIO(b""), "") for _ in range(MAX_FILES)]

    response = client.post(
        "/api/merge",
        data={"files": files},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert f"Too many files: {MAX_FILES + 5} uploaded" in error
    assert f"maximum is {MAX_FILES}" in error


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
        "the extension guidance is gone, so the format gate is doing the "
        "suffix gate's job"
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


def test_every_error_response_is_json(client, make_tiff, png_bytes, tmp_path):
    """The API table promises {"error": ...} for every status, so it must hold.

    The route's own rejections were always JSON, but a wrong method and an
    unknown path came straight from Werkzeug as text/html -- so a client that
    parses the error body as JSON, which the UI does, failed on exactly the
    responses a scanner or a stray GET produces.
    """
    good = make_tiff(name="page.tif")
    corrupt = tmp_path / "corrupt.tif"
    corrupt.write_bytes(b"II*\x00 not a real tiff payload")
    empty = tmp_path / "empty.tif"
    empty.write_bytes(b"")
    oversized = b"\x00" * (MAX_REQUEST_BYTES + 1024)

    post = lambda data, **kwargs: client.post(  # noqa: E731
        "/api/merge", data=data, content_type="multipart/form-data", **kwargs
    )
    responses = [
        post({}),
        post({"files": (io.BytesIO(png_bytes()), "photo.png")}),
        post({"files": (io.BytesIO(png_bytes()), "disguised.tif")}),
        post({"files": (io.BytesIO(corrupt.read_bytes()), "corrupt.tif")}),
        post({"files": (io.BytesIO(empty.read_bytes()), "empty.tif")}),
        post({"files": (io.BytesIO(oversized), "huge.tif")}),
        post({"files": (io.BytesIO(good.read_bytes()), "")}),
        client.get("/api/merge"),
        client.put("/api/merge"),
        client.get("/no/such/path"),
        client.post(
            "/api/merge",
            data=b"--zzz--\r\n",
            content_type="multipart/form-data; boundary=zzz",
        ),
    ]

    for response in responses:
        label = f"{response.status_code} {response.request.path}"
        assert response.status_code >= 400, label
        assert response.mimetype == "application/json", (
            f"{label} returned {response.mimetype}, not JSON: "
            f"{response.get_data(as_text=True)[:120]}"
        )
        assert response.get_json()["error"].strip(), label


# (label, limits patched before the request, the requests fired under them).
# /health is read after the patch in every scenario, so the published limits and
# the limits the route enforces are always the same numbers.
DISCLOSURE_SCENARIOS = [
    (
        "the per-image pixel cap",
        {"MAX_IMAGE_PIXELS": 128},
        [(("big.tif", 64, "L"),)],
    ),
    (
        "the per-request pixel budget",
        {"MAX_TOTAL_IMAGE_PIXELS": 128},
        [(("one.tif", 32, "L"), ("two.tif", 32, "L"), ("three.tif", 32, "L"))],
    ),
    (
        "the response ceiling and the mode conflict",
        {"MAX_RESPONSE_BYTES": 2 * 1024, "OUTPUT_COMPRESSION": "raw"},
        [
            (("page.tif", 64, "L"),),
            (("bilevel.tif", 16, "1"), ("palette.tif", 16, "P")),
        ],
    ),
]


def _quotable_numbers(client):
    """Every number /health publishes, in every form a message could render it."""
    published = client.get("/health").get_json()
    quotable = {str(value) for value in published.values()}
    for key in ("max_request_bytes", "max_response_bytes"):
        quotable |= set(
            QUOTABLE_NUMBER.findall(merge_module._format_size(published[key]))
        )
    # Counts and dimensions the request itself supplied: pages, parts, the page
    # number, and the pixel count of the side length posted.
    quotable |= {str(number) for number in range(101)}
    quotable |= {str(side * side) for side in range(1, 65)}
    return quotable


def _disclosure_responses(client, tiff_bytes, png_bytes, tmp_path, batches):
    corrupt = tmp_path / "corrupt.tif"
    corrupt.write_bytes(b"II*\x00 not a real tiff")
    empty = tmp_path / "empty.tif"
    empty.write_bytes(b"")

    def post(data):
        return client.post(
            "/api/merge", data=data, content_type="multipart/form-data"
        )

    def post_files(parts):
        return post(
            {
                "files": [
                    (io.BytesIO(tiff_bytes(mode=mode, size=(side, side))), name)
                    for name, side, mode in parts
                ]
            }
        )

    return [
        post({}),
        post({"files": (io.BytesIO(png_bytes()), "photo.png")}),
        post({"files": (io.BytesIO(png_bytes()), "disguised.tif")}),
        post({"files": (io.BytesIO(corrupt.read_bytes()), "corrupt.tif")}),
        post({"files": (io.BytesIO(empty.read_bytes()), "empty.tif")}),
        post(
            {
                "files": (
                    io.BytesIO(b"\x00" * (MAX_REQUEST_BYTES + 1024)),
                    "huge.tif",
                )
            }
        ),
        post({"files": (io.BytesIO(tiff_bytes()), "")}),
        post_files([(f"f{n}.tif", 32, "L") for n in range(MAX_FILES + 1)]),
        client.get("/api/merge"),
        client.get("/no/such/path"),
        *(post_files(parts) for parts in batches),
    ]


def test_client_errors_quote_nothing_health_does_not_already_publish(
    client, tiff_bytes, png_bytes, tmp_path, monkeypatch
):
    """A 4xx may be useful, and this is what makes being useful acceptable.

    The client errors name the file the uploader just sent and the limit it
    broke, which is exactly what a uploader needs. That is only safe to
    document while the limits are not a secret -- and they are not, because
    GET /health publishes every one of them to the same unauthenticated caller.
    This pins that invariant across the whole 4xx surface, so a future message
    that reaches for a path, a version, a produced byte size, or anything else
    health does not carry fails here rather than shipping.
    """
    for label, patches, batches in DISCLOSURE_SCENARIOS:
        with monkeypatch.context() as patcher:
            for name, value in patches.items():
                patcher.setattr(merge_module, name, value)

            quotable = _quotable_numbers(client)
            responses = _disclosure_responses(
                client, tiff_bytes, png_bytes, tmp_path, batches
            )

            for response in responses:
                assert response.status_code >= 400, f"{label}: {response.request.path}"
                error = response.get_json()["error"]
                unexpected = set(QUOTABLE_NUMBER.findall(error)) - quotable
                assert not unexpected, (
                    f"{label}: {response.status_code} quoted "
                    f"{sorted(unexpected)}, which GET /health does not "
                    f"publish: {error!r}"
                )


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_merge_endpoint_rejects_other_methods(client, method):
    assert client.open("/api/merge", method=method).status_code == 405

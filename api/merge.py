import io
import logging
import os

from flask import Flask, jsonify, request, send_file
from PIL import Image, TiffImagePlugin
from werkzeug.exceptions import RequestEntityTooLarge

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("tiff_merge")

MAX_REQUEST_BYTES = 4 * 1024 * 1024
# Vercel caps a function's request *and* response body at 4.5 MB and answers
# anything larger with 413 FUNCTION_PAYLOAD_TOO_LARGE. The request cap above
# sits under that ceiling so an oversized upload is rejected with a JSON
# message; this one is the same idea for the way out, because a merge can
# re-encode to a larger body than it received and would otherwise fail at the
# edge with no in-app signal.
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_FILES = 20
MAX_IMAGE_PIXELS = 50_000_000
# Pillow's own gate only raises above twice MAX_IMAGE_PIXELS and merely warns
# above it, so it bounds one image at 100M pixels and bounds nothing at all
# across a 20-file request. This is the budget for the decoded pixel data a
# single request may materialise, and it is checked from the TIFF header before
# any page is decoded. At four bytes per pixel it caps the decoded pages of one
# invocation at roughly 200 MB.
MAX_TOTAL_IMAGE_PIXELS = 50_000_000
TIFF_SUFFIXES = (".tif", ".tiff")
OUTPUT_FILENAME = "merged_output.tif"
OUTPUT_MIME = "image/tiff"
OUTPUT_COMPRESSION = "tiff_adobe_deflate"
MUTUALLY_EXCLUSIVE_MODE_GROUPS = ({"1"}, {"P", "PA"})

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class MergeError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _format_size(num_bytes):
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{num_bytes / 1024:.0f} KB"


def _mode_conflict(pages):
    present = {image.mode for _, image in pages}
    matched = [group & present for group in MUTUALLY_EXCLUSIVE_MODE_GROUPS]
    present_groups = [sorted(group) for group in matched if group]
    if len(present_groups) > 1:
        return [mode for group in present_groups for mode in group]
    return None


def merge_images(pages):
    if not pages:
        raise MergeError("No valid TIFF images to merge.")

    conflict = _mode_conflict(pages)
    if conflict:
        raise MergeError(
            "Bilevel (mode 1) and palette (mode P) pages cannot be written "
            "into the same multi-page TIFF. Re-save them in a shared mode, "
            f"for example RGB. Conflicting modes: {', '.join(conflict)}."
        )

    buffer = io.BytesIO()
    try:
        with TiffImagePlugin.AppendingTiffWriter(buffer) as writer:
            for name, image in pages:
                tiffinfo = TiffImagePlugin.ImageFileDirectory_v2()
                tiffinfo[270] = name
                tiffinfo[285] = name
                image.save(
                    writer,
                    format="TIFF",
                    compression=OUTPUT_COMPRESSION,
                    tiffinfo=tiffinfo,
                )
                writer.newFrame()
    except (OSError, ValueError, SyntaxError, KeyError) as exc:
        logger.exception("Failed to encode merged TIFF")
        raise MergeError(
            "These images could not be encoded into a single multi-page TIFF. "
            "Try re-saving them in a common colour mode and compression."
        ) from exc

    payload = buffer.getvalue()
    if len(payload) > MAX_RESPONSE_BYTES:
        raise MergeError(
            f"Merging these files would produce {_format_size(len(payload))}, "
            f"over the {_format_size(MAX_RESPONSE_BYTES)} this service can "
            "return in one response. Merge fewer pages per request, or split "
            "the batch into several smaller merges. Pages are already written "
            "as lossless Deflate, so re-compressing the source files will not "
            "bring the result under the limit.",
            status=413,
        )

    return payload


def _decode_upload(storage, remaining_pixels):
    name = storage.filename
    suffix = os.path.splitext(name)[1].lower()
    if suffix not in TIFF_SUFFIXES:
        raise MergeError(
            f"{name!r} is not a TIFF file. Only .tif and .tiff are accepted."
        )

    try:
        image = Image.open(io.BytesIO(storage.read()))
    except Image.DecompressionBombError as exc:
        logger.warning("Rejected oversized image %r: %s", name, exc)
        raise MergeError(
            f"{name!r} expands to too many pixels to process safely."
        ) from exc
    except Exception as exc:
        logger.warning("Rejected unreadable upload %r: %r", name, exc)
        raise MergeError(f"{name!r} could not be read as a TIFF image.") from exc

    if image.format != "TIFF":
        raise MergeError(f"{name!r} is not a TIFF image.")

    width, height = image.size
    pixels = width * height
    if pixels > MAX_IMAGE_PIXELS:
        logger.warning("Rejected oversized image %r: %d pixels", name, pixels)
        raise MergeError(
            f"{name!r} expands to {pixels} pixels, over the "
            f"{MAX_IMAGE_PIXELS} this service will decode in one image."
        )
    if pixels > remaining_pixels:
        logger.warning(
            "Rejected request over the pixel budget at %r: %d pixels left",
            name,
            remaining_pixels,
        )
        raise MergeError(
            f"{name!r} would take this request past the "
            f"{MAX_TOTAL_IMAGE_PIXELS} pixel budget for a single merge. "
            "Upload fewer pages, or split them into several merges."
        )

    try:
        image.load()
    except Image.DecompressionBombError as exc:
        logger.warning("Rejected oversized image %r on decode: %s", name, exc)
        raise MergeError(
            f"{name!r} expands to too many pixels to process safely."
        ) from exc
    except Exception as exc:
        logger.warning("Rejected undecodable upload %r: %r", name, exc)
        raise MergeError(f"{name!r} contains corrupt TIFF data.") from exc

    return os.path.basename(name), image, pixels


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        max_request_bytes=MAX_REQUEST_BYTES,
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_files=MAX_FILES,
        max_image_pixels=MAX_IMAGE_PIXELS,
        max_total_image_pixels=MAX_TOTAL_IMAGE_PIXELS,
    )


@app.post("/api/merge")
def merge_tiffs():
    if "files" not in request.files:
        return jsonify(error="No files provided."), 400

    uploads = [f for f in request.files.getlist("files") if f.filename]
    if not uploads:
        return jsonify(error="No files selected."), 400

    if len(uploads) > MAX_FILES:
        return jsonify(
            error=f"Too many files: {len(uploads)} uploaded, maximum is {MAX_FILES}."
        ), 400

    pages = []
    remaining_pixels = MAX_TOTAL_IMAGE_PIXELS
    try:
        for storage in uploads:
            name, image, pixels = _decode_upload(storage, remaining_pixels)
            remaining_pixels -= pixels
            pages.append((name, image))
        merged = merge_images(pages)
    except MergeError as exc:
        return jsonify(error=exc.message), exc.status
    except Exception:
        logger.exception("Unhandled error while merging uploads")
        return jsonify(error="Failed to merge images."), 500

    return send_file(
        io.BytesIO(merged),
        mimetype=OUTPUT_MIME,
        as_attachment=True,
        download_name=OUTPUT_FILENAME,
    )


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    return jsonify(
        error=(
            "Upload is too large. The maximum request size is "
            f"{_format_size(MAX_REQUEST_BYTES)}."
        )
    ), 413


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5328)))

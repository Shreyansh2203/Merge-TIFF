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
MAX_FILES = 20
MAX_IMAGE_PIXELS = 50_000_000
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

    return buffer.getvalue()


def _decode_upload(storage):
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

    return os.path.basename(name), image


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        max_request_bytes=MAX_REQUEST_BYTES,
        max_files=MAX_FILES,
        max_image_pixels=MAX_IMAGE_PIXELS,
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
    try:
        for storage in uploads:
            pages.append(_decode_upload(storage))
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
    limit_mb = MAX_REQUEST_BYTES // (1024 * 1024)
    return jsonify(
        error=f"Upload is too large. The maximum request size is {limit_mb} MB."
    ), 413


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5328)))

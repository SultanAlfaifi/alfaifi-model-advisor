from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "mustakshif-logo.svg"
PNG_OUTPUT = ASSETS / "mustakshif-icon.png"
ICO_OUTPUT = ASSETS / "mustakshif.ico"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    payload = QByteArray()
    buffer = QBuffer(payload)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Could not encode the {size}px brand asset.")
    return bytes(payload)


def write_ico(images: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(images))
    data_offset = 6 + 16 * len(images)
    entries: list[bytes] = []
    payloads: list[bytes] = []

    for size, payload in images:
        icon_size = 0 if size == 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                icon_size,
                icon_size,
                0,
                0,
                1,
                32,
                len(payload),
                data_offset,
            )
        )
        payloads.append(payload)
        data_offset += len(payload)

    ICO_OUTPUT.write_bytes(header + b"".join(entries) + b"".join(payloads))


def main() -> None:
    renderer = QSvgRenderer(str(SOURCE))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG source: {SOURCE}")

    PNG_OUTPUT.write_bytes(render_png(renderer, 1024))
    write_ico([(size, render_png(renderer, size)) for size in ICO_SIZES])
    print(f"Rendered {PNG_OUTPUT}")
    print(f"Rendered {ICO_OUTPUT} with {len(ICO_SIZES)} sizes")


if __name__ == "__main__":
    main()

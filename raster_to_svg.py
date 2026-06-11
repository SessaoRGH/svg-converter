#!/usr/bin/env python3
"""Convert common raster image files into faithful SVG wrappers.

This tool preserves the original raster image bytes inside an SVG file. That is
the only reliable way to keep the same pixels, colors, transparency, and JPEG
compression characteristics when converting photos or raster artwork to SVG.
"""

from __future__ import annotations

import argparse
import base64
import html
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".jfif",
    ".webp",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".ico",
}
MIME_BY_KIND = {
    "bmp": "image/bmp",
    "gif": "image/gif",
    "ico": "image/x-icon",
    "png": "image/png",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "webp": "image/webp",
}


@dataclass(frozen=True)
class ImageInfo:
    width: int
    height: int
    kind: str
    mime: str


class ConversionError(Exception):
    """Raised when a file cannot be converted safely."""


def read_image_info(path: Path) -> ImageInfo:
    data = path.read_bytes()

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        kind = "png"
        width, height = read_png_size(data)
    elif data.startswith(b"\xff\xd8"):
        kind = "jpeg"
        width, height = read_jpeg_size(data)
    elif data[:6] in {b"GIF87a", b"GIF89a"}:
        kind = "gif"
        width, height = read_gif_size(data)
    elif data.startswith(b"BM"):
        kind = "bmp"
        width, height = read_bmp_size(data)
    elif is_tiff(data):
        kind = "tiff"
        width, height = read_tiff_size(data)
    elif is_webp(data):
        kind = "webp"
        width, height = read_webp_size(data)
    elif is_ico(data):
        kind = "ico"
        width, height = read_ico_size(data)
    else:
        raise ConversionError(
            f"{path} nao parece ser uma imagem suportada valida."
        )

    return ImageInfo(
        width=width,
        height=height,
        kind=kind,
        mime=MIME_BY_KIND[kind],
    )


def read_png_size(data: bytes) -> tuple[int, int]:
    signature = b"\x89PNG\r\n\x1a\n"
    if len(data) < 24 or not data.startswith(signature):
        raise ConversionError("PNG invalido ou incompleto.")

    chunk_type = data[12:16]
    if chunk_type != b"IHDR":
        raise ConversionError("PNG sem bloco IHDR esperado.")

    width, height = struct.unpack(">II", data[16:24])
    if width <= 0 or height <= 0:
        raise ConversionError("PNG com dimensoes invalidas.")
    return width, height


def read_gif_size(data: bytes) -> tuple[int, int]:
    if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ConversionError("GIF invalido ou incompleto.")

    width, height = struct.unpack("<HH", data[6:10])
    return require_valid_size(width, height, "GIF")


def read_bmp_size(data: bytes) -> tuple[int, int]:
    if len(data) < 26 or not data.startswith(b"BM"):
        raise ConversionError("BMP invalido ou incompleto.")

    dib_header_size = struct.unpack("<I", data[14:18])[0]
    if dib_header_size == 12:
        if len(data) < 26:
            raise ConversionError("BMP CORE invalido ou incompleto.")
        width, height = struct.unpack("<HH", data[18:22])
    elif dib_header_size >= 40:
        if len(data) < 26:
            raise ConversionError("BMP invalido ou incompleto.")
        width, height = struct.unpack("<ii", data[18:26])
    else:
        raise ConversionError("BMP com cabecalho DIB nao suportado.")

    return require_valid_size(width, abs(height), "BMP")


def read_jpeg_size(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ConversionError("JPEG invalido ou incompleto.")

    offset = 2
    while offset < len(data):
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1

        if offset >= len(data):
            break

        marker = data[offset]
        offset += 1

        # Standalone markers without a payload length.
        if marker in {0x01, *range(0xD0, 0xD8), 0xD9}:
            continue

        if offset + 2 > len(data):
            break

        segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
        if segment_length < 2:
            raise ConversionError("JPEG com segmento invalido.")

        segment_start = offset + 2
        segment_end = offset + segment_length
        if segment_end > len(data):
            break

        if is_start_of_frame(marker):
            if segment_start + 5 > len(data):
                break
            height, width = struct.unpack(
                ">HH", data[segment_start + 1 : segment_start + 5]
            )
            if width <= 0 or height <= 0:
                raise ConversionError("JPEG com dimensoes invalidas.")
            return width, height

        offset = segment_end

    raise ConversionError("Nao foi possivel ler as dimensoes do JPEG.")


def is_tiff(data: bytes) -> bool:
    return data.startswith(b"II*\x00") or data.startswith(b"MM\x00*")


def read_tiff_size(data: bytes) -> tuple[int, int]:
    if len(data) < 8 or not is_tiff(data):
        raise ConversionError("TIFF invalido ou incompleto.")

    endian = "<" if data.startswith(b"II") else ">"
    ifd_offset = struct.unpack(endian + "I", data[4:8])[0]
    if ifd_offset + 2 > len(data):
        raise ConversionError("TIFF sem IFD valido.")

    entry_count = struct.unpack(endian + "H", data[ifd_offset : ifd_offset + 2])[0]
    width: int | None = None
    height: int | None = None
    cursor = ifd_offset + 2

    for _ in range(entry_count):
        if cursor + 12 > len(data):
            raise ConversionError("TIFF com entrada IFD incompleta.")

        tag, value_type, count = struct.unpack(endian + "HHI", data[cursor : cursor + 8])
        raw_value = data[cursor + 8 : cursor + 12]

        if tag in {256, 257} and count >= 1:
            value = read_tiff_inline_value(raw_value, value_type, endian)
            if tag == 256:
                width = value
            else:
                height = value

        cursor += 12

    if width is None or height is None:
        raise ConversionError("TIFF sem tags de largura/altura.")

    return require_valid_size(width, height, "TIFF")


def read_tiff_inline_value(raw_value: bytes, value_type: int, endian: str) -> int:
    if value_type == 3:
        return struct.unpack(endian + "H", raw_value[:2])[0]
    if value_type == 4:
        return struct.unpack(endian + "I", raw_value)[0]
    if value_type == 8:
        return struct.unpack(endian + "h", raw_value[:2])[0]
    if value_type == 9:
        return struct.unpack(endian + "i", raw_value)[0]
    raise ConversionError("TIFF com tipo de dimensao nao suportado.")


def is_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def read_webp_size(data: bytes) -> tuple[int, int]:
    if not is_webp(data):
        raise ConversionError("WebP invalido ou incompleto.")

    offset = 12
    while offset + 8 <= len(data):
        chunk_type = data[offset : offset + 4]
        chunk_size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        payload = offset + 8
        payload_end = payload + chunk_size

        if payload_end > len(data):
            raise ConversionError("WebP com chunk incompleto.")

        if chunk_type == b"VP8X":
            return read_webp_vp8x_size(data[payload:payload_end])
        if chunk_type == b"VP8L":
            return read_webp_vp8l_size(data[payload:payload_end])
        if chunk_type == b"VP8 ":
            return read_webp_vp8_size(data[payload:payload_end])

        offset = payload_end + (chunk_size % 2)

    raise ConversionError("Nao foi possivel ler as dimensoes do WebP.")


def read_webp_vp8x_size(payload: bytes) -> tuple[int, int]:
    if len(payload) < 10:
        raise ConversionError("WebP VP8X incompleto.")

    width = 1 + int.from_bytes(payload[4:7], "little")
    height = 1 + int.from_bytes(payload[7:10], "little")
    return require_valid_size(width, height, "WebP")


def read_webp_vp8l_size(payload: bytes) -> tuple[int, int]:
    if len(payload) < 5 or payload[0] != 0x2F:
        raise ConversionError("WebP VP8L incompleto.")

    b0, b1, b2, b3 = payload[1:5]
    width = 1 + (((b1 & 0x3F) << 8) | b0)
    height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
    return require_valid_size(width, height, "WebP")


def read_webp_vp8_size(payload: bytes) -> tuple[int, int]:
    if len(payload) < 10 or payload[3:6] != b"\x9d\x01\x2a":
        raise ConversionError("WebP VP8 incompleto.")

    width = struct.unpack("<H", payload[6:8])[0] & 0x3FFF
    height = struct.unpack("<H", payload[8:10])[0] & 0x3FFF
    return require_valid_size(width, height, "WebP")


def is_ico(data: bytes) -> bool:
    return len(data) >= 6 and data[:4] == b"\x00\x00\x01\x00"


def read_ico_size(data: bytes) -> tuple[int, int]:
    if len(data) < 22 or not is_ico(data):
        raise ConversionError("ICO invalido ou incompleto.")

    image_count = struct.unpack("<H", data[4:6])[0]
    if image_count < 1:
        raise ConversionError("ICO sem imagens.")

    width = data[6] or 256
    height = data[7] or 256
    return require_valid_size(width, height, "ICO")


def require_valid_size(width: int, height: int, format_name: str) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ConversionError(f"{format_name} com dimensoes invalidas.")
    return width, height


def is_start_of_frame(marker: int) -> bool:
    return marker in {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }


def svg_for_image(path: Path, info: ImageInfo, *, title: str | None) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    safe_title = html.escape(title if title is not None else path.name)

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{info.width}" height="{info.height}" '
                f'viewBox="0 0 {info.width} {info.height}" '
                f'role="img" aria-labelledby="title">'
            ),
            f"  <title id=\"title\">{safe_title}</title>",
            (
                f'  <image x="0" y="0" width="{info.width}" '
                f'height="{info.height}" preserveAspectRatio="none" '
                f'href="data:{info.mime};base64,{encoded}" '
                f'xlink:href="data:{info.mime};base64,{encoded}" />'
            ),
            "</svg>",
            "",
        ]
    )


def output_path_for(
    input_path: Path,
    output: Path | None,
    *,
    output_is_directory: bool,
) -> Path:
    if output is None:
        return input_path.with_suffix(".svg")

    if output_is_directory or (output.exists() and output.is_dir()):
        return output / input_path.with_suffix(".svg").name

    if output.suffix.lower() == ".svg":
        return output

    return output


def iter_input_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        if item.is_dir():
            files.extend(
                path
                for path in sorted(item.rglob("*"))
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        elif item.is_file():
            files.append(item)
        else:
            raise ConversionError(f"Entrada nao encontrada: {item}")
    return files


def convert_file(
    input_path: Path,
    *,
    output: Path | None,
    output_is_directory: bool,
    overwrite: bool,
    title: str | None,
) -> Path:
    info = read_image_info(input_path)
    destination = output_path_for(
        input_path,
        output,
        output_is_directory=output_is_directory,
    )

    if destination.exists() and not overwrite:
        raise ConversionError(
            f"{destination} ja existe. Use --overwrite para substituir."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        svg_for_image(input_path, info, title=title),
        encoding="utf-8",
        newline="\n",
    )
    return destination


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Converte imagens raster para SVG preservando a imagem original "
            "embutida em base64."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Arquivo(s) de imagem ou pasta(s) para converter.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help=(
            "Arquivo SVG de saida para uma entrada, ou pasta de saida para "
            "multiplas entradas."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Substitui arquivos SVG existentes.",
    )
    parser.add_argument(
        "--title",
        help="Titulo acessivel a incluir no SVG. Por padrao usa o nome do arquivo.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        inputs = iter_input_files(args.inputs)
        if not inputs:
            raise ConversionError("Nenhuma imagem suportada encontrada.")

        if (
            len(inputs) > 1
            and args.output is not None
            and args.output.suffix.lower() == ".svg"
        ):
            raise ConversionError(
                "Para varias entradas, --output deve ser uma pasta, nao um arquivo .svg."
            )

        output_is_directory = len(inputs) > 1

        for input_path in inputs:
            destination = convert_file(
                input_path,
                output=args.output,
                output_is_directory=output_is_directory,
                overwrite=args.overwrite,
                title=args.title,
            )
            print(f"Convertido: {input_path} -> {destination}")

        return 0
    except ConversionError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

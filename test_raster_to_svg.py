import base64
import re
import struct
import tempfile
import unittest
from pathlib import Path

from raster_to_svg import convert_file, read_image_info


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)

JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9oADAMBAAIAAwAAAB//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/EF//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/EF//xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/EF//2Q=="
)
GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAPAAAP///wAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw=="
)
WEBP_VP8X_1X1 = (
    b"RIFF"
    + struct.pack("<I", 22)
    + b"WEBPVP8X"
    + struct.pack("<I", 10)
    + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
)
BMP_1X1 = (
    b"BM"
    + struct.pack("<IHHI", 58, 0, 0, 54)
    + struct.pack("<IiiHHIIiiII", 40, 1, 1, 1, 24, 4, 0, 0, 0, 0, 0)
    + b"\x00\x00\x00\x00"
)
TIFF_1X1 = (
    b"II*\x00"
    + struct.pack("<I", 8)
    + struct.pack("<H", 2)
    + struct.pack("<HHII", 256, 4, 1, 1)
    + struct.pack("<HHII", 257, 4, 1, 1)
    + struct.pack("<I", 0)
)
ICO_1X1 = (
    b"\x00\x00\x01\x00"
    + struct.pack("<H", 1)
    + b"\x01\x01\x00\x00"
    + struct.pack("<HHII", 1, 32, 0, 22)
)


class RasterToSvgTests(unittest.TestCase):
    def test_reads_png_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pixel.png"
            path.write_bytes(PNG_1X1)

            info = read_image_info(path)

            self.assertEqual(info.width, 1)
            self.assertEqual(info.height, 1)
            self.assertEqual(info.mime, "image/png")

    def test_converts_png_to_svg_with_embedded_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pixel.png"
            path.write_bytes(PNG_1X1)

            output = convert_file(
                path,
                output=None,
                output_is_directory=False,
                overwrite=False,
                title=None,
            )
            svg = output.read_text(encoding="utf-8")

            self.assertIn('width="1" height="1"', svg)
            match = re.search(r"data:image/png;base64,([^\" ]+)", svg)
            self.assertIsNotNone(match)
            self.assertEqual(base64.b64decode(match.group(1)), PNG_1X1)

    def test_converts_to_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "pixel.png"
            output_dir = Path(temp_dir) / "svgs"
            input_path.write_bytes(PNG_1X1)

            output = convert_file(
                input_path,
                output=output_dir,
                output_is_directory=True,
                overwrite=False,
                title=None,
            )

            self.assertEqual(output, output_dir / "pixel.svg")
            self.assertTrue(output.exists())

    def test_reads_jpeg_size(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pixel.jpg"
            path.write_bytes(JPEG_1X1)

            info = read_image_info(path)

            self.assertEqual(info.width, 1)
            self.assertEqual(info.height, 1)
            self.assertEqual(info.mime, "image/jpeg")

    def test_reads_common_extra_formats(self):
        samples = {
            "pixel.gif": (GIF_1X1, "image/gif"),
            "pixel.webp": (WEBP_VP8X_1X1, "image/webp"),
            "pixel.bmp": (BMP_1X1, "image/bmp"),
            "pixel.tiff": (TIFF_1X1, "image/tiff"),
            "pixel.ico": (ICO_1X1, "image/x-icon"),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            for filename, (content, mime) in samples.items():
                path = Path(temp_dir) / filename
                path.write_bytes(content)

                info = read_image_info(path)

                self.assertEqual(info.width, 1, filename)
                self.assertEqual(info.height, 1, filename)
                self.assertEqual(info.mime, mime, filename)


if __name__ == "__main__":
    unittest.main()

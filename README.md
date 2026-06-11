Python tool to convert raster images to SVG without altering pixels,
colors, transparency, or the original compression.

Supported formats: `.png`, `.jpg`, `.jpeg`, `.jfif`, `.webp`, `.gif`, `.bmp`,
`.tif`, `.tiff`, and `.ico`.

Important: Photos and raster images do not become true vectors without loss.
Vectorization requires interpreting and redrawing the image, which can alter details and
colors. That is why this tool creates an SVG with the original image embedded in
base64. The result opens as an SVG but faithfully preserves the original image.

## Usage

Convert a file:

```powershell
python .\raster_to_svg.py .\image.png
```

Choose the output file:

```powershell
python .\raster_to_svg.py .\image.webp -o .\image.svg
```

Convert an entire folder:

```powershell
python .\raster_to_svg.py .\my-images -o .\svgs
```

Overwrite existing SVGs:

```powershell
python .\raster_to_svg.py .\my-images -o .\svgs --overwrite
```

## Requirements

Python 3.10 or higher. No external libraries need to be installed.

# Conversor fiel de imagens raster para SVG

Ferramenta Python para converter imagens raster em SVG sem alterar pixels,
cores, transparencia ou compressao original.

Formatos suportados: `.png`, `.jpg`, `.jpeg`, `.jfif`, `.webp`, `.gif`, `.bmp`,
`.tif`, `.tiff` e `.ico`.

Importante: fotos e imagens raster nao viram vetores reais sem perda.
Vetorizar exige interpretar e redesenhar a imagem, o que pode mudar detalhes e
cores. Por isso esta ferramenta cria um SVG com a imagem original embutida em
base64. O resultado abre como SVG, mas preserva fielmente a imagem original.

## Uso

Converter um arquivo:

```powershell
python .\raster_to_svg.py .\imagem.png
```

Escolher o arquivo de saida:

```powershell
python .\raster_to_svg.py .\imagem.webp -o .\imagem.svg
```

Converter uma pasta inteira:

```powershell
python .\raster_to_svg.py .\minhas-imagens -o .\svgs
```

Substituir SVGs existentes:

```powershell
python .\raster_to_svg.py .\minhas-imagens -o .\svgs --overwrite
```

## Requisitos

Python 3.10 ou superior. Nao precisa instalar bibliotecas externas.

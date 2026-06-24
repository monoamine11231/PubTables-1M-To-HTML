<h1 align="center" style="display: block; font-size: 2.5em; font-weight: bold; margin-block-start: 1em; margin-block-end: 1em; border-bottom: 0">
    <strong>PubTables-1M-To-HTML</strong><br/>
    <img align="center" src="https://raw.githubusercontent.com/monoamine11231/PubTables-1M-To-HTML/refs/heads/gh-badges/badge-tests.svg"/>
    <img align="center" src="https://raw.githubusercontent.com/monoamine11231/PubTables-1M-To-HTML/refs/heads/gh-badges/badge-coverage.svg"/>
    <a href="https://huggingface.co/datasets/monoamine11231/pubtables-1m-html"><img align="center" src="https://img.shields.io/badge/-HuggingFace-3B4252?style=flat&logo=huggingface&logoColor="/></a>
</h1>

## Introduction
This is a Python script used to convert the table XML annotations together with the JSON token annotations from [bsmock/pubtables-1m](https://huggingface.co/datasets/bsmock/pubtables-1m) to their HTML representations.

If you are looking for the **dataset files**, they can be found [here](https://huggingface.co/datasets/monoamine11231/pubtables-1m-html).

## Installation
Make sure you have [uv](https://github.com/astral-sh/uv) installed. After that, run `uv sync`.

## Usage
The Python script has 2 options:
- Convert the table XML annotations together with the JSON token annotations into HTML table representations.
- Inspect the produced HTML conversions by creating a HTML document that integrates the original table images with the produced HTML representations.

### Conversion
To make a conversion of the given annotations to HTML representations, please run:
```bash
uv run main.py convert [-h] --xml-dir XML_DIR --json-dir JSON_DIR [--output-dir OUTPUT_DIR]
```

- `XML_DIR` is the directory containing all the XML table annotations without any folder sub-structures. 
- `JSON_DIR` is the directory containing all the JSON token annotations without any folder sub-structures.

### Inspection
To make an inspection of the produced HTML representations by converting the given table annotations, please run:
```bash
uv run main.py inspect [-h] --xml-dir XML_DIR --json-dir JSON_DIR [--images-dir IMAGES_DIR] [-n N] [--output OUTPUT]
```

- `XML_DIR` is the directory containing all the XML table annotations without any folder sub-structures. 
- `JSON_DIR` is the directory containing all the JSON token annotations without any folder sub-structures.
- `IMAGES_DIR` is the directory containing all the image files of the original tables without any folder sub-structures.

## Structure
The HTML table representations have a structural format which includes bound-boxes of table cells and table rows, and marks the explicitely the header (if existant) and body parts of the table, as it can be seen below.

```html
<table>
	<thead>
		<tr bbox="[36, 36, 247, 52]">
			<th bbox="[36, 36, 130, 52]">Protein</th>
			<th bbox="[130, 36, 247, 52]">Percentage</th>
		</tr>
	</thead>
	<tbody>
		<tr bbox="[36, 52, 247, 72]">
			<td bbox="[36, 52, 130, 72]">PCNA</td>
			<td bbox="[130, 52, 247, 72]">15.93 ± 4.38</td>
		</tr>
		<tr bbox="[36, 72, 247, 92]">
			<td bbox="[36, 72, 130, 92]">hMLH1</td>
			<td bbox="[130, 72, 247, 92]">0.25 ± 1.11</td>
		</tr>
		<tr bbox="[36, 92, 247, 111]">
			<td bbox="[36, 92, 130, 111]">hPMS1</td>
			<td bbox="[130, 92, 247, 111]">0.6 ± 0.99</td>
		</tr>
		<tr bbox="[36, 111, 247, 131]">
			<td bbox="[36, 111, 130, 131]">hPMS2</td>
			<td bbox="[130, 111, 247, 131]">0 ± 0</td>
		</tr>
		<tr bbox="[36, 131, 247, 151]">
			<td bbox="[36, 131, 130, 151]">hMSH2</td>
			<td bbox="[130, 131, 247, 151]">72.7 ± 20.33</td>
		</tr>
		<tr bbox="[36, 151, 247, 166]">
			<td bbox="[36, 151, 130, 166]">TP53</td>
			<td bbox="[130, 151, 247, 166]">0 ± 0</td>
		</tr>
	</tbody>
</table>
```

## Limitations

It is important to understand that the Python script has a set of limitations which are listed below:
1. The script doesn't include any styling data about the table cell and the table cell text, e.g., border, color, text properties such as boldness, etc.
2. The script doesn't differentiate between normal text, superscript and subscript.
3. The script identifies the matching column(s) and row(s) of a set of text tokens by the overlapping coordinates only, thus 'spanning cell' and 'projected row' annotations **are not** taken in account. 

The second limitation is planned to be fixed in the near future by the use of external OCR engines.

## Contributions
All contributions to this project are welcome! Feel free to start an issue or create a PR!

## License
General MIT License, please review it [here](https://github.com/monoamine11231/PubTables-1M-To-HTML/blob/master/LICENSE).
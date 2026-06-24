import argparse
import base64
import random
from pathlib import Path

from tqdm import tqdm

from extract import extract_table_data, convert2html


def find_matching_samples(
    xml_dir: Path, json_dir: Path, images_dir: Path | None, n: int | None
) -> list[str]:
    xmls = {p.stem for p in xml_dir.glob("*.xml")}
    jsons = {p.stem.removesuffix("_words") for p in json_dir.glob("*_words.json")}

    common = xmls & jsons
    if images_dir:
        images = {p.stem for p in images_dir.glob("*.jpg")}
        common &= images

    common = sorted(common)
    if n is None:
        return common
    random.seed(42)
    return random.sample(common, min(n, len(common)))


def image_to_data_uri(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/jpeg;base64,{data}"


def cmd_convert(args: argparse.Namespace):
    xml_dir = Path(args.xml_dir)
    json_dir = Path(args.json_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(xml_dir.glob("*.xml"))
    if not xml_files:
        print(f"No XML files found in {xml_dir}")
        return

    for xml_path in tqdm(xml_files, desc="Converting"):
        stem = xml_path.stem
        json_path = json_dir / f"{stem}_words.json"

        if not json_path.exists():
            tqdm.write(f"  Skipping {stem}: no matching JSON file")
            continue

        try:
            header_rows, table_rows, table_columns, cells = extract_table_data(
                xml_path, json_path
            )
            table_html = convert2html(header_rows, table_rows, table_columns, cells)
        except Exception as e:
            tqdm.write(f"  Error processing {stem}: {e}")
            continue

        out_path = output_dir / f"{stem}.html"
        out_path.write_text(table_html)

    print(f"Output written to {output_dir}")


def cmd_inspect(args: argparse.Namespace):
    xml_dir = Path(args.xml_dir)
    json_dir = Path(args.json_dir)
    images_dir = Path(args.images_dir) if args.images_dir else None
    output_file = Path(args.output)
    n = args.n

    samples = find_matching_samples(xml_dir, json_dir, images_dir, n)

    rows_html: list[str] = []
    for i, stem in enumerate(tqdm(samples, desc="Inspecting"), 1):
        xml_path = xml_dir / f"{stem}.xml"
        json_path = json_dir / f"{stem}_words.json"

        try:
            header_rows, table_rows, table_columns, cells = extract_table_data(
                xml_path, json_path
            )
            table_html = convert2html(header_rows, table_rows, table_columns, cells)
        except Exception as e:
            table_html = f"<p style='color:red;'>Error: {e}</p>"

        image_cell = ""
        if images_dir:
            image_path = images_dir / f"{stem}.jpg"
            img_uri = image_to_data_uri(image_path)
            image_cell = f'<td class="image-cell"><img src="{img_uri}"></td>'

        rows_html.append(f"""
        <tr>
            <td class="index">{i}</td>
            <td class="label">{stem}</td>
            {image_cell}
            <td class="table-cell">{table_html}</td>
        </tr>""")

    page = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>PubTables-1M Conversion Comparison</title>
<style>
body {{ font-family: sans-serif; margin: 20px; }}
h1 {{ text-align: center; }}
.comparison {{ width: 100%; border-collapse: collapse; }}
.comparison th, .comparison td {{ border: 1px solid #ccc; padding: 8px; vertical-align: top; }}
.comparison th {{ background: #f5f5f5; position: sticky; top: 0; }}
.index {{ width: 30px; text-align: center; }}
.label {{ width: 200px; font-size: 0.85em; word-break: break-all; }}
.image-cell img {{ max-width: 500px; height: auto; }}
.table-cell table {{ border-collapse: collapse; font-size: 0.85em; }}
.table-cell td, .table-cell th {{ border: 1px solid #999; padding: 4px; }}
</style>
</head>
<body>
<h1>PubTables-1M: {"Image vs " if images_dir else ""}Converted HTML Table</h1>
<table class="comparison">
<thead><tr>
    <th>#</th>
    <th>ID</th>
    {"<th>Original Image</th>" if images_dir else ""}
    <th>Converted HTML Table</th>
</tr></thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</body>
</html>"""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(page)
    print(f"Output written to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert PubTables-1M annotations to HTML tables"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # convert subcommand
    convert_parser = subparsers.add_parser(
        "convert", help="Batch convert XML+JSON annotations to HTML table files"
    )
    convert_parser.add_argument(
        "--xml-dir", required=True, help="Directory containing XML annotation files"
    )
    convert_parser.add_argument(
        "--json-dir", required=True, help="Directory containing JSON word files"
    )
    convert_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for output HTML files (default: output)",
    )

    # inspect subcommand
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Generate a visual comparison HTML page for N random samples",
    )
    inspect_parser.add_argument(
        "--xml-dir", required=True, help="Directory containing XML annotation files"
    )
    inspect_parser.add_argument(
        "--json-dir", required=True, help="Directory containing JSON word files"
    )
    inspect_parser.add_argument(
        "--images-dir", help="Directory containing table images (optional)"
    )
    inspect_parser.add_argument(
        "-n", type=int, default=None, help="Number of samples to inspect (default: all)"
    )
    inspect_parser.add_argument(
        "--output",
        default="inspection.html",
        help="Output HTML file path (default: inspection.html)",
    )

    args = parser.parse_args()

    if args.command == "convert":
        cmd_convert(args)
    elif args.command == "inspect":
        cmd_inspect(args)


if __name__ == "__main__":
    main()

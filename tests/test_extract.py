import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from extract import (
    Bbox,
    TableCell,
    extract_structure_annotations,
    extract_token_annotations,
    find_or_raise,
    convert2html,
    extract_table_data,
)


class TestTableCell:
    def test_basic_creation(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 10, 10))
        assert cell.colspan == 1
        assert cell.rowspan == 1
        assert cell.bbox == (0, 0, 10, 10)

    def test_multispan_creation(self) -> None:
        cell = TableCell(colspan=(0, 1, 2), rowspan=(0, 1), bbox=(0, 0, 30, 20))
        assert cell.colspan == 3
        assert cell.rowspan == 2

    def test_non_sequential_colspan_raises(self) -> None:
        with pytest.raises(
            ValueError, match="doesn't span the table grid sequentially"
        ):
            TableCell(colspan=(0, 2), rowspan=(0,), bbox=(0, 0, 10, 10))

    def test_non_sequential_rowspan_raises(self) -> None:
        with pytest.raises(
            ValueError, match="doesn't span the table grid sequentially"
        ):
            TableCell(colspan=(0,), rowspan=(0, 2), bbox=(0, 0, 10, 10))

    def test_append_token_and_finalize(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 20, 10))
        cell.append_token({"text": "hello", "bbox": (0, 0, 10, 10), "span_num": 0})
        cell.append_token({"text": "world", "bbox": (10, 0, 20, 10), "span_num": 1})
        cell.finalize()
        assert cell.text == "hello world"

    def test_finalize_sorts_by_span_num(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 20, 10))
        cell.append_token({"text": "second", "bbox": (10, 0, 20, 10), "span_num": 1})
        cell.append_token({"text": "first", "bbox": (0, 0, 10, 10), "span_num": 0})
        cell.finalize()
        assert cell.text == "first second"

    def test_expand_span_merges_columns(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 10, 10))
        cell.expand_span(colspan=(1, 2), rowspan=(0,))
        assert cell.colspan == 3
        assert cell.colspan_indices == (0, 1, 2)
        assert cell.rowspan == 1

    def test_expand_span_merges_rows(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 10, 10))
        cell.expand_span(colspan=(0,), rowspan=(1, 2))
        assert cell.rowspan == 3
        assert cell.rowspan_indices == (0, 1, 2)
        assert cell.colspan == 1

    def test_expand_span_merges_both(self) -> None:
        cell = TableCell(colspan=(0, 1), rowspan=(0,), bbox=(0, 0, 20, 10))
        cell.expand_span(colspan=(2,), rowspan=(1,))
        assert cell.colspan == 3
        assert cell.colspan_indices == (0, 1, 2)
        assert cell.rowspan == 2
        assert cell.rowspan_indices == (0, 1)

    def test_expand_span_deduplicates(self) -> None:
        cell = TableCell(colspan=(0, 1), rowspan=(0, 1), bbox=(0, 0, 20, 20))
        cell.expand_span(colspan=(0, 1, 2), rowspan=(0, 1))
        assert cell.colspan == 3
        assert cell.colspan_indices == (0, 1, 2)
        assert cell.rowspan == 2
        assert cell.rowspan_indices == (0, 1)


class TestConvert2Html:
    def test_empty_cells_returns_empty(self) -> None:
        result = convert2html([], [(0, 0, 10, 10)], [(0, 0, 10, 10)], {})
        assert result == ""

    def test_single_cell_table(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 10, 10))
        cell.append_token({"text": "data", "bbox": (0, 0, 10, 10), "span_num": 0})
        cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: cell}}
        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 100, 20)],
            cols_bbox=[(0, 0, 100, 20)],
            cells=cells,
        )
        table = ET.fromstring(result)
        assert table.tag == "table"

        tbody = table.find("tbody")
        assert tbody is not None

        tr = tbody.find("tr")
        assert tr is not None
        assert tr.get("bbox") == "[0, 0, 100, 20]"

        td = tr.find("td")
        assert td is not None
        assert td.text == "data"
        assert td.get("bbox") == "[0, 0, 10, 10]"

    def test_header_row_uses_th(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 10, 10))
        cell.append_token({"text": "header", "bbox": (0, 0, 10, 10), "span_num": 0})
        cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: cell}}
        result = convert2html(
            header_rows=[0],
            rows_bbox=[(0, 0, 100, 20)],
            cols_bbox=[(0, 0, 100, 20)],
            cells=cells,
        )
        table = ET.fromstring(result)

        thead = table.find("thead")
        assert thead is not None

        th = thead.find(".//th")
        assert th is not None
        assert th.text == "header"

    def test_single_colspan_attribute(self) -> None:
        cell = TableCell(colspan=(0, 1), rowspan=(0,), bbox=(0, 0, 20, 10))
        cell.append_token({"text": "wide", "bbox": (0, 0, 20, 10), "span_num": 0})
        cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: cell}}
        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 100, 10)],
            cols_bbox=[(0, 0, 10, 10), (10, 0, 20, 10)],
            cells=cells,
        )
        table = ET.fromstring(result)
        td = table.find(".//td")
        assert td is not None
        assert td.get("colspan") == "2"
        assert td.get("rowspan") is None

    def test_single_rowspan_attribute(self) -> None:
        cell = TableCell(colspan=(0,), rowspan=(0, 1), bbox=(0, 0, 10, 20))
        cell.append_token({"text": "tall", "bbox": (0, 0, 10, 20), "span_num": 0})
        cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: cell}}
        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 100, 10), (0, 10, 100, 20)],
            cols_bbox=[(0, 0, 10, 20)],
            cells=cells,
        )
        table = ET.fromstring(result)
        td = table.find(".//td")
        assert td is not None
        assert td.get("rowspan") == "2"
        assert td.get("colspan") is None

    def test_single_colspan_and_rowspan_attribute(self) -> None:
        cell = TableCell(colspan=(0, 1), rowspan=(0, 1), bbox=(0, 0, 20, 20))
        cell.append_token({"text": "big", "bbox": (0, 0, 20, 20), "span_num": 0})
        cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: cell}}
        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 100, 10), (0, 10, 100, 20)],
            cols_bbox=[(0, 0, 10, 20), (10, 0, 20, 20)],
            cells=cells,
        )
        table = ET.fromstring(result)
        td = table.find(".//td")
        assert td is not None
        assert td.get("rowspan") == "2"
        assert td.get("colspan") == "2"

    def test_empty_cells_get_empty_td(self) -> None:
        cell = TableCell(colspan=(1,), rowspan=(0,), bbox=(50, 0, 100, 20))
        cell.append_token({"text": "B", "bbox": (50, 0, 100, 20), "span_num": 0})
        cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {1: cell}}
        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 100, 20)],
            cols_bbox=[(0, 0, 50, 20), (50, 0, 100, 20)],
            cells=cells,
        )
        table = ET.fromstring(result)
        tds = table.findall(".//td")
        assert len(tds) == 2
        assert tds[0].text is None
        assert tds[0].get("bbox") is None
        assert tds[1].text == "B"

    def test_header_and_body_separation(self) -> None:
        header_cell = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 10, 10))
        header_cell.append_token(
            {"text": "<ABCD>", "bbox": (0, 0, 10, 10), "span_num": 0}
        )
        header_cell.finalize()

        body_cell = TableCell(colspan=(0,), rowspan=(1,), bbox=(0, 20, 10, 30))
        body_cell.append_token(
            {"text": "<EFGH>", "bbox": (0, 20, 10, 30), "span_num": 0}
        )
        body_cell.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: header_cell}, 1: {0: body_cell}}
        result = convert2html(
            header_rows=[0],
            rows_bbox=[(0, 0, 100, 20), (0, 20, 100, 40)],
            cols_bbox=[(0, 0, 100, 40)],
            cells=cells,
        )
        table = ET.fromstring(result)

        thead = table.find("thead")
        tbody = table.find("tbody")
        assert thead is not None
        assert tbody is not None

        assert len(thead.findall("tr")) == 1
        assert len(tbody.findall("tr")) == 1

        th = thead.find(".//th")
        assert th is not None
        assert th.text == "<ABCD>"
        td = tbody.find(".//td")
        assert td is not None
        assert td.text == "<EFGH>"

    def test_complex_span_table(self) -> None:
        cell00 = TableCell(colspan=(0,), rowspan=(0, 1), bbox=(0, 0, 10, 20))
        cell10 = TableCell(colspan=(1, 2, 3), rowspan=(0,), bbox=(10, 0, 40, 10))
        cell40 = TableCell(colspan=(4, 5), rowspan=(0, 1, 2), bbox=(40, 0, 60, 30))
        cell11 = TableCell(colspan=(1, 2), rowspan=(1,), bbox=(10, 10, 30, 20))
        cell31 = TableCell(colspan=(3,), rowspan=(1,), bbox=(30, 10, 40, 20))
        cell22 = TableCell(colspan=(2, 3), rowspan=(2,), bbox=(20, 20, 40, 30))

        cell00.append_token({"text": "AA", "bbox": (0, 0, 10, 10), "span_num": 0})
        cell10.append_token({"text": "BB", "bbox": (10, 0, 40, 10), "span_num": 0})
        cell40.append_token({"text": "CC", "bbox": (40, 0, 60, 10), "span_num": 0})
        cell11.append_token({"text": "DD", "bbox": (10, 10, 30, 20), "span_num": 0})
        cell31.append_token({"text": "EE", "bbox": (30, 10, 40, 20), "span_num": 0})
        cell22.append_token({"text": "F", "bbox": (20, 20, 30, 30), "span_num": 0})
        cell22.append_token({"text": "F", "bbox": (30, 20, 40, 30), "span_num": 1})

        cell00.finalize()
        cell10.finalize()
        cell40.finalize()
        cell11.finalize()
        cell31.finalize()
        cell22.finalize()

        cells: dict[int, dict[int, TableCell]] = {
            0: {0: cell00, 1: cell10, 4: cell40},
            1: {1: cell11, 3: cell31},
            2: {2: cell22},
        }

        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 60, 10), (0, 10, 60, 20), (0, 20, 60, 30)],
            cols_bbox=[(0, 0, 10, 30), (10, 0, 20, 30), (20, 0, 30, 30),
                       (30, 0, 40, 30), (40, 0, 50, 30), (50, 0, 60, 30)],
            cells=cells,
        )

        table = ET.fromstring(result)
        thead = table.find("thead")
        tbody = table.find("tbody")
        assert thead is None
        assert tbody is not None

        rows = tbody.findall("tr")
        assert len(rows) == 3

        cols = rows[0].findall("td")
        assert len(cols) == 3

        assert cols[0].get("colspan") is None
        assert cols[0].get("rowspan") == "2"
        assert cols[0].get("bbox") == "[0, 0, 10, 20]"
        assert cols[0].text == "AA"

        assert cols[1].get("colspan") == "3"
        assert cols[1].get("rowspan") is None
        assert cols[1].get("bbox") == "[10, 0, 40, 10]"
        assert cols[1].text == "BB"

        assert cols[2].get("colspan") == "2"
        assert cols[2].get("rowspan") == "3"
        assert cols[2].get("bbox") == "[40, 0, 60, 30]"
        assert cols[2].text == "CC"

        cols = rows[1].findall("td")
        assert len(cols) == 2

        assert cols[0].get("colspan") == "2"
        assert cols[0].get("rowspan") is None
        assert cols[0].get("bbox") == "[10, 10, 30, 20]"
        assert cols[0].text == "DD"

        assert cols[1].get("colspan") is None
        assert cols[1].get("rowspan") is None
        assert cols[1].get("bbox") == "[30, 10, 40, 20]"
        assert cols[1].text == "EE"

        cols = rows[2].findall("td")
        assert len(cols) == 3

        assert cols[0].get("colspan") is None
        assert cols[0].get("rowspan") is None
        assert cols[0].get("bbox") is None
        assert cols[0].text is None

        assert cols[1].get("colspan") is None
        assert cols[1].get("rowspan") is None
        assert cols[1].get("bbox") is None
        assert cols[1].text is None

        assert cols[2].get("colspan") == "2"
        assert cols[2].get("rowspan") is None
        assert cols[2].get("bbox") == "[20, 20, 40, 30]"
        assert cols[2].text == "F F"

    def test_multiple_header_rows(self) -> None:
        h0 = TableCell(colspan=(0,), rowspan=(0,), bbox=(0, 0, 50, 10))
        h0.append_token({"text": "H1", "bbox": (0, 0, 50, 10), "span_num": 0})
        h0.finalize()

        h1 = TableCell(colspan=(0,), rowspan=(1,), bbox=(0, 10, 50, 20))
        h1.append_token({"text": "H2", "bbox": (0, 10, 50, 20), "span_num": 0})
        h1.finalize()

        body = TableCell(colspan=(0,), rowspan=(2,), bbox=(0, 20, 50, 30))
        body.append_token({"text": "D", "bbox": (0, 20, 50, 30), "span_num": 0})
        body.finalize()

        cells: dict[int, dict[int, TableCell]] = {0: {0: h0}, 1: {0: h1}, 2: {0: body}}
        result = convert2html(
            header_rows=[0, 1],
            rows_bbox=[(0, 0, 50, 10), (0, 10, 50, 20), (0, 20, 50, 30)],
            cols_bbox=[(0, 0, 50, 30)],
            cells=cells,
        )
        table = ET.fromstring(result)

        thead = table.find("thead")
        tbody = table.find("tbody")
        assert thead is not None
        assert tbody is not None

        assert len(thead.findall("tr")) == 2
        assert len(tbody.findall("tr")) == 1

        ths = thead.findall(".//th")
        assert len(ths) == 2
        assert ths[0].text == "H1"
        assert ths[1].text == "H2"
        td = tbody.find(".//td")
        assert td is not None
        assert td.text == "D"

    def test_multi_column_no_spans(self) -> None:
        cells: dict[int, dict[int, TableCell]] = {}
        for col in range(3):
            cell = TableCell(
                colspan=(col,), rowspan=(0,), bbox=(col * 10, 0, (col + 1) * 10, 10)
            )
            cell.append_token(
                {"text": f"c{col}", "bbox": (col * 10, 0, (col + 1) * 10, 10), "span_num": 0}
            )
            cell.finalize()
            cells.setdefault(0, {})[col] = cell

        result = convert2html(
            header_rows=[],
            rows_bbox=[(0, 0, 30, 10)],
            cols_bbox=[(0, 0, 10, 10), (10, 0, 20, 10), (20, 0, 30, 10)],
            cells=cells,
        )
        table = ET.fromstring(result)
        tds = table.findall(".//td")
        assert len(tds) == 3
        assert [td.text for td in tds] == ["c0", "c1", "c2"]
        for td in tds:
            assert td.get("colspan") is None
            assert td.get("rowspan") is None


class TestTableCellRepr:
    def test_repr(self) -> None:
        cell = TableCell(colspan=(0, 1), rowspan=(0,), bbox=(5, 10, 15, 20))
        cell.append_token({"text": "hi", "bbox": (5, 10, 15, 20), "span_num": 0})
        cell.finalize()
        r = repr(cell)
        assert "TableCell" in r
        assert "self._colspan=2" in r
        assert "self._rowspan=1" in r
        assert "self._text='hi'" in r
        assert "self._bbox=(5, 10, 15, 20)" in r


class TestFindOrRaise:
    def test_returns_element_when_found(self) -> None:
        root = ET.fromstring("<root><child>text</child></root>")
        elem = find_or_raise(root, "child")
        assert elem.text == "text"

    def test_raises_when_not_found(self) -> None:
        root = ET.fromstring("<root><child>text</child></root>")
        with pytest.raises(ValueError, match="Missing XML element: missing"):
            find_or_raise(root, "missing")


def _make_annotation_xml(
    tmp_path: Path,
    rows: list[tuple[int, int]],
    cols: list[tuple[int, int]],
    header: tuple[int, int, int, int] | None = None,
) -> Path:
    root = ET.Element("annotation")
    for y0, y1 in rows:
        obj = ET.SubElement(root, "object")
        name = ET.SubElement(obj, "name")
        name.text = "table row"
        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = "0"
        ET.SubElement(bndbox, "ymin").text = str(y0)
        ET.SubElement(bndbox, "xmax").text = "100"
        ET.SubElement(bndbox, "ymax").text = str(y1)
    for x0, x1 in cols:
        obj = ET.SubElement(root, "object")
        name = ET.SubElement(obj, "name")
        name.text = "table column"
        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = str(x0)
        ET.SubElement(bndbox, "ymin").text = "0"
        ET.SubElement(bndbox, "xmax").text = str(x1)
        ET.SubElement(bndbox, "ymax").text = "100"
    if header:
        obj = ET.SubElement(root, "object")
        name = ET.SubElement(obj, "name")
        name.text = "table column header"
        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = str(header[0])
        ET.SubElement(bndbox, "ymin").text = str(header[1])
        ET.SubElement(bndbox, "xmax").text = str(header[2])
        ET.SubElement(bndbox, "ymax").text = str(header[3])
    xml_path = tmp_path / "annotation.xml"
    tree = ET.ElementTree(root)
    tree.write(xml_path)
    return xml_path


def _make_words_json(
    tmp_path: Path, tokens: list[dict[str, Any]]
) -> Path:
    json_path = tmp_path / "words.json"
    json_path.write_text(json.dumps(tokens))
    return json_path


class TestExtractStructureAnnotations:
    def test_parses_rows_and_cols(self, tmp_path: Path) -> None:
        xml_path = _make_annotation_xml(
            tmp_path,
            rows=[(0, 10), (10, 20)],
            cols=[(0, 50), (50, 100)],
        )
        header_bbox, rows_bbox, cols_bbox = extract_structure_annotations(xml_path)
        assert header_bbox == (-1, -1, -1, -1)
        assert len(rows_bbox) == 2
        assert len(cols_bbox) == 2
        assert rows_bbox[0][1] < rows_bbox[1][1]
        assert cols_bbox[0][0] < cols_bbox[1][0]

    def test_parses_header(self, tmp_path: Path) -> None:
        xml_path = _make_annotation_xml(
            tmp_path,
            rows=[(0, 10), (10, 20)],
            cols=[(0, 100)],
            header=(0, 0, 100, 10),
        )
        header_bbox, _, _ = extract_structure_annotations(xml_path)
        assert header_bbox == (0.0, 0.0, 100.0, 10.0)

    def test_sorts_rows_by_y(self, tmp_path: Path) -> None:
        xml_path = _make_annotation_xml(
            tmp_path,
            rows=[(20, 30), (0, 10), (10, 20)],
            cols=[(0, 100)],
        )
        _, rows_bbox, _ = extract_structure_annotations(xml_path)
        assert rows_bbox[0][1] == 0.0
        assert rows_bbox[1][1] == 10.0
        assert rows_bbox[2][1] == 20.0

    def test_sorts_cols_by_x(self, tmp_path: Path) -> None:
        xml_path = _make_annotation_xml(
            tmp_path,
            rows=[(0, 100)],
            cols=[(50, 100), (0, 50)],
        )
        _, _, cols_bbox = extract_structure_annotations(xml_path)
        assert cols_bbox[0][0] == 0.0
        assert cols_bbox[1][0] == 50.0


class TestExtractTokenAnnotations:
    def test_single_token_single_cell(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        cols_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        tokens: list[dict[str, Any]] = [{"text": "hello", "bbox": [5, 5, 50, 15], "span_num": 0}]
        json_path = _make_words_json(tmp_path, tokens)

        cells = extract_token_annotations(json_path, rows_bbox, cols_bbox)
        assert 0 in cells
        assert 0 in cells[0]
        cell = cells[0][0]
        assert cell.text == "hello"

    def test_token_outside_table_is_skipped(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        cols_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        tokens: list[dict[str, Any]] = [{"text": "outside", "bbox": [200, 200, 300, 300], "span_num": 0}]
        json_path = _make_words_json(tmp_path, tokens)

        cells = extract_token_annotations(json_path, rows_bbox, cols_bbox)
        assert len(cells) == 0

    def test_multiple_tokens_same_cell(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        cols_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        tokens: list[dict[str, Any]] = [
            {"text": "hello", "bbox": [5, 5, 40, 15], "span_num": 0},
            {"text": "world", "bbox": [45, 5, 90, 15], "span_num": 1},
        ]
        json_path = _make_words_json(tmp_path, tokens)

        cells = extract_token_annotations(json_path, rows_bbox, cols_bbox)
        assert cells[0][0].text == "hello world"

    def test_tokens_in_different_cells(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0)]
        cols_bbox: list[Bbox] = [(0.0, 0.0, 50.0, 20.0), (50.0, 0.0, 100.0, 20.0)]
        tokens: list[dict[str, Any]] = [
            {"text": "left", "bbox": [5, 5, 40, 15], "span_num": 0},
            {"text": "right", "bbox": [55, 5, 90, 15], "span_num": 1},
        ]
        json_path = _make_words_json(tmp_path, tokens)

        cells = extract_token_annotations(json_path, rows_bbox, cols_bbox)
        assert cells[0][0].text == "left"
        assert cells[0][1].text == "right"

    def test_spanning_token_creates_multispan_cell(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0), (0.0, 20.0, 100.0, 40.0)]
        cols_bbox: list[Bbox] = [(0.0, 0.0, 50.0, 40.0), (50.0, 0.0, 100.0, 40.0)]
        tokens: list[dict[str, Any]] = [
            {"text": "wide", "bbox": [5, 5, 95, 15], "span_num": 0},
        ]
        json_path = _make_words_json(tmp_path, tokens)

        cells = extract_token_annotations(json_path, rows_bbox, cols_bbox)
        cell = cells[0][0]
        assert cell.colspan == 2
        assert cell.rowspan == 1
        assert cell.text == "wide"

    def test_expand_span_triggered(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 20.0), (0.0, 20.0, 100.0, 40.0)]
        cols_bbox: list[Bbox] = [(0.0, 0.0, 100.0, 40.0)]
        tokens: list[dict[str, Any]] = [
            {"text": "top", "bbox": [5, 5, 90, 15], "span_num": 0},
            {"text": "both", "bbox": [5, 5, 90, 35], "span_num": 1},
        ]
        json_path = _make_words_json(tmp_path, tokens)

        cells = extract_token_annotations(json_path, rows_bbox, cols_bbox)
        cell = cells[0][0]
        assert cell.rowspan == 2
        assert cell.text == "top both"

    def test_non_overlapping_row_col_raises(self, tmp_path: Path) -> None:
        rows_bbox: list[Bbox] = [(0.0, 0.0, 50.0, 20.0)]
        cols_bbox: list[Bbox] = [(60.0, 0.0, 100.0, 20.0)]
        tokens: list[dict[str, Any]] = [{"text": "x", "bbox": [0, 0, 100, 20], "span_num": 0}]
        json_path = _make_words_json(tmp_path, tokens)

        with pytest.raises(ValueError, match="no existing intersection"):
            extract_token_annotations(json_path, rows_bbox, cols_bbox)


class TestExtractTableData:
    def test_full_pipeline(self, tmp_path: Path) -> None:
        xml_path = _make_annotation_xml(
            tmp_path,
            rows=[(0, 20), (20, 40)],
            cols=[(0, 50), (50, 100)],
            header=(0, 0, 100, 20),
        )
        tokens: list[dict[str, Any]] = [
            {"text": "H1", "bbox": [5, 5, 40, 15], "span_num": 0},
            {"text": "H2", "bbox": [55, 5, 90, 15], "span_num": 1},
            {"text": "D1", "bbox": [5, 25, 40, 35], "span_num": 2},
            {"text": "D2", "bbox": [55, 25, 90, 35], "span_num": 3},
        ]
        json_path = _make_words_json(tmp_path, tokens)

        header_rows, rows_bbox, cols_bbox, cells = extract_table_data(
            xml_path, json_path
        )

        assert header_rows == [0]
        assert len(rows_bbox) == 2
        assert len(cols_bbox) == 2
        assert cells[0][0].text == "H1"
        assert cells[0][1].text == "H2"
        assert cells[1][0].text == "D1"
        assert cells[1][1].text == "D2"

    def test_no_header(self, tmp_path: Path) -> None:
        xml_path = _make_annotation_xml(
            tmp_path,
            rows=[(0, 20)],
            cols=[(0, 100)],
        )
        tokens: list[dict[str, Any]] = [{"text": "val", "bbox": [5, 5, 90, 15], "span_num": 0}]
        json_path = _make_words_json(tmp_path, tokens)

        header_rows, _, _, cells = extract_table_data(xml_path, json_path)
        assert header_rows == []
        assert cells[0][0].text == "val"

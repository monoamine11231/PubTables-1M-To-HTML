import xml.etree.ElementTree as ET
from rtree import index
from pathlib import Path
from typing import Any, Callable, DefaultDict, TypeAlias, TypedDict
import json

Bbox: TypeAlias = tuple[float, float, float, float]


class Token(TypedDict):
    text: str
    bbox: tuple[int, int, int, int]
    span_num: int


class TableCell:
    def __init__(
        self,
        colspan: tuple[int, ...],
        rowspan: tuple[int, ...],
        bbox: tuple[float, float, float, float],
    ):
        def sequential_span(arr: list[int] | tuple[int, ...]) -> bool:
            return all([arr[i + 1] == arr[i] + 1 for i in range(len(arr) - 1)])

        if not sequential_span(rowspan):
            raise ValueError(f"`{rowspan=}` doesn't span the table grid sequentially.")

        if not sequential_span(colspan):
            raise ValueError(f"`{colspan=}` doesn't span the table grid sequentially.")

        self._colspan = len(colspan)
        self._rowspan = len(rowspan)
        self._colspan_indices = colspan
        self._rowspan_indices = rowspan
        self._bbox = bbox
        self._tokens: list[Token] = []

    def expand_span(self, colspan: tuple[int, ...], rowspan: tuple[int, ...]):
        merged_cols = tuple(sorted(set(self._colspan_indices) | set(colspan)))
        merged_rows = tuple(sorted(set(self._rowspan_indices) | set(rowspan)))
        self._colspan_indices = merged_cols
        self._rowspan_indices = merged_rows
        self._colspan = len(merged_cols)
        self._rowspan = len(merged_rows)

    def append_token(self, token: Token):
        self._tokens.append(token)

    def extend_tokens(self, tokens: list[Token]):
        self._tokens.extend(tokens)

    def finalize(self):
        self._tokens.sort(key=lambda x: x["span_num"])
        self._text = " ".join([x["text"] for x in self._tokens])

    @property
    def colspan(self) -> int:
        return self._colspan

    @property
    def rowspan(self) -> int:
        return self._rowspan

    @property
    def colspan_indices(self) -> tuple[int, ...]:
        return self._colspan_indices

    @property
    def rowspan_indices(self) -> tuple[int, ...]:
        return self._rowspan_indices

    @property
    def text(self) -> str:
        return self._text

    @property
    def bbox(self) -> Bbox:
        return self._bbox

    @property
    def tokens(self) -> list[Token]:
        return self._tokens

    def __repr__(self) -> str:
        return f"TableCell({self._colspan=}, {self._rowspan=}, {self._text=}, {self._bbox=})"


def find_or_raise(parent: ET.Element, path: str) -> ET.Element:
    elem = parent.find(path)
    if elem is None:
        raise ValueError(f"Missing XML element: {path}")
    return elem


def extract_structure_annotations(annotation_xml: str | Path):
    annotation_tree = ET.parse(annotation_xml).getroot()

    header_bbox: Bbox = (-1, -1, -1, -1)
    rows_bbox: list[Bbox] = []
    cols_bbox: list[Bbox] = []
    for object in annotation_tree.findall("object"):
        name = find_or_raise(object, "name").text or ""
        bbox_element = find_or_raise(object, "bndbox")

        bbox: Bbox = (
            float(find_or_raise(bbox_element, "xmin").text or ""),
            float(find_or_raise(bbox_element, "ymin").text or ""),
            float(find_or_raise(bbox_element, "xmax").text or ""),
            float(find_or_raise(bbox_element, "ymax").text or ""),
        )

        if name == "table row":
            rows_bbox.append(bbox)
        elif name == "table column header":
            header_bbox = bbox
        elif name == "table column":
            cols_bbox.append(bbox)

    rows_bbox.sort(key=lambda x: x[1])
    cols_bbox.sort(key=lambda x: x[0])

    return header_bbox, rows_bbox, cols_bbox


def extract_token_annotations(
    words_json: str | Path,
    rows_bbox: list[Bbox],
    cols_bbox: list[Bbox],
) -> dict[int, dict[int, TableCell]]:
    def union_bboxes(arr: list[Bbox]) -> Bbox:
        return (
            min(b[0] for b in arr),
            min(b[1] for b in arr),
            max(b[2] for b in arr),
            max(b[3] for b in arr),
        )

    def intersection_bboxes(arr: list[Bbox]) -> Bbox:
        x0 = max(b[0] for b in arr)
        y0 = max(b[1] for b in arr)
        x1 = min(b[2] for b in arr)
        y1 = min(b[3] for b in arr)
        if x0 >= x1 or y0 >= y1:
            raise ValueError(
                f"`intersection_bboxes` received list of bboxes having no existing intersection."
            )
        return (x0, y0, x1, y1)

    def write2cells(
        cells: DefaultDict[int, dict[int, TableCell]],
        rowspan: tuple[int, ...],
        colspan: tuple[int, ...],
        element: TableCell,
        overwrite: bool = False,
    ) -> TableCell | None:
        for r in rowspan:
            for c in colspan:
                if cells[r].get(c, None):
                    if cells[r][c] != element and not overwrite:
                        # Overlap
                        return cells[r][c]
                cells[r][c] = element

        return None

    rtree_rows_index = index.Index()
    for i, bbox in enumerate(rows_bbox):
        rtree_rows_index.insert(i, tuple(bbox))

    rtree_columns_index = index.Index()
    for i, bbox in enumerate(cols_bbox):
        rtree_columns_index.insert(i, tuple(bbox))

    with open(words_json, "r") as f:
        raw_tokens: list[dict[str, Any]] = json.load(f)

    tokens_in_table: list[Token] = [
        Token(
            text=t["text"],
            bbox=tuple(t["bbox"][:4]),
            span_num=t["span_num"],
        )
        for t in raw_tokens
    ]

    cells: DefaultDict[int, dict[int, TableCell]] = DefaultDict(dict)
    for token in tokens_in_table:
        rowspan: tuple[int, ...] = tuple(
            sorted(list(rtree_rows_index.intersection(tuple(token["bbox"]))))
        )
        colspan: tuple[int, ...] = tuple(
            sorted(list(rtree_columns_index.intersection(tuple(token["bbox"]))))
        )

        # Outside of table
        if (len(rowspan) == 0) or (len(colspan) == 0):
            continue

        cell: TableCell | None = None
        for r in rowspan:
            for c in colspan:
                if c in cells[r]:
                    cell = cells[r][c]
                    break
            if cell:
                break

        if not cell:
            cell_cols_bbox = union_bboxes([cols_bbox[x] for x in colspan])
            cell_rows_bbox = union_bboxes([rows_bbox[x] for x in rowspan])
            cell_bbox = intersection_bboxes([cell_cols_bbox, cell_rows_bbox])

            cell = TableCell(colspan, rowspan, cell_bbox)

        if (cell.rowspan_indices != rowspan) or (cell.colspan_indices != colspan):
            cell.expand_span(colspan, rowspan)

        while overlapped := write2cells(
            cells, cell.rowspan_indices, cell.colspan_indices, cell
        ):
            # Edge case of an overlap
            cell.expand_span(overlapped.colspan_indices, overlapped.rowspan_indices)
            cell.extend_tokens(overlapped.tokens)
            write2cells(
                cells,
                overlapped.rowspan_indices,
                overlapped.colspan_indices,
                cell,
                overwrite=True,
            )

        cell.append_token(token)

    for _, row in cells.items():
        for _, col in row.items():
            col.finalize()

    return cells


def extract_table_data(annotation_xml: str | Path, words_json: str | Path) -> tuple[
    list[int],
    list[Bbox],
    list[Bbox],
    dict[int, dict[int, TableCell]],
]:
    def inside_bbox(inner: Bbox, outer: Bbox) -> bool:
        return inner[1] >= outer[1] and inner[3] <= outer[3]

    header_bbox, rows_bbox, cols_bbox = extract_structure_annotations(annotation_xml)

    cells = extract_token_annotations(words_json, rows_bbox, cols_bbox)

    header_rows: list[int] = [
        i for i, row in enumerate(rows_bbox) if inside_bbox(row, header_bbox)
    ]

    return header_rows, rows_bbox, cols_bbox, cells


def convert2html(
    header_rows: list[int],
    rows_bbox: list[Bbox],
    cols_bbox: list[Bbox],
    cells: dict[int, dict[int, TableCell]],
) -> str:
    ROWS: int = len(rows_bbox)
    COLUMNS: int = len(cols_bbox)

    if not cells:
        return ""

    jump_grid: list[list[int]] = [[0 for _ in range(COLUMNS)] for _ in range(ROWS)]
    intlist: Callable[[Bbox], list[int]] = lambda arr: [int(x) for x in arr]

    def _build_row(parent: ET.Element, row_ind: int, tag: str = "td"):
        tr = ET.SubElement(parent, "tr")
        tr.set("bbox", str(intlist(rows_bbox[row_ind])))

        col_ind: int = 0
        while col_ind < COLUMNS:
            while col_ind < COLUMNS and (jump := jump_grid[row_ind][col_ind]) > 0:
                col_ind += jump
            if col_ind >= COLUMNS:
                break

            cell: TableCell | None = cells.get(row_ind, {}).get(col_ind, None)
            if not cell:
                ET.SubElement(tr, tag)
                jump_grid[row_ind][col_ind] = 1
                continue

            td = ET.SubElement(tr, tag)
            if cell.colspan > 1:
                td.set("colspan", str(cell.colspan))
            if cell.rowspan > 1:
                td.set("rowspan", str(cell.rowspan))
            td.set("bbox", str(intlist(cell.bbox)))
            td.text = cell.text

            for k in range(cell.rowspan):
                jump_grid[row_ind + k][col_ind] = cell.colspan

    table = ET.Element("table")
    row_ind = 0

    if header_rows:
        thead = ET.SubElement(table, "thead")
        while row_ind <= header_rows[-1]:
            _build_row(thead, row_ind, tag="th")
            row_ind += 1

    tbody = ET.SubElement(table, "tbody")
    while row_ind < ROWS:
        _build_row(tbody, row_ind)
        row_ind += 1

    ET.indent(table, space="\t")
    return ET.tostring(table, encoding="unicode", short_empty_elements=False)

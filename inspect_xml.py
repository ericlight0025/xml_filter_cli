"""查看 XML 結構與內容的 Rich CLI。"""

from __future__ import annotations

import argparse
import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

from xml_service import (
    LARGE_FILE_THRESHOLD_BYTES,
    XmlFilterError,
    analyze_xml_structure,
)


console = Console()


class XmlInspectError(Exception):
    """XML 查看作業的可預期錯誤。"""


@dataclass(frozen=True)
class XmlInspection:
    """XML 基本結構與顯示內容。"""

    input_path: Path
    file_size: int
    root_tag: str
    child_tag_counts: dict[str, int]
    key_tags_by_item: dict[str, tuple[str, ...]]
    full_xml: str
    truncated: bool = False


def inspect_xml(
    input_path: Path,
    *,
    large_threshold_bytes: int = LARGE_FILE_THRESHOLD_BYTES,
    large_item_limit: int = 50,
) -> XmlInspection:
    """小檔完整顯示；大型 XML 以串流方式顯示前幾個直接子節點。"""
    try:
        structure = analyze_xml_structure(input_path)
    except XmlFilterError as exc:
        raise XmlInspectError(str(exc)) from exc

    if structure.file_size >= large_threshold_bytes:
        display_xml = _large_xml_preview(structure.input_path, large_item_limit)
        truncated = sum(structure.child_tag_counts.values()) > large_item_limit
    else:
        try:
            tree = ET.parse(structure.input_path)
        except ET.ParseError as exc:
            raise XmlInspectError(f"XML 格式錯誤：{exc}") from exc
        except OSError as exc:
            raise XmlInspectError(f"無法讀取 XML：{exc}") from exc
        ET.indent(tree, space="    ")
        display_xml = ET.tostring(
            tree.getroot(),
            encoding="unicode",
            short_empty_elements=True,
        )
        truncated = False

    return XmlInspection(
        input_path=structure.input_path,
        file_size=structure.file_size,
        root_tag=structure.root_tag,
        child_tag_counts=structure.child_tag_counts,
        key_tags_by_item=structure.key_tags_by_item,
        full_xml=display_xml,
        truncated=truncated,
    )


def _large_xml_preview(input_path: Path, item_limit: int) -> str:
    """大型 XML 不整包載入，只建立前 N 個直接子節點的顯示內容。"""
    preview_root: ET.Element | None = None
    depth = 0
    appended = 0
    try:
        for event, element in ET.iterparse(input_path, events=("start", "end")):
            if event == "start":
                depth += 1
                if depth == 1:
                    preview_root = ET.Element(element.tag, dict(element.attrib))
                continue
            if depth == 2:
                if preview_root is not None and appended < item_limit:
                    preview_root.append(copy.deepcopy(element))
                    appended += 1
                element.clear()
            depth -= 1
    except ET.ParseError as exc:
        raise XmlInspectError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        raise XmlInspectError(f"無法讀取 XML：{exc}") from exc

    if preview_root is None:
        raise XmlInspectError("XML 沒有根標籤。")
    ET.indent(preview_root, space="    ")
    return ET.tostring(preview_root, encoding="unicode", short_empty_elements=True)


def show_inspection(inspection: XmlInspection) -> None:
    """以 Rich 顯示 XML 結構與內容。"""
    console.print(
        Panel.fit(
            "[bold cyan]XML Content Inspector[/bold cyan]\n"
            f"檔案：{inspection.input_path}\n"
            f"大小：{inspection.file_size / 1024 / 1024:.2f} MB",
            border_style="cyan",
        )
    )
    console.print(f"根標籤：[bold green]<{inspection.root_tag}>[/bold green]")

    table = Table(title="根標籤下的直接子標籤", border_style="blue")
    table.add_column("list tag", style="bold")
    table.add_column("數量", justify="right")
    table.add_column("候選 key tags")
    for tag, count in inspection.child_tag_counts.items():
        candidates = ", ".join(inspection.key_tags_by_item.get(tag, ())) or "—"
        table.add_row(f"<{tag}>", str(count), candidates)
    console.print(table)

    if inspection.truncated:
        console.print("[yellow]大型 XML：內容區只顯示前 50 個直接子節點。[/yellow]")
    else:
        console.print("[bold]完整 XML 內容：[/bold]")
    console.print(Syntax(inspection.full_xml, "xml", theme="monokai", word_wrap=True))


def run_inspect_interactive() -> int:
    """在總選單中互動式查看 XML。"""
    input_text = Prompt.ask("請輸入要查看的 XML 檔案路徑").strip().strip('"')
    try:
        inspection = inspect_xml(Path(input_text))
    except XmlInspectError as exc:
        console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1
    show_inspection(inspection)
    return 0


def main(argv: list[str] | None = None) -> int:
    """XML 查看 CLI 入口。"""
    parser = argparse.ArgumentParser(description="查看 XML 的標籤結構與內容。")
    parser.add_argument("xml_filepath", type=Path, nargs="?", help="XML 檔案路徑")
    parser.add_argument(
        "--large-threshold-mb",
        type=float,
        default=LARGE_FILE_THRESHOLD_BYTES / 1024 / 1024,
        help="超過此大小使用大型檔案預覽，預設 20 MB",
    )
    args = parser.parse_args(argv)
    if args.xml_filepath is None:
        return run_inspect_interactive()
    try:
        inspection = inspect_xml(
            args.xml_filepath,
            large_threshold_bytes=max(0, int(args.large_threshold_mb * 1024 * 1024)),
        )
    except XmlInspectError as exc:
        console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1
    show_inspection(inspection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

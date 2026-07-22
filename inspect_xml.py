"""查看 XML 的根標籤、直接子標籤與內容範例。"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table


console = Console()


class XmlInspectError(Exception):
    """XML 查看作業的可預期錯誤。"""


@dataclass(frozen=True)
class XmlInspection:
    """XML 基本結構與完整內容的查看結果。"""

    input_path: Path
    root_tag: str
    child_tag_counts: dict[str, int]
    full_xml: str


def inspect_xml(input_path: Path) -> XmlInspection:
    """讀取 XML，統計根節點下一層標籤，並取得完整 XML 內容。"""
    input_path = input_path.expanduser().resolve()

    if not input_path.is_file():
        raise XmlInspectError(f"找不到輸入 XML：{input_path}")

    try:
        tree = ET.parse(input_path)
    except ET.ParseError as exc:
        raise XmlInspectError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        raise XmlInspectError(f"無法讀取 XML：{exc}") from exc

    root = tree.getroot()
    child_nodes = list(root)
    tag_counts = Counter(child.tag for child in child_nodes)
    ET.indent(tree, space="    ")
    full_xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)

    return XmlInspection(
        input_path=input_path,
        root_tag=root.tag,
        child_tag_counts=dict(tag_counts),
        full_xml=full_xml,
    )


def show_inspection(inspection: XmlInspection) -> None:
    """以 Rich 顯示 XML 結構與內容範例。"""
    console.print(
        Panel.fit(
            "[bold cyan]XML Content Inspector[/bold cyan]\n"
            f"檔案：{inspection.input_path}",
            border_style="cyan",
        )
    )

    console.print(f"根標籤：[bold green]<{inspection.root_tag}>[/bold green]")

    table = Table(title="根標籤下的直接子標籤", border_style="blue")
    table.add_column("標籤", style="bold")
    table.add_column("數量", justify="right")
    for tag, count in inspection.child_tag_counts.items():
        table.add_row(f"<{tag}>", str(count))
    console.print(table)

    console.print("[bold]完整 XML 內容：[/bold]")
    console.print(
        Syntax(
            inspection.full_xml,
            "xml",
            theme="monokai",
            word_wrap=True,
        )
    )


def run_inspect_interactive() -> int:
    """在選單中互動式查看 XML。"""
    input_text = Prompt.ask("請輸入要查看的 XML 檔案路徑").strip().strip('"')

    try:
        inspection = inspect_xml(Path(input_text))
    except XmlInspectError as exc:
        console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    show_inspection(inspection)
    return 0


def main(argv: list[str] | None = None) -> int:
    """XML 查看 CLI 入口；省略路徑時使用互動輸入。"""
    parser = argparse.ArgumentParser(description="查看 XML 的標籤結構與內容範例。")
    parser.add_argument("xml_filepath", type=Path, nargs="?", help="XML 檔案路徑")
    args = parser.parse_args(argv)

    if args.xml_filepath is None:
        return run_inspect_interactive()

    try:
        inspection = inspect_xml(args.xml_filepath)
    except XmlInspectError as exc:
        console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    show_inspection(inspection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

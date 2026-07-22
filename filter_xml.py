"""依照 <key> 篩選 <datalist> 內的 <data> 節點。"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table


ROOT_TAG = "datalist"
ITEM_TAG = "data"
KEY_TAG = "key"
console = Console()
error_console = Console(stderr=True)


class XmlFilterError(Exception):
    """XML 篩選作業的可預期錯誤。"""


@dataclass(frozen=True)
class FilterResult:
    """篩選完成後的統計資料。"""

    output_path: Path
    kept_count: int
    removed_count: int


def default_output_path(input_path: Path) -> Path:
    """產生不覆蓋原始檔案的預設輸出路徑。"""
    return input_path.with_name(f"{input_path.stem}.filtered{input_path.suffix}")


def filter_xml_by_key(
    input_path: Path,
    target_key: str,
    output_path: Path | None = None,
    *,
    item_tag: str = ITEM_TAG,
    force: bool = False,
) -> FilterResult:
    """只保留指定 list tag 內 <key> 符合 target_key 的節點。"""
    input_path = input_path.expanduser().resolve()
    output_path = (output_path or default_output_path(input_path)).expanduser().resolve()

    if not input_path.is_file():
        raise XmlFilterError(f"找不到輸入 XML：{input_path}")

    if input_path == output_path:
        raise XmlFilterError("輸出路徑不可與輸入路徑相同，避免破壞原始 XML。")

    if output_path.exists() and not force:
        raise XmlFilterError(
            f"輸出檔已存在：{output_path}。如要覆蓋，請加上 --force。"
        )

    if not target_key.strip():
        raise XmlFilterError("key 不可為空白。")

    if not item_tag.strip():
        raise XmlFilterError("外圍 list tag 不可為空白。")

    try:
        tree = ET.parse(input_path)
    except ET.ParseError as exc:
        raise XmlFilterError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        raise XmlFilterError(f"無法讀取 XML：{exc}") from exc

    root = tree.getroot()
    if root.tag != ROOT_TAG:
        raise XmlFilterError(
            f"最外層標籤必須是 <{ROOT_TAG}>，目前是 <{root.tag}>。"
        )

    data_nodes = list(root.findall(item_tag))
    kept_count = 0
    removed_count = 0

    for data_node in data_nodes:
        key_node = data_node.find(KEY_TAG)
        key_value = key_node.text.strip() if key_node is not None and key_node.text else ""

        if key_value == target_key:
            kept_count += 1
        else:
            root.remove(data_node)
            removed_count += 1

    if kept_count == 0:
        raise XmlFilterError(
            f"找不到 key={target_key!r} 的 <{item_tag}>，未建立輸出檔。"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="    ")

    try:
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        raise XmlFilterError(f"無法寫入輸出 XML：{exc}") from exc

    return FilterResult(
        output_path=output_path,
        kept_count=kept_count,
        removed_count=removed_count,
    )


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器。"""
    parser = argparse.ArgumentParser(
        description="Rich 互動選單／參數模式：篩選 XML 中指定 key 的資料。"
    )
    parser.add_argument(
        "xml_filepath",
        type=Path,
        nargs="?",
        help="輸入 XML 檔案路徑；省略時進入互動選單",
    )
    parser.add_argument(
        "key",
        nargs="?",
        help="要保留的 <key> 值，例如 A001",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="輸出 XML 路徑；預設為原檔名加上 .filtered",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允許覆蓋已存在的輸出檔",
    )
    parser.add_argument(
        "--item-tag",
        default=ITEM_TAG,
        help="包住 <key> 的外圍 list tag，預設為 data",
    )
    return parser


def show_title() -> None:
    """顯示 Rich CLI 標題。"""
    console.print(
        Panel.fit(
            "[bold cyan]XML Key Filter[/bold cyan]\n"
            "只保留 [bold]<datalist>[/bold] 中指定 key 的資料",
            border_style="cyan",
        )
    )


def show_job_summary(
    input_path: Path,
    item_tag: str,
    target_key: str,
    output_path: Path,
) -> None:
    """顯示即將執行的篩選設定。"""
    table = Table(title="執行設定", show_header=False, border_style="blue")
    table.add_column("欄位", style="bold")
    table.add_column("內容")
    table.add_row("輸入 XML", str(input_path))
    table.add_row("外圍 list tag", item_tag)
    table.add_row("保留 key", target_key)
    table.add_row("輸出 XML", str(output_path))
    console.print(table)


def run_filter_interactive() -> int:
    """執行 XML 篩選的互動式表單，完成後回傳給上層選單。"""
    show_title()

    while True:
        input_text = Prompt.ask("請輸入 XML 檔案路徑").strip().strip('"')
        input_path = Path(input_text).expanduser().resolve()

        if not input_path.is_file():
            console.print(f"[bold red]錯誤：找不到輸入 XML：{input_path}[/bold red]")
            return 1

        item_tag = Prompt.ask(
            "請輸入資料外圍 list tag",
            default=ITEM_TAG,
        ).strip()
        if not item_tag:
            console.print("[bold red]錯誤：外圍 list tag 不可為空白。[/bold red]")
            return 1

        target_key = Prompt.ask("請輸入要保留的 key").strip()
        if not target_key:
            console.print("[bold red]錯誤：key 不可為空白。[/bold red]")
            return 1

        suggested_output = default_output_path(input_path)
        output_text = Prompt.ask(
            "請輸入輸出 XML 路徑",
            default=str(suggested_output),
        ).strip().strip('"')
        output_path = Path(output_text).expanduser().resolve()

        show_job_summary(input_path, item_tag, target_key, output_path)
        if not Confirm.ask("確認執行？", default=True):
            console.print("[yellow]已取消本次操作。[/yellow]")
            return 0

        force = False
        if output_path.exists():
            force = Confirm.ask(
                "[yellow]輸出檔已存在，確定要覆蓋？[/yellow]",
                default=False,
            )
            if not force:
                console.print("[yellow]未覆蓋既有檔案。[/yellow]")
                return 0

        try:
            result = filter_xml_by_key(
                input_path=input_path,
                target_key=target_key,
                output_path=output_path,
                item_tag=item_tag,
                force=force,
            )
        except XmlFilterError as exc:
            console.print(f"[bold red]錯誤：{exc}[/bold red]")
            return 1
        else:
            console.print(
                Panel.fit(
                    f"[bold green]篩選完成[/bold green]\n"
                    f"保留：{result.kept_count} 筆\n"
                    f"刪除：{result.removed_count} 筆\n"
                    f"輸出：{result.output_path}",
                    border_style="green",
                )
            )
            return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 進入點。"""
    args = build_parser().parse_args(argv)

    if args.xml_filepath is None and args.key is None:
        return run_filter_interactive()

    if args.xml_filepath is None or args.key is None:
        console.print(
            "[bold red]錯誤：參數模式必須同時提供 XML 檔案路徑與 key。[/bold red]"
        )
        return 2

    try:
        result = filter_xml_by_key(
            input_path=args.xml_filepath,
            target_key=args.key,
            output_path=args.output,
            item_tag=args.item_tag,
            force=args.force,
        )
    except XmlFilterError as exc:
        error_console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    console.print(
        f"[bold green]完成[/bold green]：保留 {result.kept_count} 筆，"
        f"刪除 {result.removed_count} 筆。"
    )
    console.print(f"輸出檔：{result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

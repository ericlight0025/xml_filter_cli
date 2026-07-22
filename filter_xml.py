"""XML Key Filter 的 Rich CLI 與參數模式入口。"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from xml_service import (
    ITEM_TAG,
    KEY_TAG,
    LARGE_FILE_THRESHOLD_BYTES,
    ROOT_TAG,
    FilterPreview,
    FilterResult,
    XmlFilterError,
    analyze_xml_structure,
    default_output_path,
    filter_xml_by_key,
    filter_xml_by_keys,
    parse_target_keys,
    preview_filter,
)


console = Console()
error_console = Console(stderr=True)


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器。"""
    parser = argparse.ArgumentParser(
        description="Rich 互動選單／參數模式：依一個或多個 key 篩選 XML。"
    )
    parser.add_argument(
        "xml_filepath",
        type=Path,
        nargs="?",
        help="輸入 XML 路徑；省略時進入互動模式",
    )
    parser.add_argument(
        "keys",
        nargs="?",
        help="保留 key；多個值可用逗號或分號分隔",
    )
    parser.add_argument("-o", "--output", type=Path, help="輸出 XML 路徑")
    parser.add_argument("--root-tag", default=ROOT_TAG, help="根標籤")
    parser.add_argument("--item-tag", default=ITEM_TAG, help="外圍 list tag")
    parser.add_argument("--key-tag", default=KEY_TAG, help="key 欄位 tag")
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="只顯示篩選統計與 XML 預覽，不寫入檔案",
    )
    parser.add_argument("--force", action="store_true", help="允許覆蓋輸出檔")
    parser.add_argument(
        "--large-threshold-mb",
        type=float,
        default=LARGE_FILE_THRESHOLD_BYTES / 1024 / 1024,
        help="超過此大小自動使用串流模式，預設 20 MB",
    )
    return parser


def show_title() -> None:
    """顯示 Rich CLI 標題。"""
    console.print(
        Panel.fit(
            "[bold cyan]XML Key Filter[/bold cyan]\n"
            "自動偵測 tag・多 key・namespace・大型檔案串流",
            border_style="cyan",
        )
    )


def show_preview(preview: FilterPreview, output_path: Path | None = None) -> None:
    """顯示執行前統計與結果 XML。"""
    table = Table(title="篩選預覽", show_header=False, border_style="blue")
    table.add_column("欄位", style="bold")
    table.add_column("內容")
    table.add_row("輸入 XML", str(preview.input_path))
    table.add_row("根標籤", preview.root_tag)
    table.add_row("外圍 list tag", preview.item_tag)
    table.add_row("key tag", preview.key_tag)
    table.add_row("保留 keys", ", ".join(preview.target_keys))
    table.add_row("資料總數", str(preview.total_count))
    table.add_row("預計保留", str(preview.kept_count))
    table.add_row("預計刪除", str(preview.removed_count))
    table.add_row("處理模式", "串流" if preview.streaming_recommended else "一般")
    if output_path is not None:
        table.add_row("輸出 XML", str(output_path))
    console.print(table)
    if preview.truncated:
        console.print("[yellow]大型 XML：畫面只顯示前 50 筆匹配資料。[/yellow]")
    console.print(Syntax(preview.preview_xml, "xml", theme="monokai", word_wrap=True))


def run_filter_interactive() -> int:
    """自動偵測 tag，預覽確認後才寫出 XML。"""
    show_title()
    input_text = Prompt.ask("請輸入 XML 檔案路徑").strip().strip('"')
    input_path = Path(input_text).expanduser().resolve()

    try:
        structure = analyze_xml_structure(input_path)
    except XmlFilterError as exc:
        error_console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    default_item = ITEM_TAG if ITEM_TAG in structure.item_tags else (
        structure.item_tags[0] if structure.item_tags else ITEM_TAG
    )
    key_candidates = structure.key_tags_by_item.get(default_item, ())
    default_key = KEY_TAG if KEY_TAG in key_candidates else (
        key_candidates[0] if key_candidates else KEY_TAG
    )

    console.print(
        f"偵測結果：根標籤 [cyan]{structure.root_tag}[/cyan]；"
        f"list tags [cyan]{', '.join(structure.item_tags) or '無'}[/cyan]"
    )
    root_tag = Prompt.ask("根標籤", default=structure.root_tag).strip()
    item_tag = Prompt.ask("外圍 list tag", default=default_item).strip()
    item_key_candidates = structure.key_tags_by_item.get(item_tag, ())
    if KEY_TAG in item_key_candidates:
        default_key = KEY_TAG
    elif item_key_candidates:
        default_key = item_key_candidates[0]
    key_tag = Prompt.ask("key tag", default=default_key).strip()
    keys_text = Prompt.ask("保留 keys（多個請用逗號分隔）").strip()
    suggested_output = default_output_path(input_path)
    output_text = Prompt.ask("輸出 XML 路徑", default=str(suggested_output)).strip().strip('"')
    output_path = Path(output_text).expanduser().resolve()

    try:
        preview = preview_filter(
            input_path,
            keys_text,
            root_tag=root_tag,
            item_tag=item_tag,
            key_tag=key_tag,
        )
    except XmlFilterError as exc:
        error_console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    show_preview(preview, output_path)
    if not Confirm.ask("確認寫入輸出 XML？", default=True):
        console.print("[yellow]已取消，沒有寫入檔案。[/yellow]")
        return 0

    force = output_path.exists() and Confirm.ask(
        "[yellow]輸出檔已存在，確定覆蓋？[/yellow]",
        default=False,
    )
    if output_path.exists() and not force:
        console.print("[yellow]未覆蓋既有檔案。[/yellow]")
        return 0

    try:
        result = filter_xml_by_keys(
            input_path,
            preview.target_keys,
            output_path,
            root_tag=root_tag,
            item_tag=item_tag,
            key_tag=key_tag,
            force=force,
        )
    except XmlFilterError as exc:
        error_console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    _show_result(result)
    return 0


def _show_result(result: FilterResult) -> None:
    mode = "串流" if result.streaming_used else "一般"
    console.print(
        Panel.fit(
            f"[bold green]篩選完成[/bold green]\n"
            f"保留：{result.kept_count} 筆\n"
            f"刪除：{result.removed_count} 筆\n"
            f"模式：{mode}\n"
            f"輸出：{result.output_path}",
            border_style="green",
        )
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 進入點。"""
    args = build_parser().parse_args(argv)
    if args.xml_filepath is None and args.keys is None:
        return run_filter_interactive()
    if args.xml_filepath is None or args.keys is None:
        error_console.print("[bold red]錯誤：必須同時提供 XML 路徑與 key。[/bold red]")
        return 2

    threshold_bytes = max(0, int(args.large_threshold_mb * 1024 * 1024))
    try:
        preview = preview_filter(
            args.xml_filepath,
            args.keys,
            root_tag=args.root_tag,
            item_tag=args.item_tag,
            key_tag=args.key_tag,
            large_threshold_bytes=threshold_bytes,
        )
        if args.preview_only:
            show_preview(preview, args.output)
            return 0
        result = filter_xml_by_keys(
            args.xml_filepath,
            preview.target_keys,
            args.output,
            root_tag=args.root_tag,
            item_tag=args.item_tag,
            key_tag=args.key_tag,
            force=args.force,
            large_threshold_bytes=threshold_bytes,
        )
    except XmlFilterError as exc:
        error_console.print(f"[bold red]錯誤：{exc}[/bold red]")
        return 1

    _show_result(result)
    return 0


__all__ = [
    "ITEM_TAG",
    "KEY_TAG",
    "ROOT_TAG",
    "FilterResult",
    "XmlFilterError",
    "analyze_xml_structure",
    "default_output_path",
    "filter_xml_by_key",
    "filter_xml_by_keys",
    "main",
    "parse_target_keys",
    "preview_filter",
    "run_filter_interactive",
]


if __name__ == "__main__":
    raise SystemExit(main())

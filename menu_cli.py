"""XML 工具的 Rich 總選單入口。"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from filter_xml import run_filter_interactive
from inspect_xml import run_inspect_interactive
from xml_filter_gui import main as run_gui


console = Console()


def show_main_menu() -> None:
    """顯示可執行 CLI 工具清單。"""
    table = Table(title="可執行工具", border_style="cyan")
    table.add_column("選項", justify="center", style="bold cyan")
    table.add_column("工具")
    table.add_column("用途")
    table.add_row("1", "XML Key Filter", "只保留指定 key 的 <data> XML")
    table.add_row("2", "XML Content Inspector", "查看 XML 標籤與完整內容")
    table.add_row("3", "XML Filter GUI", "開啟選檔與完整預覽視窗")
    table.add_row("4", "離開", "結束程式")
    console.print(table)


def main() -> int:
    """啟動總選單並依使用者選擇執行對應 CLI。"""
    console.print(
        Panel.fit(
            "[bold cyan]XML Tools Menu CLI[/bold cyan]\n"
            "請選擇要執行的工具",
            border_style="cyan",
        )
    )

    while True:
        show_main_menu()
        choice = Prompt.ask("請選擇", choices=["1", "2", "3", "4"], default="1")

        if choice == "1":
            run_filter_interactive()
            console.print()
            continue

        if choice == "2":
            run_inspect_interactive()
            console.print()
            continue

        if choice == "3":
            run_gui()
            console.print()
            continue

        console.print("[dim]已離開。[/dim]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

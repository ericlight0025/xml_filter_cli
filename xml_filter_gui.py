"""XML Key Filter 的 Tkinter GUI 入口。"""

from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from filter_xml import ITEM_TAG, XmlFilterError, default_output_path, filter_xml_by_key
from inspect_xml import XmlInspectError, inspect_xml


COLORS = {
    "background": "#111827",
    "surface": "#182230",
    "surface_active": "#243244",
    "border": "#334155",
    "text": "#E5EEF8",
    "muted_text": "#9FB0C3",
    "accent": "#2563EB",
    "accent_active": "#3B82F6",
    "preview_background": "#0B1220",
    "preview_text": "#CBD5E1",
    "tag": "#7DD3FC",
    "attribute": "#C4B5FD",
    "value": "#86EFAC",
    "comment": "#64748B",
    "declaration": "#FBBF24",
    "punctuation": "#94A3B8",
}

XML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
XML_DECLARATION_PATTERN = re.compile(r"<\?.*?\?>", re.DOTALL)
XML_TAG_PATTERN = re.compile(
    r"</?(?P<tag>[A-Za-z_][\w:.-]*)(?P<attributes>[^<>]*?)/?>"
)
XML_ATTRIBUTE_PATTERN = re.compile(
    r"(?P<name>[A-Za-z_][\w:.-]*)\s*=\s*(?P<value>\"[^\"]*\"|'[^']*')"
)


class XmlFilterApp:
    """提供選檔、完整 XML 預覽與篩選另存的桌面介面。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.input_path_var = tk.StringVar()
        self.item_tag_var = tk.StringVar(value=ITEM_TAG)
        self.key_var = tk.StringVar()
        self.status_var = tk.StringVar(value="請先選擇 XML 檔案。")

        self.root.title("XML Key Filter GUI")
        self.root.geometry("1100x720")
        self.root.minsize(820, 560)

        self._configure_dark_theme()
        self._build_layout()

    def _configure_dark_theme(self) -> None:
        """設定深色操作介面與清楚的互動狀態。"""
        self.root.configure(background=COLORS["background"])

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            ".",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=("Microsoft JhengHei UI", 10),
        )
        style.configure("TFrame", background=COLORS["background"])
        style.configure("TLabel", background=COLORS["background"], foreground=COLORS["text"])
        style.configure(
            "Title.TLabel",
            background=COLORS["background"],
            foreground=COLORS["tag"],
            font=("Microsoft JhengHei UI", 18, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=COLORS["background"],
            foreground=COLORS["muted_text"],
        )
        style.configure(
            "TLabelframe",
            background=COLORS["background"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
        )
        style.configure(
            "TLabelframe.Label",
            background=COLORS["background"],
            foreground=COLORS["muted_text"],
            font=("Microsoft JhengHei UI", 10, "bold"),
        )
        style.configure(
            "TEntry",
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            insertcolor=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            padding=6,
        )
        style.configure(
            "TButton",
            background=COLORS["surface_active"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            padding=(10, 6),
        )
        style.map(
            "TButton",
            background=[("active", COLORS["border"])],
            foreground=[("disabled", COLORS["muted_text"])],
        )
        style.configure(
            "Accent.TButton",
            background=COLORS["accent"],
            foreground="#FFFFFF",
            bordercolor=COLORS["accent"],
        )
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["accent_active"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["surface_active"],
            troughcolor=COLORS["preview_background"],
            bordercolor=COLORS["preview_background"],
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=COLORS["surface_active"],
            troughcolor=COLORS["preview_background"],
            bordercolor=COLORS["preview_background"],
        )

    def _build_layout(self) -> None:
        """建立 GUI 的欄位、按鈕與完整內容預覽區。"""
        main_frame = ttk.Frame(self.root, padding=16)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

        ttk.Label(
            main_frame,
            text="XML Key Filter",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 12))

        ttk.Label(main_frame, text="輸入 XML：").grid(
            row=1,
            column=0,
            sticky=tk.W,
            pady=4,
        )
        ttk.Entry(main_frame, textvariable=self.input_path_var).grid(
            row=1,
            column=1,
            sticky=tk.EW,
            padx=(0, 8),
            pady=4,
        )
        ttk.Button(
            main_frame,
            text="選擇 XML",
            command=self.select_input_file,
        ).grid(row=1, column=2, sticky=tk.E, pady=4)

        settings_frame = ttk.LabelFrame(main_frame, text="篩選條件", padding=10)
        settings_frame.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky=tk.EW,
            pady=(10, 8),
        )
        settings_frame.columnconfigure(3, weight=1)

        ttk.Label(settings_frame, text="外圍 list tag：").grid(
            row=0,
            column=0,
            sticky=tk.W,
        )
        ttk.Entry(settings_frame, width=16, textvariable=self.item_tag_var).grid(
            row=0,
            column=1,
            sticky=tk.W,
            padx=(0, 20),
        )
        ttk.Label(settings_frame, text="保留 key：").grid(
            row=0,
            column=2,
            sticky=tk.W,
        )
        ttk.Entry(settings_frame, textvariable=self.key_var).grid(
            row=0,
            column=3,
            sticky=tk.EW,
        )

        actions_frame = ttk.Frame(main_frame)
        actions_frame.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky=tk.EW,
            pady=(0, 10),
        )
        ttk.Button(
            actions_frame,
            text="查看完整 XML",
            command=self.inspect_xml,
        ).pack(side=tk.LEFT)
        ttk.Button(
            actions_frame,
            text="篩選並另存 XML",
            command=self.filter_and_save,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(8, 0))

        preview_frame = ttk.LabelFrame(main_frame, text="完整 XML 預覽", padding=8)
        preview_frame.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky=tk.NSEW,
        )
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview = tk.Text(
            preview_frame,
            wrap=tk.NONE,
            font=("Consolas", 11),
            background=COLORS["preview_background"],
            foreground=COLORS["preview_text"],
            insertbackground=COLORS["text"],
            selectbackground="#1E40AF",
            selectforeground="#FFFFFF",
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED,
        )
        self._configure_xml_tags()
        vertical_scrollbar = ttk.Scrollbar(
            preview_frame,
            orient=tk.VERTICAL,
            command=self.preview.yview,
        )
        horizontal_scrollbar = ttk.Scrollbar(
            preview_frame,
            orient=tk.HORIZONTAL,
            command=self.preview.xview,
        )
        self.preview.configure(
            yscrollcommand=vertical_scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )
        self.preview.grid(row=0, column=0, sticky=tk.NSEW)
        vertical_scrollbar.grid(row=0, column=1, sticky=tk.NS)
        horizontal_scrollbar.grid(row=1, column=0, sticky=tk.EW)

        ttk.Label(
            main_frame,
            textvariable=self.status_var,
            style="Status.TLabel",
        ).grid(
            row=5,
            column=0,
            columnspan=3,
            sticky=tk.W,
            pady=(10, 0),
        )

    def select_input_file(self) -> None:
        """以檔案選擇器選取 XML，並立即顯示完整內容。"""
        selected_path = filedialog.askopenfilename(
            title="選擇輸入 XML",
            filetypes=[("XML 檔案", "*.xml"), ("所有檔案", "*.*")],
        )
        if not selected_path:
            return

        self.input_path_var.set(selected_path)
        self.inspect_xml()

    def inspect_xml(self) -> None:
        """將目前輸入 XML 的完整內容載入預覽區。"""
        input_path = self._get_input_path()
        if input_path is None:
            return

        try:
            inspection = inspect_xml(input_path)
        except XmlInspectError as exc:
            self._show_error(str(exc))
            return

        self._set_preview(inspection.full_xml)
        tag_summary = ", ".join(
            f"<{tag}>：{count}"
            for tag, count in inspection.child_tag_counts.items()
        )
        self.status_var.set(
            f"已載入 <{inspection.root_tag}>；直接子標籤：{tag_summary or '無'}"
        )

    def filter_and_save(self) -> None:
        """依畫面條件篩選 XML，並使用另存對話框安全輸出。"""
        input_path = self._get_input_path()
        if input_path is None:
            return

        item_tag = self.item_tag_var.get().strip()
        target_key = self.key_var.get().strip()
        if not item_tag:
            self._show_error("外圍 list tag 不可為空白。")
            return
        if not target_key:
            self._show_error("保留 key 不可為空白。")
            return

        suggested_path = default_output_path(input_path)
        output_text = filedialog.asksaveasfilename(
            title="另存篩選結果 XML",
            initialfile=suggested_path.name,
            initialdir=str(suggested_path.parent),
            defaultextension=".xml",
            filetypes=[("XML 檔案", "*.xml"), ("所有檔案", "*.*")],
        )
        if not output_text:
            return

        output_path = Path(output_text)
        if output_path == input_path:
            self._show_error("輸出路徑不可與輸入 XML 相同。")
            return

        force = False
        if output_path.exists():
            force = messagebox.askyesno(
                "確認覆蓋",
                f"輸出檔已存在，是否覆蓋？\n{output_path}",
                parent=self.root,
            )
            if not force:
                return

        try:
            result = filter_xml_by_key(
                input_path=input_path,
                target_key=target_key,
                output_path=output_path,
                item_tag=item_tag,
                force=force,
            )
        except XmlFilterError as exc:
            self._show_error(str(exc))
            return

        self.input_path_var.set(str(result.output_path))
        self.inspect_xml()
        messagebox.showinfo(
            "篩選完成",
            f"保留 {result.kept_count} 筆，刪除 {result.removed_count} 筆。\n"
            f"輸出檔：{result.output_path}",
            parent=self.root,
        )

    def _get_input_path(self) -> Path | None:
        """取得並驗證畫面中的輸入 XML 路徑。"""
        input_text = self.input_path_var.get().strip().strip('"')
        if not input_text:
            self._show_error("請先選擇或輸入 XML 檔案路徑。")
            return None

        input_path = Path(input_text).expanduser().resolve()
        if not input_path.is_file():
            self._show_error(f"找不到輸入 XML：{input_path}")
            return None
        return input_path

    def _set_preview(self, content: str) -> None:
        """安全更新唯讀 XML 預覽區，並套用 XML 語法顏色。"""
        self.preview.configure(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", content)
        self._highlight_xml(content)
        self.preview.configure(state=tk.DISABLED)

    def _configure_xml_tags(self) -> None:
        """定義預覽區的 XML 語法色彩。"""
        self.preview.tag_configure("xml_tag", foreground=COLORS["tag"])
        self.preview.tag_configure("xml_attribute", foreground=COLORS["attribute"])
        self.preview.tag_configure("xml_value", foreground=COLORS["value"])
        self.preview.tag_configure("xml_comment", foreground=COLORS["comment"])
        self.preview.tag_configure("xml_declaration", foreground=COLORS["declaration"])
        self.preview.tag_configure("xml_punctuation", foreground=COLORS["punctuation"])

    def _highlight_xml(self, content: str) -> None:
        """依標籤、屬性、字串值與註解套用 XML 編輯器式配色。"""
        for match in XML_COMMENT_PATTERN.finditer(content):
            self._add_text_tag("xml_comment", match.start(), match.end())

        for match in XML_DECLARATION_PATTERN.finditer(content):
            self._add_text_tag("xml_declaration", match.start(), match.end())

        for match in XML_TAG_PATTERN.finditer(content):
            tag_start, tag_end = match.span("tag")
            self._add_text_tag("xml_tag", tag_start, tag_end)
            self._add_text_tag("xml_punctuation", match.start(), tag_start)
            closing_length = 2 if content[match.end() - 2 : match.end()] == "/>" else 1
            self._add_text_tag(
                "xml_punctuation",
                match.end() - closing_length,
                match.end(),
            )

            attributes = match.group("attributes")
            attributes_start = match.start("attributes")
            for attribute_match in XML_ATTRIBUTE_PATTERN.finditer(attributes):
                name_start = attributes_start + attribute_match.start("name")
                name_end = attributes_start + attribute_match.end("name")
                value_start = attributes_start + attribute_match.start("value")
                value_end = attributes_start + attribute_match.end("value")
                self._add_text_tag("xml_attribute", name_start, name_end)
                self._add_text_tag("xml_value", value_start, value_end)

    def _add_text_tag(self, tag_name: str, start: int, end: int) -> None:
        """用字元偏移量將 Tkinter Text tag 套用到指定範圍。"""
        self.preview.tag_add(
            tag_name,
            f"1.0+{start}c",
            f"1.0+{end}c",
        )

    def _show_error(self, message: str) -> None:
        """顯示錯誤並同步更新視窗底部狀態。"""
        self.status_var.set(f"錯誤：{message}")
        messagebox.showerror("XML Key Filter", message, parent=self.root)


def main() -> None:
    """啟動 Tkinter 視窗。"""
    root = tk.Tk()
    XmlFilterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

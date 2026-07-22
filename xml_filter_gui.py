"""XML Key Filter 的深色 Tkinter GUI。"""

from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from inspect_xml import XmlInspectError, inspect_xml
from xml_service import (
    ITEM_TAG,
    KEY_TAG,
    ROOT_TAG,
    FilterPreview,
    XmlFilterError,
    XmlStructure,
    analyze_xml_structure,
    default_output_path,
    filter_xml_by_keys,
    parse_target_keys,
    preview_filter,
)


COLORS = {
    "background": "#111827",
    "surface": "#182230",
    "surface_active": "#243244",
    "border": "#334155",
    "text": "#E5EEF8",
    "muted_text": "#9FB0C3",
    "accent": "#2563EB",
    "accent_active": "#3B82F6",
    "success": "#34D399",
    "warning": "#FBBF24",
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
XML_ELEMENT_TOKEN_PATTERN = re.compile(
    r"<!--.*?-->|<\?.*?\?>|<!\[CDATA\[.*?\]\]>|"
    r"(?P<element></?(?P<tag>[A-Za-z_][\w:.-]*)(?:\s[^<>]*?)?/?>)",
    re.DOTALL,
)


def find_element_content_ranges(content: str, target_tag: str) -> list[tuple[int, int]]:
    """找出指定 tag 的內文範圍，供 GUI 視覺摺疊使用。"""
    ranges: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    target_local = target_tag.rsplit(":", 1)[-1]

    for match in XML_ELEMENT_TOKEN_PATTERN.finditer(content):
        token = match.group("element")
        tag = match.group("tag")
        if token is None or tag is None:
            continue
        tag_local = tag.rsplit(":", 1)[-1]
        if token.startswith("</"):
            if not stack:
                continue
            open_tag, content_start = stack.pop()
            if open_tag == tag_local and tag_local == target_local:
                ranges.append((content_start, match.start()))
            continue
        if token.rstrip().endswith("/>"):
            continue
        stack.append((tag_local, match.end()))
    return ranges


class XmlFilterApp:
    """整合結構分析、篩選預覽、搜尋與安全另存的桌面介面。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.structure: XmlStructure | None = None
        self.current_content = ""
        self.preview_signature: tuple[object, ...] | None = None
        self.search_positions: list[tuple[str, str]] = []
        self.search_index = -1

        self.input_path_var = tk.StringVar()
        self.output_path_var = tk.StringVar(value="尚未輸出")
        self.root_tag_var = tk.StringVar(value=ROOT_TAG)
        self.item_tag_var = tk.StringVar(value=ITEM_TAG)
        self.key_tag_var = tk.StringVar(value=KEY_TAG)
        self.search_var = tk.StringVar()
        self.search_count_var = tk.StringVar(value="0 / 0")
        self.summary_var = tk.StringVar(value="尚未建立篩選預覽")
        self.status_var = tk.StringVar(value="請選擇 XML，系統會自動分析 tag。")

        self.root.title("XML Key Filter Studio")
        self.root.geometry("1280x840")
        self.root.minsize(980, 680)
        self._configure_dark_theme()
        self._build_layout()

    def _configure_dark_theme(self) -> None:
        """設定偏向 XML 編輯器的深色介面。"""
        self.root.configure(background=COLORS["background"])
        self.root.option_add("*TCombobox*Listbox.background", COLORS["surface"])
        self.root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent"])

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
            foreground=COLORS["tag"],
            font=("Microsoft JhengHei UI", 20, "bold"),
        )
        style.configure("Muted.TLabel", foreground=COLORS["muted_text"])
        style.configure(
            "Summary.TLabel",
            foreground=COLORS["success"],
            font=("Microsoft JhengHei UI", 10, "bold"),
        )
        style.configure(
            "TLabelframe",
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
        )
        style.configure(
            "TLabelframe.Label",
            foreground=COLORS["muted_text"],
            font=("Microsoft JhengHei UI", 10, "bold"),
        )
        for entry_style in ("TEntry", "TCombobox"):
            style.configure(
                entry_style,
                fieldbackground=COLORS["surface"],
                foreground=COLORS["text"],
                insertcolor=COLORS["text"],
                bordercolor=COLORS["border"],
                lightcolor=COLORS["border"],
                darkcolor=COLORS["border"],
                arrowcolor=COLORS["muted_text"],
                padding=6,
            )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["surface"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["surface"])],
            selectforeground=[("readonly", COLORS["text"])],
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
        """依分析、條件、預覽、輸出的順序建立畫面。"""
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(6, weight=1)

        title_frame = ttk.Frame(main)
        title_frame.grid(row=0, column=0, columnspan=3, sticky=tk.EW, pady=(0, 12))
        ttk.Label(title_frame, text="XML Key Filter Studio", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(
            title_frame,
            text="分析 → 預覽 → 確認 → 另存",
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT)

        ttk.Label(main, text="原始 XML：").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(main, textvariable=self.input_path_var).grid(
            row=1,
            column=1,
            sticky=tk.EW,
            padx=(0, 8),
            pady=4,
        )
        input_actions = ttk.Frame(main)
        input_actions.grid(row=1, column=2, sticky=tk.E)
        ttk.Button(input_actions, text="選擇 XML", command=self.select_input_file).pack(side=tk.LEFT)
        ttk.Button(input_actions, text="分析", command=self.analyze_input).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(main, text="輸出 XML：").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(main, textvariable=self.output_path_var, state="readonly").grid(
            row=2,
            column=1,
            columnspan=2,
            sticky=tk.EW,
            pady=4,
        )

        settings = ttk.LabelFrame(main, text="篩選條件（自動偵測後仍可手動修改）", padding=10)
        settings.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(10, 8))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)
        settings.columnconfigure(5, weight=1)

        ttk.Label(settings, text="根 tag").grid(row=0, column=0, sticky=tk.W)
        self.root_tag_combo = ttk.Combobox(settings, textvariable=self.root_tag_var)
        self.root_tag_combo.grid(row=0, column=1, sticky=tk.EW, padx=(6, 14))
        ttk.Label(settings, text="list tag").grid(row=0, column=2, sticky=tk.W)
        self.item_tag_combo = ttk.Combobox(settings, textvariable=self.item_tag_var)
        self.item_tag_combo.grid(row=0, column=3, sticky=tk.EW, padx=(6, 14))
        ttk.Label(settings, text="key tag").grid(row=0, column=4, sticky=tk.W)
        self.key_tag_combo = ttk.Combobox(settings, textvariable=self.key_tag_var)
        self.key_tag_combo.grid(row=0, column=5, sticky=tk.EW, padx=(6, 0))

        ttk.Label(settings, text="保留 keys（換行、逗號或分號分隔）").grid(
            row=1,
            column=0,
            columnspan=6,
            sticky=tk.W,
            pady=(10, 4),
        )
        self.keys_text = tk.Text(
            settings,
            height=3,
            wrap=tk.WORD,
            font=("Consolas", 10),
            background=COLORS["surface"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground="#1E40AF",
            relief=tk.FLAT,
            padx=8,
            pady=6,
        )
        self.keys_text.grid(row=2, column=0, columnspan=6, sticky=tk.EW)

        self.item_tag_combo.bind("<<ComboboxSelected>>", self._item_tag_changed)
        self.item_tag_combo.bind("<KeyRelease>", self._conditions_changed)
        self.root_tag_combo.bind("<<ComboboxSelected>>", self._conditions_changed)
        self.root_tag_combo.bind("<KeyRelease>", self._conditions_changed)
        self.key_tag_combo.bind("<<ComboboxSelected>>", self._conditions_changed)
        self.key_tag_combo.bind("<KeyRelease>", self._conditions_changed)
        self.keys_text.bind("<KeyRelease>", self._conditions_changed)

        actions = ttk.Frame(main)
        actions.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        ttk.Button(actions, text="顯示原始 XML", command=self.show_original).pack(side=tk.LEFT)
        ttk.Button(actions, text="預覽篩選結果", command=self.preview_results).pack(side=tk.LEFT, padx=(6, 0))
        self.save_button = ttk.Button(
            actions,
            text="確認並另存 XML",
            command=self.filter_and_save,
            style="Accent.TButton",
        )
        self.save_button.pack(side=tk.LEFT, padx=(6, 0))
        self.save_button.state(["disabled"])
        ttk.Button(actions, text="摺疊 list 節點", command=self.collapse_list_nodes).pack(
            side=tk.LEFT,
            padx=(18, 0),
        )
        ttk.Button(actions, text="展開全部", command=self.expand_all).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(actions, textvariable=self.summary_var, style="Summary.TLabel").pack(side=tk.RIGHT)

        search = ttk.Frame(main)
        search.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="搜尋 XML：").grid(row=0, column=0, sticky=tk.W)
        search_entry = ttk.Entry(search, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 6))
        search_entry.bind("<Return>", lambda _event: self.search_xml())
        ttk.Button(search, text="搜尋", command=self.search_xml).grid(row=0, column=2)
        ttk.Button(search, text="上一筆", command=self.previous_search_result).grid(row=0, column=3, padx=(6, 0))
        ttk.Button(search, text="下一筆", command=self.next_search_result).grid(row=0, column=4, padx=(6, 0))
        ttk.Label(search, textvariable=self.search_count_var, style="Muted.TLabel").grid(
            row=0,
            column=5,
            padx=(10, 0),
        )

        preview_frame = ttk.LabelFrame(main, text="XML 編輯器預覽", padding=8)
        preview_frame.grid(row=6, column=0, columnspan=3, sticky=tk.NSEW)
        preview_frame.columnconfigure(1, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.line_numbers = tk.Text(
            preview_frame,
            width=6,
            wrap=tk.NONE,
            font=("Consolas", 11),
            background="#0F172A",
            foreground=COLORS["comment"],
            relief=tk.FLAT,
            padx=6,
            state=tk.DISABLED,
        )
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
            padx=8,
            borderwidth=0,
            state=tk.DISABLED,
        )
        self._configure_xml_tags()
        vertical = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self._scroll_vertical)
        horizontal = ttk.Scrollbar(preview_frame, orient=tk.HORIZONTAL, command=self.preview.xview)
        self.preview.configure(yscrollcommand=lambda first, last: self._sync_scroll(vertical, first, last))
        self.line_numbers.grid(row=0, column=0, sticky=tk.NS)
        self.preview.grid(row=0, column=1, sticky=tk.NSEW)
        vertical.grid(row=0, column=2, sticky=tk.NS)
        horizontal.grid(row=1, column=1, sticky=tk.EW)

        ttk.Label(main, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=7,
            column=0,
            columnspan=3,
            sticky=tk.W,
            pady=(10, 0),
        )

    def select_input_file(self) -> None:
        """選取 XML 並自動分析結構。"""
        selected = filedialog.askopenfilename(
            title="選擇輸入 XML",
            filetypes=[("XML 檔案", "*.xml"), ("所有檔案", "*.*")],
        )
        if selected:
            self.input_path_var.set(selected)
            self.analyze_input()

    def analyze_input(self) -> None:
        """自動偵測 root、list 與候選 key tag。"""
        input_path = self._get_input_path()
        if input_path is None:
            return
        try:
            self.structure = analyze_xml_structure(input_path)
        except XmlFilterError as exc:
            self._show_error(str(exc))
            return

        structure = self.structure
        self.root_tag_combo["values"] = (structure.root_tag,)
        self.root_tag_var.set(structure.root_tag)
        self.item_tag_combo["values"] = structure.item_tags
        item_tag = ITEM_TAG if ITEM_TAG in structure.item_tags else (
            structure.item_tags[0] if structure.item_tags else ITEM_TAG
        )
        self.item_tag_var.set(item_tag)
        self._update_key_tag_values(item_tag)
        self.output_path_var.set("尚未輸出")
        self._invalidate_preview("已分析 XML，請輸入要保留的 key 後建立預覽。")
        self.show_original()

    def _update_key_tag_values(self, item_tag: str) -> None:
        candidates = self.structure.key_tags_by_item.get(item_tag, ()) if self.structure else ()
        self.key_tag_combo["values"] = candidates
        selected = KEY_TAG if KEY_TAG in candidates else (candidates[0] if candidates else KEY_TAG)
        self.key_tag_var.set(selected)

    def _item_tag_changed(self, _event: object | None = None) -> None:
        self._update_key_tag_values(self.item_tag_var.get().strip())
        self._invalidate_preview("list tag 已變更，請重新預覽。")

    def _conditions_changed(self, _event: object | None = None) -> None:
        self._invalidate_preview("篩選條件已變更，請重新預覽。")

    def _invalidate_preview(self, message: str) -> None:
        self.preview_signature = None
        self.save_button.state(["disabled"])
        self.summary_var.set("尚未建立有效預覽")
        self.status_var.set(message)

    def show_original(self) -> None:
        """顯示原始 XML；大型檔案自動顯示安全樣本。"""
        input_path = self._get_input_path()
        if input_path is None:
            return
        try:
            inspection = inspect_xml(input_path)
        except XmlInspectError as exc:
            self._show_error(str(exc))
            return
        self._set_preview(inspection.full_xml, store=True)
        suffix = "；大型檔案僅顯示前 50 個節點" if inspection.truncated else "；已完整顯示"
        self.status_var.set(
            f"原始 XML <{inspection.root_tag}>，{inspection.file_size / 1024 / 1024:.2f} MB{suffix}。"
        )

    def preview_results(self) -> None:
        """計算保留／刪除筆數，成功後才開放另存。"""
        settings = self._get_filter_settings()
        if settings is None:
            return
        input_path, root_tag, item_tag, key_tag, keys = settings
        try:
            result_preview = preview_filter(
                input_path,
                keys,
                root_tag=root_tag,
                item_tag=item_tag,
                key_tag=key_tag,
            )
        except XmlFilterError as exc:
            self._show_error(str(exc))
            return

        self._set_preview(result_preview.preview_xml, store=True)
        self.preview_signature = self._current_signature()
        self.save_button.state(["!disabled"])
        self._show_preview_summary(result_preview)

    def _show_preview_summary(self, result_preview: FilterPreview) -> None:
        self.summary_var.set(
            f"總數 {result_preview.total_count}｜保留 {result_preview.kept_count}｜"
            f"刪除 {result_preview.removed_count}"
        )
        mode = "大型檔案串流模式" if result_preview.streaming_recommended else "一般模式"
        suffix = "，內容只顯示前 50 筆" if result_preview.truncated else ""
        self.status_var.set(f"篩選預覽完成：{mode}{suffix}。確認無誤後即可另存。")

    def filter_and_save(self) -> None:
        """只有目前條件已預覽時，才允許安全另存。"""
        settings = self._get_filter_settings()
        if settings is None:
            return
        if self.preview_signature != self._current_signature():
            self._show_error("篩選條件已改變，請先重新預覽結果。")
            return
        input_path, root_tag, item_tag, key_tag, keys = settings
        suggested = default_output_path(input_path)
        output_text = filedialog.asksaveasfilename(
            title="另存篩選結果 XML",
            initialfile=suggested.name,
            initialdir=str(suggested.parent),
            defaultextension=".xml",
            filetypes=[("XML 檔案", "*.xml"), ("所有檔案", "*.*")],
        )
        if not output_text:
            return
        output_path = Path(output_text).expanduser().resolve()
        if output_path == input_path:
            self._show_error("輸出路徑不可與原始 XML 相同。")
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
            result = filter_xml_by_keys(
                input_path,
                keys,
                output_path,
                root_tag=root_tag,
                item_tag=item_tag,
                key_tag=key_tag,
                force=force,
            )
        except XmlFilterError as exc:
            self._show_error(str(exc))
            return

        self.output_path_var.set(str(result.output_path))
        mode = "串流" if result.streaming_used else "一般"
        self.status_var.set(f"輸出完成：{result.output_path}（{mode}模式）")
        messagebox.showinfo(
            "篩選完成",
            f"保留 {result.kept_count} 筆，刪除 {result.removed_count} 筆。\n"
            f"原始檔保持不變。\n輸出檔：{result.output_path}",
            parent=self.root,
        )

    def search_xml(self) -> None:
        """標記所有搜尋結果並移動到第一筆。"""
        query = self.search_var.get()
        self.preview.tag_remove("search_all", "1.0", tk.END)
        self.preview.tag_remove("search_current", "1.0", tk.END)
        self.search_positions = []
        self.search_index = -1
        if not query:
            self.search_count_var.set("0 / 0")
            return
        start = "1.0"
        while True:
            position = self.preview.search(query, start, stopindex=tk.END, nocase=True)
            if not position:
                break
            end = f"{position}+{len(query)}c"
            self.search_positions.append((position, end))
            self.preview.tag_add("search_all", position, end)
            start = end
        if self.search_positions:
            self.search_index = 0
            self._select_search_result()
        else:
            self.search_count_var.set("0 / 0")
            self.status_var.set(f"找不到：{query}")

    def next_search_result(self) -> None:
        if not self.search_positions:
            self.search_xml()
            return
        self.search_index = (self.search_index + 1) % len(self.search_positions)
        self._select_search_result()

    def previous_search_result(self) -> None:
        if not self.search_positions:
            self.search_xml()
            return
        self.search_index = (self.search_index - 1) % len(self.search_positions)
        self._select_search_result()

    def _select_search_result(self) -> None:
        self.preview.tag_remove("search_current", "1.0", tk.END)
        start, end = self.search_positions[self.search_index]
        self.preview.tag_add("search_current", start, end)
        self.preview.see(start)
        self.search_count_var.set(f"{self.search_index + 1} / {len(self.search_positions)}")

    def collapse_list_nodes(self) -> None:
        """將目前 list tag 的節點內容折成省略符號。"""
        if not self.current_content:
            return
        ranges = find_element_content_ranges(self.current_content, self.item_tag_var.get().strip())
        if not ranges:
            self.status_var.set("目前畫面找不到可摺疊的 list 節點。")
            return
        collapsed = self.current_content
        for start, end in reversed(ranges):
            collapsed = collapsed[:start] + " …內容已摺疊… " + collapsed[end:]
        self._render_preview(collapsed)
        self.status_var.set(f"已摺疊 {len(ranges)} 個 <{self.item_tag_var.get().strip()}> 節點。")

    def expand_all(self) -> None:
        if self.current_content:
            self._render_preview(self.current_content)
            self.status_var.set("已展開所有 XML 內容。")

    def _get_input_path(self) -> Path | None:
        input_text = self.input_path_var.get().strip().strip('"')
        if not input_text:
            self._show_error("請先選擇或輸入 XML 檔案路徑。")
            return None
        input_path = Path(input_text).expanduser().resolve()
        if not input_path.is_file():
            self._show_error(f"找不到輸入 XML：{input_path}")
            return None
        return input_path

    def _get_filter_settings(
        self,
    ) -> tuple[Path, str, str, str, tuple[str, ...]] | None:
        input_path = self._get_input_path()
        if input_path is None:
            return None
        root_tag = self.root_tag_var.get().strip()
        item_tag = self.item_tag_var.get().strip()
        key_tag = self.key_tag_var.get().strip()
        keys = parse_target_keys(self.keys_text.get("1.0", tk.END))
        if not root_tag or not item_tag or not key_tag:
            self._show_error("root tag、list tag 與 key tag 都不可空白。")
            return None
        if not keys:
            self._show_error("請至少輸入一個要保留的 key。")
            return None
        return input_path, root_tag, item_tag, key_tag, keys

    def _current_signature(self) -> tuple[object, ...]:
        path = self.input_path_var.get().strip().strip('"')
        keys = parse_target_keys(self.keys_text.get("1.0", tk.END))
        return (
            path,
            self.root_tag_var.get().strip(),
            self.item_tag_var.get().strip(),
            self.key_tag_var.get().strip(),
            keys,
        )

    def _set_preview(self, content: str, *, store: bool) -> None:
        if store:
            self.current_content = content
        self._render_preview(content)

    def _render_preview(self, content: str) -> None:
        self.preview.configure(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", content)
        self._highlight_xml(content)
        self.preview.configure(state=tk.DISABLED)
        self._update_line_numbers(content)
        self.search_positions = []
        self.search_index = -1
        self.search_count_var.set("0 / 0")

    def _update_line_numbers(self, content: str) -> None:
        count = max(1, content.count("\n") + 1)
        numbers = "\n".join(str(index) for index in range(1, count + 1))
        self.line_numbers.configure(state=tk.NORMAL)
        self.line_numbers.delete("1.0", tk.END)
        self.line_numbers.insert("1.0", numbers)
        self.line_numbers.configure(state=tk.DISABLED)

    def _configure_xml_tags(self) -> None:
        self.preview.tag_configure("xml_tag", foreground=COLORS["tag"])
        self.preview.tag_configure("xml_attribute", foreground=COLORS["attribute"])
        self.preview.tag_configure("xml_value", foreground=COLORS["value"])
        self.preview.tag_configure("xml_comment", foreground=COLORS["comment"])
        self.preview.tag_configure("xml_declaration", foreground=COLORS["declaration"])
        self.preview.tag_configure("xml_punctuation", foreground=COLORS["punctuation"])
        self.preview.tag_configure("search_all", background="#4A3B10", foreground="#FEF3C7")
        self.preview.tag_configure("search_current", background="#B45309", foreground="#FFFFFF")

    def _highlight_xml(self, content: str) -> None:
        for match in XML_COMMENT_PATTERN.finditer(content):
            self._add_text_tag("xml_comment", match.start(), match.end())
        for match in XML_DECLARATION_PATTERN.finditer(content):
            self._add_text_tag("xml_declaration", match.start(), match.end())
        for match in XML_TAG_PATTERN.finditer(content):
            tag_start, tag_end = match.span("tag")
            self._add_text_tag("xml_tag", tag_start, tag_end)
            self._add_text_tag("xml_punctuation", match.start(), tag_start)
            closing_length = 2 if content[match.end() - 2 : match.end()] == "/>" else 1
            self._add_text_tag("xml_punctuation", match.end() - closing_length, match.end())
            attributes = match.group("attributes")
            attributes_start = match.start("attributes")
            for attribute in XML_ATTRIBUTE_PATTERN.finditer(attributes):
                self._add_text_tag(
                    "xml_attribute",
                    attributes_start + attribute.start("name"),
                    attributes_start + attribute.end("name"),
                )
                self._add_text_tag(
                    "xml_value",
                    attributes_start + attribute.start("value"),
                    attributes_start + attribute.end("value"),
                )

    def _add_text_tag(self, tag_name: str, start: int, end: int) -> None:
        self.preview.tag_add(tag_name, f"1.0+{start}c", f"1.0+{end}c")

    def _scroll_vertical(self, *args: object) -> None:
        self.preview.yview(*args)
        self.line_numbers.yview(*args)

    def _sync_scroll(self, scrollbar: ttk.Scrollbar, first: str, last: str) -> None:
        scrollbar.set(first, last)
        self.line_numbers.yview_moveto(first)

    def _show_error(self, message: str) -> None:
        self.status_var.set(f"錯誤：{message}")
        messagebox.showerror("XML Key Filter", message, parent=self.root)


def main() -> None:
    """啟動 Tkinter 視窗。"""
    root = tk.Tk()
    XmlFilterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

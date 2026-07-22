"""XML 結構分析、預覽與安全篩選服務。"""

from __future__ import annotations

import copy
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT_TAG = "datalist"
ITEM_TAG = "data"
KEY_TAG = "key"
LARGE_FILE_THRESHOLD_BYTES = 20 * 1024 * 1024
LARGE_PREVIEW_ITEM_LIMIT = 50


class XmlFilterError(Exception):
    """XML 篩選作業的可預期錯誤。"""


@dataclass(frozen=True)
class XmlStructure:
    """XML 根節點、list tag 與候選 key tag。"""

    input_path: Path
    file_size: int
    root_tag: str
    item_tags: tuple[str, ...]
    child_tag_counts: dict[str, int]
    key_tags_by_item: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class FilterPreview:
    """真正寫檔前的篩選統計與 XML 預覽。"""

    input_path: Path
    root_tag: str
    item_tag: str
    key_tag: str
    target_keys: tuple[str, ...]
    total_count: int
    kept_count: int
    removed_count: int
    matched_keys: tuple[str, ...]
    preview_xml: str
    truncated: bool
    streaming_recommended: bool


@dataclass(frozen=True)
class FilterResult:
    """篩選完成後的統計資料。"""

    output_path: Path
    kept_count: int
    removed_count: int
    streaming_used: bool = False


def local_name(tag: str) -> str:
    """移除 ElementTree namespace 或 XML prefix，只回傳本地 tag 名稱。"""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def parse_target_keys(values: str | Iterable[str]) -> tuple[str, ...]:
    """接受換行、逗號或分號分隔的多個 key，去除空白與重複值。"""
    if isinstance(values, str):
        candidates = re.split(r"[\n,;]+", values)
    else:
        candidates = []
        for value in values:
            candidates.extend(re.split(r"[\n,;]+", str(value)))

    unique_keys: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.strip()
        if key and key not in seen:
            seen.add(key)
            unique_keys.append(key)
    return tuple(unique_keys)


def default_output_path(input_path: Path) -> Path:
    """產生不覆蓋原始檔案的預設輸出路徑。"""
    return input_path.with_name(f"{input_path.stem}.filtered{input_path.suffix}")


def analyze_xml_structure(input_path: Path) -> XmlStructure:
    """以 iterparse 掃描 XML，偵測根、直接子節點與其欄位 tag。"""
    input_path = _validated_input_path(input_path)
    child_counts: Counter[str] = Counter()
    key_tags: dict[str, Counter[str]] = defaultdict(Counter)
    root_tag = ""
    depth = 0

    try:
        for event, element in ET.iterparse(input_path, events=("start", "end")):
            if event == "start":
                depth += 1
                if depth == 1:
                    root_tag = local_name(element.tag)
                continue

            if depth == 2:
                item_name = local_name(element.tag)
                child_counts[item_name] += 1
                for child in list(element):
                    key_tags[item_name][local_name(child.tag)] += 1
                element.clear()
            depth -= 1
    except ET.ParseError as exc:
        raise XmlFilterError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        raise XmlFilterError(f"無法讀取 XML：{exc}") from exc

    if not root_tag:
        raise XmlFilterError("XML 沒有根標籤。")

    return XmlStructure(
        input_path=input_path,
        file_size=input_path.stat().st_size,
        root_tag=root_tag,
        item_tags=tuple(child_counts.keys()),
        child_tag_counts=dict(child_counts),
        key_tags_by_item={
            item_name: tuple(counter.keys())
            for item_name, counter in key_tags.items()
        },
    )


def preview_filter(
    input_path: Path,
    target_keys: str | Iterable[str],
    *,
    root_tag: str = ROOT_TAG,
    item_tag: str = ITEM_TAG,
    key_tag: str = KEY_TAG,
    large_threshold_bytes: int = LARGE_FILE_THRESHOLD_BYTES,
    large_preview_limit: int = LARGE_PREVIEW_ITEM_LIMIT,
) -> FilterPreview:
    """計算篩選結果；小檔顯示完整結果，大檔顯示匹配樣本。"""
    input_path = _validated_input_path(input_path)
    keys = _validated_filter_settings(target_keys, root_tag, item_tag, key_tag)
    streaming = input_path.stat().st_size >= large_threshold_bytes

    if streaming:
        return _preview_streaming(
            input_path,
            keys,
            root_tag=root_tag,
            item_tag=item_tag,
            key_tag=key_tag,
            preview_limit=large_preview_limit,
        )
    return _preview_in_memory(
        input_path,
        keys,
        root_tag=root_tag,
        item_tag=item_tag,
        key_tag=key_tag,
    )


def filter_xml_by_keys(
    input_path: Path,
    target_keys: str | Iterable[str],
    output_path: Path | None = None,
    *,
    root_tag: str = ROOT_TAG,
    item_tag: str = ITEM_TAG,
    key_tag: str = KEY_TAG,
    force: bool = False,
    large_threshold_bytes: int = LARGE_FILE_THRESHOLD_BYTES,
) -> FilterResult:
    """依多個 key 篩選 XML，檔案較大時自動使用串流輸出。"""
    input_path = _validated_input_path(input_path)
    output_path = (output_path or default_output_path(input_path)).expanduser().resolve()
    keys = _validated_filter_settings(target_keys, root_tag, item_tag, key_tag)
    _validate_output_path(input_path, output_path, force)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if input_path.stat().st_size >= large_threshold_bytes:
        return _filter_streaming(
            input_path,
            output_path,
            keys,
            root_tag=root_tag,
            item_tag=item_tag,
            key_tag=key_tag,
        )
    return _filter_in_memory(
        input_path,
        output_path,
        keys,
        root_tag=root_tag,
        item_tag=item_tag,
        key_tag=key_tag,
    )


def filter_xml_by_key(
    input_path: Path,
    target_key: str,
    output_path: Path | None = None,
    *,
    root_tag: str = ROOT_TAG,
    item_tag: str = ITEM_TAG,
    key_tag: str = KEY_TAG,
    force: bool = False,
    large_threshold_bytes: int = LARGE_FILE_THRESHOLD_BYTES,
) -> FilterResult:
    """保留單一 key 的相容入口。"""
    return filter_xml_by_keys(
        input_path,
        target_key,
        output_path,
        root_tag=root_tag,
        item_tag=item_tag,
        key_tag=key_tag,
        force=force,
        large_threshold_bytes=large_threshold_bytes,
    )


def _preview_in_memory(
    input_path: Path,
    keys: tuple[str, ...],
    *,
    root_tag: str,
    item_tag: str,
    key_tag: str,
) -> FilterPreview:
    tree = _parse_tree(input_path)
    root = tree.getroot()
    _validate_root(root, root_tag)
    kept, removed, matched = _filter_tree(root, set(keys), item_tag, key_tag)
    _raise_if_no_match(keys, item_tag, kept)
    ET.indent(tree, space="    ")
    preview_xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    return FilterPreview(
        input_path=input_path,
        root_tag=local_name(root.tag),
        item_tag=item_tag,
        key_tag=key_tag,
        target_keys=keys,
        total_count=kept + removed,
        kept_count=kept,
        removed_count=removed,
        matched_keys=tuple(matched),
        preview_xml=preview_xml,
        truncated=False,
        streaming_recommended=False,
    )


def _preview_streaming(
    input_path: Path,
    keys: tuple[str, ...],
    *,
    root_tag: str,
    item_tag: str,
    key_tag: str,
    preview_limit: int,
) -> FilterPreview:
    key_set = set(keys)
    kept = 0
    removed = 0
    matched: list[str] = []
    preview_root: ET.Element | None = None
    depth = 0
    displayed_nodes = 0
    truncated = False

    try:
        for event, payload in ET.iterparse(
            input_path,
            events=("start-ns", "start", "end"),
        ):
            if event == "start-ns":
                _register_namespace(payload)
                continue
            element = payload
            if event == "start":
                depth += 1
                if depth == 1:
                    _validate_root(element, root_tag)
                    preview_root = ET.Element(element.tag, dict(element.attrib))
                continue

            if depth == 2:
                if local_name(element.tag) == item_tag:
                    value = _key_value(element, key_tag)
                    if value in key_set:
                        kept += 1
                        matched.append(value)
                        if preview_root is not None and displayed_nodes < preview_limit:
                            preview_root.append(copy.deepcopy(element))
                            displayed_nodes += 1
                        else:
                            truncated = True
                    else:
                        removed += 1
                elif preview_root is not None:
                    if displayed_nodes < preview_limit:
                        preview_root.append(copy.deepcopy(element))
                        displayed_nodes += 1
                    else:
                        truncated = True
                element.clear()
            depth -= 1
    except ET.ParseError as exc:
        raise XmlFilterError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        raise XmlFilterError(f"無法讀取 XML：{exc}") from exc

    _raise_if_no_match(keys, item_tag, kept)
    if preview_root is None:
        raise XmlFilterError("XML 沒有根標籤。")
    ET.indent(preview_root, space="    ")
    preview_xml = ET.tostring(preview_root, encoding="unicode", short_empty_elements=True)
    return FilterPreview(
        input_path=input_path,
        root_tag=local_name(preview_root.tag),
        item_tag=item_tag,
        key_tag=key_tag,
        target_keys=keys,
        total_count=kept + removed,
        kept_count=kept,
        removed_count=removed,
        matched_keys=tuple(matched),
        preview_xml=preview_xml,
        truncated=truncated,
        streaming_recommended=True,
    )


def _filter_in_memory(
    input_path: Path,
    output_path: Path,
    keys: tuple[str, ...],
    *,
    root_tag: str,
    item_tag: str,
    key_tag: str,
) -> FilterResult:
    tree = _parse_tree(input_path)
    root = tree.getroot()
    _validate_root(root, root_tag)
    kept, removed, _matched = _filter_tree(root, set(keys), item_tag, key_tag)
    _raise_if_no_match(keys, item_tag, kept)
    ET.indent(tree, space="    ")
    temp_path = _temporary_output_path(output_path)
    try:
        tree.write(temp_path, encoding="utf-8", xml_declaration=True)
        temp_path.replace(output_path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise XmlFilterError(f"無法寫入輸出 XML：{exc}") from exc
    return FilterResult(output_path, kept, removed, streaming_used=False)


def _filter_streaming(
    input_path: Path,
    output_path: Path,
    keys: tuple[str, ...],
    *,
    root_tag: str,
    item_tag: str,
    key_tag: str,
) -> FilterResult:
    key_set = set(keys)
    kept = 0
    removed = 0
    depth = 0
    temp_path = _temporary_output_path(output_path)
    output_file = None

    try:
        output_file = temp_path.open("w", encoding="utf-8", newline="\n")
        output_file.write("<?xml version='1.0' encoding='utf-8'?>\n")
        for event, payload in ET.iterparse(
            input_path,
            events=("start-ns", "start", "end"),
        ):
            if event == "start-ns":
                _register_namespace(payload)
                continue
            element = payload
            if event == "start":
                depth += 1
                if depth == 1:
                    _validate_root(element, root_tag)
                    opening, _closing = _root_tags(element)
                    output_file.write(opening + "\n")
                continue

            if depth == 2:
                should_write = True
                if local_name(element.tag) == item_tag:
                    value = _key_value(element, key_tag)
                    should_write = value in key_set
                    if should_write:
                        kept += 1
                    else:
                        removed += 1
                if should_write:
                    element.tail = None
                    ET.indent(element, space="    ", level=1)
                    output_file.write(
                        ET.tostring(
                            element,
                            encoding="unicode",
                            short_empty_elements=True,
                        )
                    )
                    output_file.write("\n")
                element.clear()
            elif depth == 1:
                _opening, closing = _root_tags(element)
                output_file.write(closing + "\n")
            depth -= 1

        output_file.close()
        output_file = None
        _raise_if_no_match(keys, item_tag, kept)
        temp_path.replace(output_path)
    except ET.ParseError as exc:
        if output_file is not None:
            output_file.close()
        temp_path.unlink(missing_ok=True)
        raise XmlFilterError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        if output_file is not None:
            output_file.close()
        temp_path.unlink(missing_ok=True)
        raise XmlFilterError(f"無法寫入輸出 XML：{exc}") from exc
    except XmlFilterError:
        if output_file is not None:
            output_file.close()
        temp_path.unlink(missing_ok=True)
        raise

    return FilterResult(output_path, kept, removed, streaming_used=True)


def _filter_tree(
    root: ET.Element,
    keys: set[str],
    item_tag: str,
    key_tag: str,
) -> tuple[int, int, list[str]]:
    kept = 0
    removed = 0
    matched: list[str] = []
    for node in list(root):
        if local_name(node.tag) != item_tag:
            continue
        value = _key_value(node, key_tag)
        if value in keys:
            kept += 1
            matched.append(value)
        else:
            root.remove(node)
            removed += 1
    return kept, removed, matched


def _key_value(item: ET.Element, key_tag: str) -> str:
    for child in list(item):
        if local_name(child.tag) == key_tag:
            return (child.text or "").strip()
    return ""


def _parse_tree(input_path: Path) -> ET.ElementTree:
    namespaces: list[tuple[str, str]] = []
    try:
        for _event, namespace in ET.iterparse(input_path, events=("start-ns",)):
            namespaces.append(namespace)
        for namespace in namespaces:
            _register_namespace(namespace)
        return ET.parse(input_path)
    except ET.ParseError as exc:
        raise XmlFilterError(f"XML 格式錯誤：{exc}") from exc
    except OSError as exc:
        raise XmlFilterError(f"無法讀取 XML：{exc}") from exc


def _root_tags(root: ET.Element) -> tuple[str, str]:
    shallow_root = ET.Element(root.tag, dict(root.attrib))
    serialized = ET.tostring(shallow_root, encoding="unicode", short_empty_elements=True)
    if not serialized.endswith(" />") and not serialized.endswith("/>"):
        raise XmlFilterError("無法建立串流 XML 根標籤。")
    marker_length = 3 if serialized.endswith(" />") else 2
    opening = serialized[:-marker_length] + ">"
    match = re.match(r"<([^\s>/]+)", opening)
    if match is None:
        raise XmlFilterError("無法辨識串流 XML 根標籤。")
    return opening, f"</{match.group(1)}>"


def _register_namespace(namespace: tuple[str, str]) -> None:
    prefix, uri = namespace
    try:
        ET.register_namespace(prefix or "", uri)
    except ValueError:
        # ElementTree 不允許保留的 ns\d+ prefix；不影響 local-name 篩選。
        pass


def _validated_input_path(input_path: Path) -> Path:
    resolved = input_path.expanduser().resolve()
    if not resolved.is_file():
        raise XmlFilterError(f"找不到輸入 XML：{resolved}")
    return resolved


def _validated_filter_settings(
    target_keys: str | Iterable[str],
    root_tag: str,
    item_tag: str,
    key_tag: str,
) -> tuple[str, ...]:
    keys = parse_target_keys(target_keys)
    if not keys:
        raise XmlFilterError("至少需要一個 key。")
    if not root_tag.strip():
        raise XmlFilterError("根標籤不可為空白。")
    if not item_tag.strip():
        raise XmlFilterError("外圍 list tag 不可為空白。")
    if not key_tag.strip():
        raise XmlFilterError("key tag 不可為空白。")
    return keys


def _validate_output_path(input_path: Path, output_path: Path, force: bool) -> None:
    if input_path == output_path:
        raise XmlFilterError("輸出路徑不可與輸入路徑相同，避免破壞原始 XML。")
    if output_path.exists() and not force:
        raise XmlFilterError(
            f"輸出檔已存在：{output_path}。如要覆蓋，請明確允許覆蓋。"
        )


def _validate_root(root: ET.Element, expected_root_tag: str) -> None:
    actual = local_name(root.tag)
    if actual != expected_root_tag:
        raise XmlFilterError(
            f"最外層標籤必須是 <{expected_root_tag}>，目前是 <{actual}>。"
        )


def _raise_if_no_match(keys: tuple[str, ...], item_tag: str, kept: int) -> None:
    if kept == 0:
        joined = ", ".join(keys)
        raise XmlFilterError(
            f"找不到 key={joined!r} 的 <{item_tag}>，未建立輸出檔。"
        )


def _temporary_output_path(output_path: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{output_path.stem}.",
        suffix=".tmp",
        dir=output_path.parent,
        delete=False,
    )
    handle.close()
    return Path(handle.name)

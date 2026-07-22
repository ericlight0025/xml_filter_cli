"""XML Filter 的核心、CLI、Inspector 與 GUI 輔助功能測試。"""

from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import menu_cli  # noqa: E402
import xml_filter_gui  # noqa: E402
from filter_xml import main, run_filter_interactive  # noqa: E402
from inspect_xml import inspect_xml  # noqa: E402
from xml_filter_gui import find_element_content_ranges  # noqa: E402
from xml_service import (  # noqa: E402
    XmlFilterError,
    analyze_xml_structure,
    filter_xml_by_key,
    filter_xml_by_keys,
    local_name,
    parse_target_keys,
    preview_filter,
)


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<datalist source="模擬資料">
    <data>
        <key>A001</key>
        <name>第一筆資料</name>
    </data>
    <data>
        <key>A002</key>
        <name>第二筆資料</name>
    </data>
    <data>
        <key>A002</key>
        <name>第二筆重複 key 資料</name>
    </data>
    <data>
        <key>A003</key>
        <name>第三筆資料</name>
    </data>
</datalist>
"""

NAMESPACE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ns:datalist xmlns:ns="urn:example">
    <ns:data><ns:key>N001</ns:key><ns:name>第一筆</ns:name></ns:data>
    <ns:data><ns:key>N002</ns:key><ns:name>第二筆</ns:name></ns:data>
</ns:datalist>
"""


class FilterXmlTests(unittest.TestCase):
    """驗證 XML 篩選的正常流程與安全防護。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.input_path = self.work_dir / "input.xml"
        self.input_path.write_text(SAMPLE_XML, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_keep_all_nodes_with_matching_key(self) -> None:
        output_path = self.work_dir / "result.xml"
        result = filter_xml_by_key(self.input_path, "A002", output_path)
        root = ET.parse(output_path).getroot()
        keys = [node.findtext("key") for node in root.findall("data")]
        self.assertEqual(keys, ["A002", "A002"])
        self.assertEqual(root.attrib["source"], "模擬資料")
        self.assertEqual((result.kept_count, result.removed_count), (2, 2))

    def test_multiple_keys_are_kept(self) -> None:
        output_path = self.work_dir / "multi.xml"
        result = filter_xml_by_keys(self.input_path, "A001, A003", output_path)
        keys = [node.findtext("key") for node in ET.parse(output_path).getroot()]
        self.assertEqual(keys, ["A001", "A003"])
        self.assertEqual((result.kept_count, result.removed_count), (2, 2))

    def test_parse_target_keys_supports_newline_comma_and_semicolon(self) -> None:
        keys = parse_target_keys("A001\nA002; A003, A002")
        self.assertEqual(keys, ("A001", "A002", "A003"))

    def test_no_match_does_not_create_output(self) -> None:
        output_path = self.work_dir / "not-created.xml"
        with self.assertRaisesRegex(XmlFilterError, "找不到 key"):
            filter_xml_by_key(self.input_path, "Z999", output_path)
        self.assertFalse(output_path.exists())

    def test_reject_wrong_root_tag(self) -> None:
        self.input_path.write_text("<items><data><key>A001</key></data></items>", encoding="utf-8")
        with self.assertRaisesRegex(XmlFilterError, "最外層標籤"):
            filter_xml_by_key(self.input_path, "A001")

    def test_reject_malformed_xml(self) -> None:
        self.input_path.write_text("<datalist><data></datalist>", encoding="utf-8")
        with self.assertRaisesRegex(XmlFilterError, "XML 格式錯誤"):
            filter_xml_by_key(self.input_path, "A001")

    def test_reject_existing_output_without_force(self) -> None:
        output_path = self.work_dir / "existing.xml"
        output_path.write_text("原有內容", encoding="utf-8")
        with self.assertRaisesRegex(XmlFilterError, "輸出檔已存在"):
            filter_xml_by_key(self.input_path, "A001", output_path)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "原有內容")

    def test_force_overwrites_existing_output(self) -> None:
        output_path = self.work_dir / "existing.xml"
        output_path.write_text("原有內容", encoding="utf-8")
        result = filter_xml_by_key(self.input_path, "A001", output_path, force=True)
        self.assertEqual(result.kept_count, 1)
        self.assertEqual(ET.parse(output_path).getroot().findtext("data/key"), "A001")

    def test_reject_same_input_and_output_path(self) -> None:
        with self.assertRaisesRegex(XmlFilterError, "不可與輸入路徑相同"):
            filter_xml_by_key(self.input_path, "A001", self.input_path, force=True)

    def test_custom_root_item_and_key_tags_are_supported(self) -> None:
        custom = self.work_dir / "custom.xml"
        output = self.work_dir / "custom-result.xml"
        custom.write_text(
            "<records><record><code>X001</code></record>"
            "<record><code>X002</code></record></records>",
            encoding="utf-8",
        )
        result = filter_xml_by_key(
            custom,
            "X002",
            output,
            root_tag="records",
            item_tag="record",
            key_tag="code",
        )
        self.assertEqual(result.kept_count, 1)
        self.assertEqual(ET.parse(output).getroot().findtext("record/code"), "X002")

    def test_namespace_xml_is_filtered_by_local_tag_names(self) -> None:
        namespace_input = self.work_dir / "namespace.xml"
        output = self.work_dir / "namespace-result.xml"
        namespace_input.write_text(NAMESPACE_XML, encoding="utf-8")
        result = filter_xml_by_key(namespace_input, "N002", output)
        root = ET.parse(output).getroot()
        children = [node for node in root if local_name(node.tag) == "data"]
        self.assertEqual(result.kept_count, 1)
        self.assertEqual(
            next(child.text for child in children[0] if local_name(child.tag) == "key"),
            "N002",
        )

    def test_streaming_namespace_output_is_valid(self) -> None:
        namespace_input = self.work_dir / "namespace-stream.xml"
        output = self.work_dir / "namespace-stream-result.xml"
        namespace_input.write_text(NAMESPACE_XML, encoding="utf-8")
        result = filter_xml_by_key(
            namespace_input,
            "N001",
            output,
            large_threshold_bytes=0,
        )
        root = ET.parse(output).getroot()
        self.assertTrue(result.streaming_used)
        self.assertEqual(local_name(root.tag), "datalist")
        self.assertEqual(
            [local_name(node.tag) for node in root],
            ["data"],
        )

    def test_analyze_xml_structure_detects_tags(self) -> None:
        structure = analyze_xml_structure(self.input_path)
        self.assertEqual(structure.root_tag, "datalist")
        self.assertEqual(structure.item_tags, ("data",))
        self.assertEqual(structure.child_tag_counts, {"data": 4})
        self.assertEqual(structure.key_tags_by_item["data"], ("key", "name"))

    def test_preview_reports_counts_without_writing(self) -> None:
        preview = preview_filter(self.input_path, "A002")
        self.assertEqual((preview.total_count, preview.kept_count, preview.removed_count), (4, 2, 2))
        self.assertIn("第二筆重複 key 資料", preview.preview_xml)
        self.assertFalse((self.work_dir / "input.filtered.xml").exists())

    def test_large_preview_is_truncated(self) -> None:
        preview = preview_filter(
            self.input_path,
            "A002",
            large_threshold_bytes=0,
            large_preview_limit=1,
        )
        self.assertTrue(preview.streaming_recommended)
        self.assertTrue(preview.truncated)
        self.assertEqual(preview.kept_count, 2)

    def test_streaming_filter_produces_valid_xml(self) -> None:
        output = self.work_dir / "stream.xml"
        result = filter_xml_by_keys(
            self.input_path,
            "A001;A003",
            output,
            large_threshold_bytes=0,
        )
        root = ET.parse(output).getroot()
        self.assertTrue(result.streaming_used)
        self.assertEqual([node.findtext("key") for node in root.findall("data")], ["A001", "A003"])

    def test_inspector_reports_full_xml_for_small_file(self) -> None:
        inspection = inspect_xml(self.input_path)
        self.assertFalse(inspection.truncated)
        self.assertEqual(inspection.root_tag, "datalist")
        self.assertEqual(inspection.child_tag_counts, {"data": 4})
        self.assertIn("<key>A003</key>", inspection.full_xml)

    def test_inspector_uses_limited_display_for_large_file(self) -> None:
        inspection = inspect_xml(
            self.input_path,
            large_threshold_bytes=0,
            large_item_limit=1,
        )
        self.assertTrue(inspection.truncated)
        self.assertIn("A001", inspection.full_xml)
        self.assertNotIn("A003", inspection.full_xml)

    def test_fold_range_finder_detects_list_nodes(self) -> None:
        ranges = find_element_content_ranges(SAMPLE_XML, "data")
        self.assertEqual(len(ranges), 4)
        first_content = SAMPLE_XML[ranges[0][0] : ranges[0][1]]
        self.assertIn("<key>A001</key>", first_content)

    @patch("filter_xml.Confirm.ask", side_effect=[True])
    @patch("filter_xml.Prompt.ask")
    def test_rich_filter_form_filters_xml(self, mock_prompt, _mock_confirm) -> None:
        output = self.work_dir / "menu-result.xml"
        mock_prompt.side_effect = [
            str(self.input_path),
            "datalist",
            "data",
            "key",
            "A003",
            str(output),
        ]
        exit_code = run_filter_interactive()
        self.assertEqual(exit_code, 0)
        self.assertEqual(ET.parse(output).getroot().findtext("data/key"), "A003")

    def test_parameter_mode_requires_path_and_key_together(self) -> None:
        self.assertEqual(main([str(self.input_path)]), 2)

    @patch("menu_cli.run_filter_interactive", return_value=0)
    @patch("menu_cli.Prompt.ask", side_effect=["1", "4"])
    def test_main_menu_starts_filter(self, _mock_prompt, mock_filter) -> None:
        self.assertEqual(menu_cli.main(), 0)
        mock_filter.assert_called_once()

    @patch("menu_cli.run_inspect_interactive", return_value=0)
    @patch("menu_cli.Prompt.ask", side_effect=["2", "4"])
    def test_main_menu_starts_inspector(self, _mock_prompt, mock_inspector) -> None:
        self.assertEqual(menu_cli.main(), 0)
        mock_inspector.assert_called_once()

    @patch("menu_cli.run_gui")
    @patch("menu_cli.Prompt.ask", side_effect=["3", "4"])
    def test_main_menu_starts_gui(self, _mock_prompt, mock_gui) -> None:
        self.assertEqual(menu_cli.main(), 0)
        mock_gui.assert_called_once()

    def test_gui_module_can_be_imported_without_starting_window(self) -> None:
        self.assertTrue(hasattr(xml_filter_gui, "XmlFilterApp"))


if __name__ == "__main__":
    unittest.main()

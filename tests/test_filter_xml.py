"""filter_xml.py 的自動化測試。"""

from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from filter_xml import (  # noqa: E402
    XmlFilterError,
    filter_xml_by_key,
    main,
    run_filter_interactive,
)
from inspect_xml import inspect_xml  # noqa: E402
import menu_cli  # noqa: E402
import xml_filter_gui  # noqa: E402


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
        names = [node.findtext("name") for node in root.findall("data")]

        self.assertEqual(keys, ["A002", "A002"])
        self.assertEqual(names, ["第二筆資料", "第二筆重複 key 資料"])
        self.assertEqual(root.attrib["source"], "模擬資料")
        self.assertEqual(result.kept_count, 2)
        self.assertEqual(result.removed_count, 2)

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

        result = filter_xml_by_key(
            self.input_path,
            "A001",
            output_path,
            force=True,
        )

        self.assertEqual(result.kept_count, 1)
        self.assertEqual(ET.parse(output_path).getroot().findtext("data/key"), "A001")

    def test_reject_same_input_and_output_path(self) -> None:
        with self.assertRaisesRegex(XmlFilterError, "不可與輸入路徑相同"):
            filter_xml_by_key(
                self.input_path,
                "A001",
                self.input_path,
                force=True,
            )

    @patch("filter_xml.Confirm.ask", side_effect=[True])
    @patch("filter_xml.Prompt.ask")
    def test_rich_filter_form_filters_xml(self, mock_prompt, _mock_confirm) -> None:
        output_path = self.work_dir / "menu-result.xml"
        mock_prompt.side_effect = [
            str(self.input_path),
            "data",
            "A003",
            str(output_path),
        ]

        exit_code = run_filter_interactive()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            ET.parse(output_path).getroot().findtext("data/key"),
            "A003",
        )

    def test_parameter_mode_requires_path_and_key_together(self) -> None:
        exit_code = main([str(self.input_path)])

        self.assertEqual(exit_code, 2)

    @patch("menu_cli.run_filter_interactive", return_value=0)
    @patch("menu_cli.Prompt.ask", side_effect=["1", "4"])
    def test_main_menu_starts_selected_tool(
        self,
        _mock_prompt,
        mock_filter_form,
    ) -> None:
        exit_code = menu_cli.main()

        self.assertEqual(exit_code, 0)
        mock_filter_form.assert_called_once()

    @patch("menu_cli.run_inspect_interactive", return_value=0)
    @patch("menu_cli.Prompt.ask", side_effect=["2", "4"])
    def test_main_menu_starts_inspector(
        self,
        _mock_prompt,
        mock_inspector,
    ) -> None:
        exit_code = menu_cli.main()

        self.assertEqual(exit_code, 0)
        mock_inspector.assert_called_once()

    @patch("menu_cli.run_gui")
    @patch("menu_cli.Prompt.ask", side_effect=["3", "4"])
    def test_main_menu_starts_gui(
        self,
        _mock_prompt,
        mock_gui,
    ) -> None:
        exit_code = menu_cli.main()

        self.assertEqual(exit_code, 0)
        mock_gui.assert_called_once()

    def test_gui_module_can_be_imported_without_starting_window(self) -> None:
        self.assertTrue(hasattr(xml_filter_gui, "XmlFilterApp"))

    def test_custom_outer_list_tag_is_supported(self) -> None:
        custom_input = self.work_dir / "custom.xml"
        output_path = self.work_dir / "custom-result.xml"
        custom_input.write_text(
            "<datalist><record><key>X001</key></record>"
            "<record><key>X002</key></record></datalist>",
            encoding="utf-8",
        )

        result = filter_xml_by_key(
            custom_input,
            "X002",
            output_path,
            item_tag="record",
        )

        self.assertEqual(result.kept_count, 1)
        self.assertEqual(ET.parse(output_path).getroot().findtext("record/key"), "X002")

    def test_inspector_reports_direct_child_tags_and_full_xml(self) -> None:
        inspection = inspect_xml(self.input_path)

        self.assertEqual(inspection.root_tag, "datalist")
        self.assertEqual(inspection.child_tag_counts, {"data": 4})
        self.assertIn("<key>A001</key>", inspection.full_xml)
        self.assertIn("<key>A003</key>", inspection.full_xml)


if __name__ == "__main__":
    unittest.main()

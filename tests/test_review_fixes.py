"""2026-10-26 review 修正的回歸測試：Big5、找不到的 key、GUI 上色索引。"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import filter_xml  # noqa: E402
from inspect_xml import inspect_xml  # noqa: E402
from xml_filter_gui import text_index  # noqa: E402
from xml_service import (  # noqa: E402
    XmlFilterError,
    analyze_xml_structure,
    filter_xml_by_keys,
    parse_target_keys,
    preview_filter,
)


BIG5_XML = (
    '<?xml version="1.0" encoding="Big5"?>\n'
    "<datalist>\n"
    "    <data><key>A001</key><name>保單一</name></data>\n"
    "    <data><key>A002</key><name>保單二</name></data>\n"
    "</datalist>\n"
)


class Big5XmlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_dir = Path(tempfile.mkdtemp())
        self.input_path = self.work_dir / "big5.xml"
        self.input_path.write_bytes(BIG5_XML.encode("cp950"))

    def test_big5_xml_works_in_memory_and_streaming(self) -> None:
        structure = analyze_xml_structure(self.input_path)
        self.assertEqual(structure.child_tag_counts, {"data": 2})
        for threshold in (0, 10**9):
            with self.subTest(threshold=threshold):
                preview = preview_filter(self.input_path, "A002", large_threshold_bytes=threshold)
                self.assertEqual((preview.kept_count, preview.removed_count), (1, 1))
                self.assertIn("保單二", preview.preview_xml)
                output = self.work_dir / f"out-{threshold}.xml"
                filter_xml_by_keys(self.input_path, "A002", output, large_threshold_bytes=threshold)
                self.assertEqual(ET.parse(output).getroot().findtext("data/name"), "保單二")
                inspection = inspect_xml(self.input_path, large_threshold_bytes=threshold)
                self.assertIn("保單一", inspection.full_xml)

    def test_bytes_not_matching_declaration_is_a_filter_error(self) -> None:
        self.input_path.write_bytes(
            b'<?xml version="1.0" encoding="Big5"?>\n<datalist><data><key>\xff\xff</key></data></datalist>'
        )
        with self.assertRaises(XmlFilterError):
            preview_filter(self.input_path, "A")


class MissingKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_dir = Path(tempfile.mkdtemp())
        self.input_path = self.work_dir / "input.xml"
        self.input_path.write_text(
            "<datalist><data><key>A001</key></data><data><key>A002</key></data></datalist>",
            encoding="utf-8",
        )

    def test_full_width_and_tab_separators(self) -> None:
        self.assertEqual(parse_target_keys("A001，A002；A003\tA004"), ("A001", "A002", "A003", "A004"))

    def test_preview_reports_missing_keys(self) -> None:
        preview = preview_filter(self.input_path, "A001, A0O1")
        self.assertEqual(preview.kept_count, 1)
        self.assertEqual(preview.missing_keys, ("A0O1",))

    def test_cli_warns_about_missing_keys(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            exit_code = filter_xml.main([
                str(self.input_path), "A001,A0O1", "-o", str(self.work_dir / "out.xml"),
            ])
        self.assertEqual(exit_code, 0)
        self.assertIn("A0O1", stderr.getvalue())


class TextIndexTests(unittest.TestCase):
    def test_offsets_map_to_line_and_column(self) -> None:
        content = "<a>\n  <b/>\n</a>"
        line_starts = [0, 4, 11]
        self.assertEqual(text_index(line_starts, 0), "1.0")
        self.assertEqual(text_index(line_starts, 6), "2.2")
        self.assertEqual(text_index(line_starts, len(content)), "3.4")


if __name__ == "__main__":
    unittest.main()

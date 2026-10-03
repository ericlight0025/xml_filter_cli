"""Regression coverage for streaming memory, namespaces and output errors."""

from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import inspect_xml
import xml_service
from xml_service import XmlFilterError, filter_xml_by_keys, preview_filter


class ReviewRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_dir = Path(tempfile.mkdtemp())
        self.input_path = self.work_dir / "input.xml"
        self.input_path.write_text(
            "<datalist>" + "<data><key>A</key></data>" * 1000 + "</datalist>",
            encoding="utf-8",
        )

    def test_streaming_releases_completed_root_children(self) -> None:
        original_iterparse = ET.iterparse
        retained_counts = []

        def tracked_iterparse(*args, **kwargs):
            root = None
            for event, element in original_iterparse(*args, **kwargs):
                if event == "start" and root is None:
                    root = element
                if event == "end" and element is root:
                    retained_counts.append(len(root))
                yield event, element

        with patch.object(ET, "iterparse", side_effect=tracked_iterparse):
            xml_service.analyze_xml_structure(self.input_path)
            preview_filter(self.input_path, "A", large_threshold_bytes=0)
            filter_xml_by_keys(
                self.input_path, "A", self.work_dir / "result.xml",
                large_threshold_bytes=0,
            )
            inspect_xml.inspect_xml(self.input_path, large_threshold_bytes=0)
        self.assertEqual(retained_counts, [0] * 5)

    def test_matched_keys_are_unique_in_both_preview_modes(self) -> None:
        for threshold in (0, 10**9):
            with self.subTest(threshold=threshold):
                preview = preview_filter(
                    self.input_path, "A", large_threshold_bytes=threshold,
                )
                self.assertEqual(preview.kept_count, 1000)
                self.assertEqual(preview.matched_keys, ("A",))

    def test_streaming_root_closing_tag_survives_prefix_rebinding(self) -> None:
        self.input_path.write_text(
            '<p:datalist xmlns:p="urn:root">'
            '<p:data><p:key>A</p:key></p:data>'
            '<p:metadata xmlns:p="urn:other">info</p:metadata>'
            '</p:datalist>', encoding="utf-8",
        )
        output = self.work_dir / "namespaces.xml"
        filter_xml_by_keys(self.input_path, "A", output, large_threshold_bytes=0)
        root = ET.parse(output).getroot()
        self.assertEqual(root.tag, "{urn:root}datalist")
        self.assertEqual([child.tag for child in root],
                         ["{urn:root}data", "{urn:other}metadata"])

    def test_output_directory_errors_are_wrapped(self) -> None:
        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(XmlFilterError, "無法.*輸出"):
                filter_xml_by_keys(self.input_path, "A", self.work_dir / "result.xml")

    def test_temporary_file_errors_are_wrapped_in_both_modes(self) -> None:
        for threshold in (0, 10**9):
            with self.subTest(threshold=threshold):
                with patch.object(xml_service.tempfile, "NamedTemporaryFile",
                                  side_effect=PermissionError("denied")):
                    with self.assertRaisesRegex(XmlFilterError, "無法.*輸出"):
                        filter_xml_by_keys(
                            self.input_path, "A", self.work_dir / "result.xml",
                            large_threshold_bytes=threshold,
                        )


if __name__ == "__main__":
    unittest.main()

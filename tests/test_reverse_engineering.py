"""
Tests for HIVEBrain Reverse Engineering Subsystem (v1.0.0)
Validates:
  1. Track 1: Dynamic Web / Chrome Extension Classification & Manifest Audit
  2. Track 2: Static Local Binary Classification (Browser-Free) & REA Provenance
  3. Tool decoupling (Track 2 runs with zero browser dependencies)
"""

import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from reverse_engineering import ReverseEngineeringSubsystem

class TestReverseEngineeringSubsystem(unittest.TestCase):

    def setUp(self):
        self.subsystem = ReverseEngineeringSubsystem()
        self.ghostshot_dir = "/Users/nishant/Documents/gravity_work/GhostShot"
        self.serversctl_bin = "/Users/nishant/.local/bin/serversctl"

    def test_1_track1_extension_classification(self):
        """Validates that GhostShot is correctly classified as an extension requiring browser."""
        target = self.subsystem.classify_target(self.ghostshot_dir)
        self.assertEqual(target.target_type, "extension")
        self.assertTrue(target.requires_browser)
        self.assertIn("manifest", target.metadata)

    def test_2_track1_execution_manifest_audit(self):
        """Validates that Track 1 extracts permissions and background details from manifest.json."""
        target = self.subsystem.classify_target(self.ghostshot_dir)
        findings = self.subsystem.execute_track1_web_extension(target)
        self.assertEqual(findings["track"], "Track 1: Dynamic Web / Chrome Extension")
        self.assertTrue(findings["requires_browser"])
        self.assertIn("phase_1_manifest_audit", findings["phases"])
        self.assertIn("phase_4_devtools_profile_config", findings["phases"])
        self.assertIn("--categoryExtensions", findings["phases"]["phase_4_devtools_profile_config"]["flags"])

    def test_3_track2_binary_classification_browser_free(self):
        """Validates that local executable is classified as native/Go binary and requires NO browser."""
        if os.path.exists(self.serversctl_bin):
            target = self.subsystem.classify_target(self.serversctl_bin)
            self.assertIn(target.target_type, ["native_binary", "go_binary"])
            self.assertFalse(target.requires_browser)

    def test_4_track2_execution_static_dissection(self):
        """Validates that Track 2 dissects binary statically with zero browser dependencies."""
        if os.path.exists(self.serversctl_bin):
            target = self.subsystem.classify_target(self.serversctl_bin)
            findings = self.subsystem.execute_track2_static_binary(target)
            self.assertEqual(findings["track"], "Track 2: Static / Local Binary Dissection (Browser-Free)")
            self.assertFalse(findings["requires_browser"])
            self.assertIn("phase_1_binary_fingerprint", findings["phases"])
            self.assertIn("phase_3_craft_native_analysis", findings["phases"])

    def test_5_tool_role_definitions(self):
        """Verifies that all tool roles are clearly articulated in findings."""
        target_ext = self.subsystem.classify_target(self.ghostshot_dir)
        findings_ext = self.subsystem.execute_track1_web_extension(target_ext)
        self.assertIn("chrome_devtools_mcp", findings_ext["tool_roles"])
        self.assertIn("craft_anything", findings_ext["tool_roles"])
        self.assertIn("rea", findings_ext["tool_roles"])
        self.assertIn("graphify", findings_ext["tool_roles"])

if __name__ == "__main__":
    unittest.main()

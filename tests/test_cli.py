import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from teleop_link_diag.cli import direct_sdk_environment, proxy_report, summarize_jsonl


class ProxyDiagnosisTests(unittest.TestCase):
    def test_localhost_does_not_bypass_literal_loopback_ip(self):
        secret = "http://user:token@proxy.invalid:8080"
        report = proxy_report({"http_proxy": secret, "no_proxy": "localhost"})
        self.assertTrue(report["potential_grpc_proxy_interference"])
        self.assertNotIn(secret, json.dumps(report))

    def test_explicit_loopback_bypass_and_precedence(self):
        report = proxy_report({
            "grpc_proxy": "http://proxy.invalid:8080",
            "no_grpc_proxy": "127.0.0.1,localhost",
            "no_proxy": "localhost",
        })
        self.assertEqual(report["grpc_core_bypass_variable"], "no_grpc_proxy")
        self.assertFalse(report["potential_grpc_proxy_interference"])

    def test_sdk_environment_does_not_change_parent_mapping(self):
        original = {"http_proxy": "http://proxy.invalid", "OTHER": "keep"}
        child = direct_sdk_environment(original)
        self.assertEqual(original["http_proxy"], "http://proxy.invalid")
        self.assertNotIn("http_proxy", child)
        self.assertEqual(child["no_proxy"], "127.0.0.1,localhost")
        self.assertEqual(child["OTHER"], "keep")


class SampleDiagnosisTests(unittest.TestCase):
    def test_counts_data_separately_from_tracking_pose(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "samples.jsonl"
            path.write_text(
                '{"tracking_timestamp_ns":0,"right_controller_pose":null}\n'
                '{"tracking_timestamp_ns":12,"right_controller_pose":null}\n'
                '{"tracking_timestamp_ns":13,"right_controller_pose":[1,2,3]}\n'
                'invalid json\n',
                encoding="utf-8",
            )
            report = summarize_jsonl(path)
        self.assertEqual(report["total_rows"], 3)
        self.assertEqual(report["nonzero_timestamp_rows"], 2)
        self.assertEqual(report["non_null_pose_rows"], 1)
        self.assertEqual(report["malformed_rows"], 1)


if __name__ == "__main__":
    unittest.main()

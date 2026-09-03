"""Source-distribution metadata and the public release/support boundary."""
from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APACHE_2_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"
CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Software Development :: Version Control :: Git",
]


class PackageMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configuration = tomllib.loads(
            (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_canonical_apache_2_license_and_pep_639_metadata(self) -> None:
        license_bytes = (PROJECT_ROOT / "LICENSE").read_bytes()
        self.assertEqual(hashlib.sha256(license_bytes).hexdigest(), APACHE_2_SHA256)

        project = self.configuration["project"]
        self.assertEqual(project["license"], "Apache-2.0")
        self.assertEqual(project["license-files"], ["LICENSE"])
        self.assertFalse(any(item.startswith("License ::") for item in project["classifiers"]))
        self.assertEqual(
            self.configuration["build-system"]["requires"],
            ["setuptools>=77.0.3"],
        )

    def test_package_and_public_support_boundaries_agree(self) -> None:
        project = self.configuration["project"]
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["classifiers"], CLASSIFIERS)

        readme = " ".join((PROJECT_ROOT / "README.md").read_text(encoding="utf-8").split())
        self.assertIn("Git 2.29.0 or newer and Python 3.11 or newer are required", readme)
        self.assertIn("supported operating-system targets are Linux and macOS", readme)
        self.assertIn("Native Windows is explicitly unsupported in 0.x", readme)
        self.assertIn("Apache License, Version 2.0", readme)


if __name__ == "__main__":
    unittest.main()

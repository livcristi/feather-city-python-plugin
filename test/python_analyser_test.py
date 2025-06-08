import os
import tempfile
import unittest
from pathlib import Path

from visualiser.schema.data import ProjectData, FileNode, FolderNode

from python_analyser_plugin.python_analyser import PythonAnalyser


class TestPythonAnalyser(unittest.TestCase):
    """Unit tests for PythonAnalyser class."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyser = PythonAnalyser()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyse_nonexistent_directory(self):
        """Test that analyse raises ValueError for non-existent directory."""
        with self.assertRaises(ValueError) as context:
            self.analyser.analyse("/non/existent/path")

    def test_analyse_single_python_file(self):
        """Test analysis of a directory with a single Python file."""
        # Create a simple Python file
        python_content = '''#!/usr/bin/env python3
"""
This is a test module.
Multi-line docstring.
"""

def hello_world():
    """Say hello to the world."""
    print("Hello, World!")  # This is a comment
    return "Hello"

class TestClass:
    """A simple test class."""

    def method_one(self):
        # Another comment
        pass

    async def async_method(self):
        return True
'''

        test_file = Path(self.temp_dir) / "test_module.py"
        test_file.write_text(python_content, encoding='utf-8')

        # Analyse the directory
        result = self.analyser.analyse(self.temp_dir)

        # Assertions
        self.assertIsInstance(result, ProjectData)
        self.assertEqual(result.title, os.path.basename(self.temp_dir))
        self.assertEqual(len(result.metrics), 4)  # loc, cloc, nom, tloc

        # Check hierarchy
        self.assertIsInstance(result.hierarchy, FolderNode)
        self.assertEqual(len(result.hierarchy.children), 1)

        file_node = result.hierarchy.children[0]
        self.assertIsInstance(file_node, FileNode)
        self.assertEqual(file_node.name, "test_module.py")
        self.assertEqual(file_node.language, "python")

        # Check metrics (approximate values)
        metrics = file_node.metrics
        self.assertGreater(metrics["tloc"], 15)
        self.assertGreater(metrics["loc"], 7)
        self.assertGreater(metrics["cloc"], 7)
        self.assertEqual(metrics["nom"], 3)  # 3 functions/methods (hello_world, method_one, async_method)

    def test_analyse_with_exclusions(self):
        """Test analysis with file and directory exclusions."""
        # Create directory structure
        src_dir = Path(self.temp_dir) / "src"
        test_dir = Path(self.temp_dir) / "__pycache__"
        src_dir.mkdir()
        test_dir.mkdir()

        # Create files
        (src_dir / "main.py").write_text("def main(): pass", encoding='utf-8')
        (src_dir / "test_file.py").write_text("def test(): pass", encoding='utf-8')
        (test_dir / "cache.pyc").write_text("compiled code", encoding='utf-8')

        # Analyse with exclusions
        result = self.analyser.analyse(
            self.temp_dir,
            exclude_directories="__pycache__",
            exclude_filenames="test_*.py"
        )

        # Should only have src directory
        self.assertEqual(len(result.hierarchy.children), 1)
        src_node = result.hierarchy.children[0]
        self.assertEqual(src_node.name, "src")

        # Should only have main.py (test_file.py excluded)
        self.assertEqual(len(src_node.children), 1)
        self.assertEqual(src_node.children[0].name, "main.py")

    def test_analyse_empty_directory(self):
        """Test analysis of an empty directory."""
        result = self.analyser.analyse(self.temp_dir)

        self.assertIsInstance(result, ProjectData)
        self.assertEqual(len(result.hierarchy.children), 0)

    def test_analyse_with_custom_metrics(self):
        """Test analysis with custom metric selection."""
        # Create a simple Python file
        test_file = Path(self.temp_dir) / "simple.py"
        test_file.write_text("def func(): pass", encoding='utf-8')

        # Analyse with only specific metrics
        result = self.analyser.analyse(self.temp_dir, metrics="loc,nom")

        # Should only have 2 metrics
        self.assertEqual(len(result.metrics), 2)
        metric_ids = [m.id for m in result.metrics]
        self.assertIn("loc", metric_ids)
        self.assertIn("nom", metric_ids)
        self.assertNotIn("cloc", metric_ids)
        self.assertNotIn("tloc", metric_ids)

    def test_analyse_invalid_metrics(self):
        """Test that invalid metrics raise ValueError."""
        test_file = Path(self.temp_dir) / "simple.py"
        test_file.write_text("def func(): pass", encoding='utf-8')

        with self.assertRaises(ValueError) as context:
            self.analyser.analyse(self.temp_dir, metrics="invalid,nonexistent")

    def test_analyse_nested_directory_structure(self):
        """Test analysis of nested directory structure."""
        # Create nested structure
        src_dir = Path(self.temp_dir) / "src"
        utils_dir = src_dir / "utils"
        src_dir.mkdir()
        utils_dir.mkdir()

        # Create files at different levels
        (src_dir / "main.py").write_text("def main(): pass", encoding='utf-8')
        (utils_dir / "helper.py").write_text("def helper(): pass", encoding='utf-8')

        result = self.analyser.analyse(self.temp_dir)

        # Check structure
        self.assertEqual(len(result.hierarchy.children), 1)
        src_node = result.hierarchy.children[0]
        self.assertEqual(src_node.name, "src")
        self.assertEqual(len(src_node.children), 2)  # main.py and utils/

        # Find utils directory
        utils_node = next(child for child in src_node.children if child.name == "utils")
        self.assertEqual(len(utils_node.children), 1)
        self.assertEqual(utils_node.children[0].name, "helper.py")

    def test_analyse_with_syntax_error_file(self):
        """Test analysis handles files with syntax errors gracefully."""
        # Create a Python file with syntax error
        bad_file = Path(self.temp_dir) / "bad_syntax.py"
        bad_file.write_text("def incomplete_function(\n    # Missing closing parenthesis", encoding='utf-8')

        # Should not raise exception, but handle gracefully
        result = self.analyser.analyse(self.temp_dir)

        self.assertIsInstance(result, ProjectData)
        self.assertEqual(len(result.hierarchy.children), 1)
        file_node = result.hierarchy.children[0]
        self.assertEqual(file_node.name, "bad_syntax.py")
        # Should have some metrics even if AST parsing failed
        self.assertIn("tloc", file_node.metrics)
        self.assertEqual(file_node.metrics["nom"], 0)

    def test_analyse_non_python_files_ignored(self):
        """Test that non-Python files are ignored."""
        # Create various file types
        (Path(self.temp_dir) / "readme.txt").write_text("Not Python", encoding='utf-8')
        (Path(self.temp_dir) / "config.json").write_text('{"key": "value"}', encoding='utf-8')
        (Path(self.temp_dir) / "script.py").write_text("def func(): pass", encoding='utf-8')

        result = self.analyser.analyse(self.temp_dir)

        # Should only have the Python file
        self.assertEqual(len(result.hierarchy.children), 1)
        self.assertEqual(result.hierarchy.children[0].name, "script.py")

    def test_custom_title_and_description(self):
        """Test analysis with custom title and description."""
        test_file = Path(self.temp_dir) / "simple.py"
        test_file.write_text("def func(): pass", encoding='utf-8')

        result = self.analyser.analyse(
            self.temp_dir,
            title="Custom Project",
            description="Custom description"
        )

        self.assertEqual(result.title, "Custom Project")
        self.assertEqual(result.description, "Custom description")


if __name__ == '__main__':
    unittest.main()
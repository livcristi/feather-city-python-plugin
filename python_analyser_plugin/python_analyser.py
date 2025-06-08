import argparse
import ast
import fnmatch
import os
from datetime import datetime
from typing import Dict, Optional, override, List
import logging

from visualiser.analyser.base import Analyser
from visualiser.schema.data import (
    ProjectData,
    MetricDef,
    HierarchyNode,
    FolderNode,
    FileNode,
)

logger: logging.Logger = logging.getLogger(__name__)


class PythonAnalyser(Analyser):
    """
    Python code analyser that counts lines of code, comments, and methods.
    """

    @override
    def analyse(
        self,
        input_dir: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs,
    ) -> ProjectData:
        """
        Analyse Python files in the input directory and returns the analysis result as a ProjectData object.

        Args:
            input_dir: Directory to analyse
            title: Project title
            description: Project description
            **kwargs: Can include:
                - exclude_directories: Comma-separated list of directory names to exclude
                - exclude_filenames: Comma-separated list of filename patterns to exclude
                - metrics: Comma-separated string of metric IDs to compute

        Raises:
            ValueError: if the input directory does not exist, the provided metrics are invalid
        """
        logger.info("Starting analysis for directory: %s", input_dir)

        if not os.path.exists(input_dir):
            logger.error("Input directory does not exist: %s", input_dir)
            raise ValueError(f"Input directory does not exist: {input_dir}")

        # Parse kwargs for extra parameters
        exclude_dirs_csv: str = kwargs.get("exclude_directories", "")
        exclude_files_csv: str = kwargs.get("exclude_filenames", "")
        requested_metrics_csv: str = kwargs.get("metrics", "")

        exclude_dirs_list: List[str] = PythonAnalyser.__parse_csv_param(
            exclude_dirs_csv
        )
        exclude_files_list: List[str] = PythonAnalyser.__parse_csv_param(
            exclude_files_csv
        )
        requested_metric_ids: List[str] = PythonAnalyser.__parse_csv_param(
            requested_metrics_csv
        )

        logger.debug("Exclusion directories: %s", exclude_dirs_list)
        logger.debug("Exclusion filename patterns: %s", exclude_files_list)
        logger.debug("Requested metrics: %s", requested_metric_ids)

        all_metrics = {
            "loc": MetricDef(
                id="loc",
                name="Lines of Code",
                description="Number of non-empty, non-comment lines",
                type="number",
                aggregate="sum",
                propagate=True,
            ),
            "cloc": MetricDef(
                id="cloc",
                name="Comment Lines",
                description="Number of comment lines",
                type="number",
                aggregate="sum",
                propagate=True,
            ),
            "nom": MetricDef(
                id="nom",
                name="Method Count",
                description="Number of methods and functions",
                type="number",
                aggregate="sum",
                propagate=True,
            ),
            "tloc": MetricDef(
                id="tloc",
                name="Total Lines",
                description="Total number of lines in file",
                type="number",
                aggregate="sum",
                propagate=True,
            ),
        }

        metrics_to_compute: List[MetricDef]
        if requested_metric_ids:
            metrics_to_compute = [
                all_metrics[metric_id]
                for metric_id in requested_metric_ids
                if metric_id in all_metrics
            ]
            if not metrics_to_compute:
                logger.warning(
                    "No valid metrics found in requested list: %s. Available: %s",
                    requested_metric_ids,
                    list(all_metrics.keys()),
                )
                raise ValueError(f"No valid metrics found in: {requested_metric_ids}")
        else:
            metrics_to_compute = list(all_metrics.values())

        hierarchy = PythonAnalyser.__build_hierarchy(
            input_dir, input_dir, exclude_dirs_list, exclude_files_list
        )

        project_title: str = title or os.path.basename(os.path.abspath(input_dir))
        project_description: str = description or f"Analysis of {project_title}"
        project_data: ProjectData = ProjectData(
            version="1.0",
            title=project_title,
            description=project_description,
            metrics=metrics_to_compute,
            hierarchy=hierarchy,
        )
        logger.info("Analysis completed for project: %s", project_data.title)
        return project_data

    @staticmethod
    def __parse_csv_param(param: str) -> List[str]:
        """
        Parse comma-separated parameter into list, handling empty strings.
        """
        if not param or not param.strip():
            return []
        return [item.strip() for item in param.split(",") if item.strip()]

    @staticmethod
    def __should_exclude_directory(dir_name: str, exclude_dirs_list: List[str]) -> bool:
        """
        Check if directory should be excluded based on the provided list.
        """
        if not exclude_dirs_list:
            return False
        is_excluded: bool = dir_name in exclude_dirs_list
        if is_excluded:
            logger.debug("Excluding directory by name: %s", dir_name)
        return is_excluded

    @staticmethod
    def __should_exclude_file(file_path: str, exclude_files_list: List[str]) -> bool:
        """
        Check if file should be excluded based on exclude_filenames filter.
        """
        if not exclude_files_list:
            return False

        file_name: str = os.path.basename(file_path)
        for pattern in exclude_files_list:
            if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(
                file_path, pattern
            ):
                logger.debug(
                    "Excluding file '%s' due to pattern '%s'", file_path, pattern
                )
                return True
        return False

    @staticmethod
    def __build_hierarchy(
        current_path: str,
        root_path: str,
        exclude_dirs: List[str],
        exclude_files: List[str],
    ) -> HierarchyNode:
        """
        Recursively build the project hierarchy.
        This method adheres to the original logic of returning HierarchyNode, and how children are processed and added.
        """
        rel_name: str = os.path.basename(current_path)

        # If current_path is a file, analyse it directly
        if os.path.isfile(current_path):
            return PythonAnalyser.__analyse_file(current_path, rel_name)

        # current_path is a directory
        children: List[HierarchyNode] = []
        try:
            for item_name in sorted(os.listdir(current_path)):
                item_path: str = os.path.join(current_path, item_name)

                # Skip hidden files and directories
                if item_name.startswith("."):
                    logger.debug("Skipping hidden item: %s", item_path)
                    continue

                if os.path.isdir(item_path):
                    if PythonAnalyser.__should_exclude_directory(
                        item_name, exclude_dirs
                    ):
                        continue

                    child_node: FolderNode = PythonAnalyser.__build_hierarchy(
                        item_path, root_path, exclude_dirs, exclude_files
                    )
                    if child_node.type == "folder" and child_node.children:
                        children.append(child_node)

                elif os.path.isfile(item_path):
                    # Check for exclusion before attempting to build hierarchy for the file
                    if PythonAnalyser.__should_exclude_file(item_path, exclude_files):
                        continue

                    if item_name.endswith(".py"):
                        # Recursively call _build_hierarchy, which will then call _analyse_file
                        file_child_node: FileNode = PythonAnalyser.__build_hierarchy(
                            item_path, root_path, exclude_dirs, exclude_files
                        )
                        children.append(file_child_node)

        except PermissionError:
            logger.warning(
                "Permission denied for directory: %s. Skipping.", current_path
            )
        except Exception as exception:
            logger.warning(
                "Error processing directory %s: %s. Skipping.",
                current_path,
                exception,
                exc_info=True,
            )

        return FolderNode(name=rel_name, type="folder", children=children)

    @staticmethod
    def __analyse_file(file_path: str, file_name: str) -> FileNode:
        """
        Analyse a single file. If not a Python file or an error was raised, returns FileNode with zero/default metrics.
        """
        logger.debug("Analyzing file: %s", file_path)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file_data:
                content = file_data.read()

            last_mod_time: str = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).isoformat()

            # Calculate metrics
            metrics_data: Dict[str, float] = PythonAnalyser.__calculate_metrics(content)

            logger.debug("File analysis completed for: %s", file_path)
            return FileNode(
                name=file_name,
                type="file",
                language="python",
                lastModified=last_mod_time,
                metrics=metrics_data,
                uses=[],
                usedBy=[],
            )
        except Exception as exception:
            logger.warning(
                "Failed to analyse file %s: %s", file_path, exception, exc_info=True
            )
            # Return a file node with zero metrics
            return FileNode(
                name=file_name,
                type="file",
                language="python",
                lastModified=datetime.now().isoformat(),
                metrics={"loc": 0, "cloc": 0, "nom": 0, "tloc": 0,},
                uses=[],
                usedBy=[],
            )

    @staticmethod
    def __calculate_metrics(content: str) -> Dict[str, float]:
        """
        Calculate metrics (lines of code, lines of comments, number of methods, total lines) for Python code content.
        """
        lines: list[str] = content.split("\n")
        total_lines: int = len(lines)
        comment_lines_count: int = 0
        code_lines_count: int = 0
        method_cnt: int = 0

        in_multiline_string: bool = False
        multiline_quote: Optional[str] = None

        for line in lines:
            stripped: str = line.strip()

            if not in_multiline_string:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    multiline_quote = stripped[:3]
                    if stripped.count(multiline_quote) == 1:
                        in_multiline_string = True
                        comment_lines_count += 1
                        continue
                    if stripped.count(multiline_quote) >= 2:
                        comment_lines_count += 1
                        continue
            else:
                comment_lines_count += 1
                if multiline_quote in stripped:
                    in_multiline_string = False
                    multiline_quote = None
                continue

            if stripped.startswith("#"):
                comment_lines_count += 1
            elif stripped and not in_multiline_string:
                code_lines_count += 1

        try:
            tree: ast.AST = ast.parse(content)
            method_cnt = PythonAnalyser.__count_functions_and_methods(tree)
        except SyntaxError as syntax_error:
            # Fallback if AST parsing fails
            logger.debug(
                "AST parsing failed for content (likely not Python or syntax error): %s. Using simple def count.",
                syntax_error,
            )
            for line in lines:
                stripped: str = line.strip()
                if stripped.startswith("def ") and stripped.endswith(":"):
                    method_cnt += 1

        return {
            "loc": float(code_lines_count),
            "cloc": float(comment_lines_count),
            "nom": float(method_cnt),
            "tloc": float(total_lines),
        }

    @staticmethod
    def __count_functions_and_methods(node: ast.AST) -> int:
        """
        Recursively count function and method definitions in the Python AST.
        """
        count: int = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                count += 1
        return count

    @classmethod
    def get_cli_parser(cls) -> argparse.ArgumentParser:
        """
        Return an ArgumentParser configured for Python analysis.
        """
        parser = argparse.ArgumentParser(
            description="Analyse Python projects for code metrics"
        )
        parser.add_argument(
            "--metrics",
            type=str,
            default="loc,cloc,nom,tloc",  # Default to all common metrics
            help="Comma-separated list of metric IDs to compute (e.g., loc,nom). "
            "Available: loc, cloc, nom, tloc.",
        )
        parser.add_argument(
            "--exclude-directories",
            type=str,
            default="__pycache__,.git,.idea,node_modules,.pytest_cache,venv,.venv,env,build,dist,docs",
            help="Comma-separated list of directory names to exclude (e.g., venv,build,dist).",
        )
        parser.add_argument(
            "--exclude-filenames",
            type=str,
            default="*.test.py,*.spec.py,setup.py,*.tmp",
            help="Comma-separated list of filename patterns to exclude (e.g., '*.log,*.tmp'). Supports fnmatch.",
        )
        return parser


if __name__ == "__main__":
    analyser = PythonAnalyser()
    print(analyser.analyse(r"D:\MasterThesis\MasterThesis").model_dump_json())

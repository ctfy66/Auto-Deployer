import tempfile
import unittest
from pathlib import Path

from auto_deployer.analyzer import RepositoryAnalyzer
from auto_deployer.workspace import WorkspaceContext


class AnalyzerTests(unittest.TestCase):
    def test_detects_languages_and_hints(self) -> None:
        analyzer = RepositoryAnalyzer()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            source_dir = run_dir / "source"
            source_dir.mkdir(parents=True)
            (source_dir / "package.json").write_text("{}", encoding="utf-8")
            (source_dir / "Dockerfile").write_text("FROM node", encoding="utf-8")

            context = WorkspaceContext(
                repo_url="https://github.com/example/project.git",
                root=run_dir.parent,
                run_dir=run_dir,
                source_dir=source_dir,
                metadata_file=run_dir / "metadata.json",
                run_id="test",
            )
            insights = analyzer.analyze(context)

            self.assertIn("node", insights.languages)
            self.assertIn("dockerfile-present", insights.deployment_hints)
            self.assertTrue(insights.detected_files["package.json"])
            self.assertTrue(insights.detected_files["Dockerfile"])


if __name__ == "__main__":
    unittest.main()

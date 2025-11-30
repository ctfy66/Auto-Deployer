import json
import tempfile
import unittest
from pathlib import Path

from auto_deployer.workspace import WorkspaceManager


class WorkspaceManagerTests(unittest.TestCase):
    def test_prepare_creates_directory_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = WorkspaceManager(root)
            ctx = manager.prepare("https://github.com/example/project.git")

            self.assertTrue(ctx.run_dir.exists())
            self.assertTrue(ctx.source_dir.exists())
            self.assertTrue(ctx.metadata_file.exists())

            metadata = json.loads(ctx.metadata_file.read_text(encoding="utf-8"))
            self.assertEqual(metadata["repo_url"], "https://github.com/example/project.git")
            self.assertIn("run_id", metadata)
            self.assertEqual(metadata["source_dir"], str(ctx.source_dir))

    def test_cleanup_removes_directory_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = WorkspaceManager(Path(tmp))
            ctx = manager.prepare("https://github.com/example/project.git")
            (ctx.source_dir / "dummy.txt").write_text("hello", encoding="utf-8")

            manager.cleanup(ctx, delete_repo=True)
            self.assertFalse(ctx.run_dir.exists())


if __name__ == "__main__":
    unittest.main()

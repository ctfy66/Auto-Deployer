import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from auto_deployer.gitops import GitRepositoryManager


def _git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


class GitRepositoryManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        if not _git_available():
            self.skipTest("git binary not found")

    def test_clone_and_update_local_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            origin.mkdir()
            _run_git(["init", "--initial-branch=main"], origin)
            _run_git(["config", "user.email", "bot@example.com"], origin)
            _run_git(["config", "user.name", "Auto Deployer"], origin)
            (origin / "README.md").write_text("v1", encoding="utf-8")
            _run_git(["add", "README.md"], origin)
            _run_git(["commit", "-m", "initial"], origin)

            manager = GitRepositoryManager()
            target = root / "checkout"
            result = manager.clone_or_update(str(origin), target)
            self.assertTrue((target / "README.md").exists())
            self.assertEqual(len(result.commit_sha), 40)

            # Make a new commit in origin and ensure pull updates checkout
            (origin / "README.md").write_text("v2", encoding="utf-8")
            _run_git(["add", "README.md"], origin)
            _run_git(["commit", "-m", "update"], origin)

            result = manager.clone_or_update(str(origin), target)
            self.assertEqual((target / "README.md").read_text(encoding="utf-8"), "v2")
            self.assertEqual(len(result.commit_sha), 40)


if __name__ == "__main__":
    unittest.main()

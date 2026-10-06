import importlib.util
import os
import subprocess
import tempfile
import unittest

HOOK_PATH = os.path.join(os.path.dirname(__file__), "..", "guard-default-branch-push.py")
spec = importlib.util.spec_from_file_location("guard", HOOK_PATH)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def git(cwd, *args):
    subprocess.run(
        ["git", "-C", cwd, "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        check=True,
        capture_output=True,
    )


class GuardDefaultBranchPushTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        remote = os.path.join(cls.tmp.name, "remote.git")
        cls.repo = os.path.join(cls.tmp.name, "repo")
        cls.outside = os.path.join(cls.tmp.name, "outside")
        os.makedirs(cls.outside)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", remote], check=True)
        subprocess.run(["git", "init", "-q", "-b", "master", cls.repo], check=True)
        git(cls.repo, "commit", "-q", "--allow-empty", "-m", "init")
        git(cls.repo, "remote", "add", "origin", remote)
        git(cls.repo, "push", "-q", "-u", "origin", "master")
        git(cls.repo, "remote", "set-head", "origin", "master")
        git(cls.repo, "push", "-q", "origin", "master:feature")
        git(cls.repo, "fetch", "-q")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def checkout(self, branch):
        git(self.repo, "checkout", "-q", branch)

    def on_master(self):
        self.checkout("master")

    def on_feature(self):
        git(self.repo, "checkout", "-q", "-B", "feature", "--track", "origin/feature")

    def asks(self, command, cwd=None):
        return guard.evaluate(command, cwd or self.repo) is not None

    def test_bare_push_on_default_branch_asks(self):
        self.on_master()
        self.assertTrue(self.asks("git push"))

    def test_bare_push_on_feature_branch_passes(self):
        self.on_feature()
        self.assertFalse(self.asks("git push"))

    def test_push_with_remote_only_on_default_branch_asks(self):
        self.on_master()
        self.assertTrue(self.asks("git push origin"))

    def test_push_with_redirect_does_not_hide_current_branch(self):
        self.on_master()
        self.assertTrue(self.asks("git push origin 2>&1"))
        self.on_feature()
        self.assertFalse(self.asks("git push origin 2>&1"))

    def test_feature_branch_push_to_default_refspec_asks(self):
        self.on_feature()
        self.assertTrue(self.asks("git push origin HEAD:master"))
        self.assertTrue(self.asks("git push origin feature:refs/heads/master"))
        self.assertTrue(self.asks("git push origin master"))

    def test_feature_branch_push_to_own_name_passes(self):
        self.on_feature()
        self.assertFalse(self.asks("git push -u origin feature"))
        self.assertFalse(self.asks("git push origin HEAD"))

    def test_delete_default_branch_asks(self):
        self.on_feature()
        self.assertTrue(self.asks("git push origin --delete master"))
        self.assertTrue(self.asks("git push origin :master"))

    def test_all_and_mirror_ask(self):
        self.on_feature()
        self.assertTrue(self.asks("git push --all"))
        self.assertTrue(self.asks("git push --mirror origin"))

    def test_force_with_plus_refspec_to_default_asks(self):
        self.on_feature()
        self.assertTrue(self.asks("git push origin +feature:master"))

    def test_push_inside_compound_command_asks(self):
        self.on_master()
        self.assertTrue(self.asks('git commit -m "x" && git push'))

    def test_cd_before_push_uses_that_directory(self):
        self.on_master()
        self.assertTrue(self.asks(f"cd {self.repo} && git push", cwd=self.outside))

    def test_git_dash_c_uses_that_directory(self):
        self.on_master()
        self.assertTrue(self.asks(f"git -C {self.repo} push", cwd=self.outside))

    def test_env_prefix_is_ignored(self):
        self.on_master()
        self.assertTrue(self.asks("GIT_SSH_COMMAND=ssh git push"))

    def test_non_push_commands_pass(self):
        self.on_master()
        self.assertFalse(self.asks("git status"))
        self.assertFalse(self.asks('echo "git push"'))
        self.assertFalse(self.asks('git commit -m "docs: git push の説明"'))

    def test_outside_repository_passes(self):
        self.assertFalse(self.asks("git push", cwd=self.outside))

    def test_unparsable_command_mentioning_push_asks(self):
        self.on_feature()
        self.assertTrue(self.asks("git push origin 'unterminated"))


if __name__ == "__main__":
    unittest.main()

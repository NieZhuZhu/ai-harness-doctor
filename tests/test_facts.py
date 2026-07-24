import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import facts  # noqa: E402


class IterCodeTokensTests(unittest.TestCase):
    def test_yields_fenced_commands_and_inline_spans(self):
        text = "Run `npm test` first.\n```bash\nnpm run build\n```\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertIn("npm test", tokens)
        self.assertIn("npm run build", tokens)

    def test_skips_shell_comment_lines_inside_fence(self):
        text = "```bash\n# make sure the tests pass\nnpm run build\n```\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["npm run build"])

    def test_backticks_inside_fenced_comment_do_not_leak_tokens(self):
        # A shell comment inside a fence is skipped by the CORR-02 guard; the
        # inline-backtick regex must not leak substrings out of it.
        text = (
            "```bash\n"
            "# see `config.yaml` for details\n"
            "npm run build\n"
            "```\n"
        )
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertNotIn("config.yaml", tokens)
        self.assertEqual(tokens, ["npm run build"])

    def test_command_substitution_backticks_not_split_into_extra_tokens(self):
        # Literal backticks inside a fenced command line are command
        # substitution, not Markdown inline spans; the whole line is the token.
        text = "```bash\nRELEASE=`date +%s` npm publish\n```\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["RELEASE=`date +%s` npm publish"])

    def test_inline_spans_still_scanned_outside_fences(self):
        text = "Prefer `pnpm install` over `npm install`.\n"
        tokens = [tok for _lineno, tok in facts.iter_code_tokens(text)]
        self.assertEqual(tokens, ["pnpm install", "npm install"])


if __name__ == "__main__":
    unittest.main()

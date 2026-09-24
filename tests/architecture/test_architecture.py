import subprocess

def test_architecture_boundaries():
    """
    Runs import-linter to mechanically prove that the LLM extraction layer
    never imports any decision, rules, or scoring modules (NFR-04).
    """
    result = subprocess.run(
        ["lint-imports"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Architecture violation detected:\n{result.stdout}"

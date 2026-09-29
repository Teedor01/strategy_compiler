import ast
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent / "strategy_compiler"

MUST_NOT_IMPORT_LLM = ["evaluator.py", "resolver.py", "receipt.py", "envelope.py", "ryo_client.py", "schema.py"]


def _imported_module_names(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_evaluator_resolver_receipt_never_import_llm():
    for filename in MUST_NOT_IMPORT_LLM:
        imports = _imported_module_names(PACKAGE_DIR / filename)
        llm_imports = {m for m in imports if m == "llm" or m.endswith(".llm")}
        assert not llm_imports, f"{filename} imports the LLM module ({llm_imports}) -- boundary violation"


def test_llm_module_is_imported_by_exactly_the_expected_wiring_points():
    """Not a hard requirement that this list never grows -- but a change to
    it should be a deliberate, visible diff in this test, not something
    that happens silently.
    """
    expected_importers = {"cli.py", "compiler.py", "decide.py", "fixtures.py", "skill.py"}
    actual_importers = set()
    for py_file in PACKAGE_DIR.glob("*.py"):
        imports = _imported_module_names(py_file)
        if any(m == "llm" or m.endswith(".llm") for m in imports):
            actual_importers.add(py_file.name)
    assert actual_importers == expected_importers


def test_decide_passes_llm_only_into_compile_strategy():
    """A slightly stronger check than the import check above: decide.py is
    allowed to import llm.py (for the type hint), but the `llm` parameter
    itself must only ever be passed into compile_strategy -- never into
    resolver.resolve or evaluate_strategy.
    """
    source = (PACKAGE_DIR / "decide.py").read_text()
    tree = ast.parse(source)
    calls_with_llm_arg = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            arg_names = {kw.arg for kw in node.keywords} | {
                getattr(a, "id", None) for a in node.args if isinstance(a, ast.Name)
            }
            if "llm" in arg_names:
                calls_with_llm_arg.append(func_name)
    assert calls_with_llm_arg == ["compile_strategy"]

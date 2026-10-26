"""Static project checks: standard library only, no network, no database.

Run from backend/:   python -m scripts.static_checks

They catch problems that unit tests cannot see when the real libraries are not installed:
broken imports, circular imports, settings missing from .env.example, leaked secrets,
unsafe logging, unsafe SQL. They are STATIC analysis: they do NOT prove the code works
(the test suite does that) and they use simple rules, so they can have false positives.
"""
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
CODE_DIRS = ("app", "tests", "scripts")
SECRET_ACCESS_ALLOWED = {"app/core/config.py", "app/core/reviewer_auth.py", "app/db/database.py", "app/services/gemini_client.py"}
SETTINGS_WITHOUT_ENV = {"app_name", "app_version"}  # fixed labels, not meant to be configured
LOG_METHODS = {"debug", "info", "warning", "error", "critical", "exception"}
BAD_LOG_NAMES = {"exc", "e", "err", "error", "ex"}
SENSITIVE_NAMES = {"text", "original_text", "prompt", "api_key", "password", "database_url", "payload", "raw", "output"}
PLACEHOLDER_PASSWORDS = {"password", "change_me_local_only", "your_password"}


@dataclass
class Check:
    name: str
    problems: list = field(default_factory=list)
    info: list = field(default_factory=list)

    @property
    def passed(self):
        return not self.problems


def _py_files(dirs=CODE_DIRS):
    for d in dirs:
        for p in sorted((BACKEND / d).rglob("*.py")):
            if "__pycache__" not in p.parts:
                yield p


def _rel(path):
    return path.relative_to(BACKEND).as_posix()


def _module_path(modname):
    base = BACKEND / modname.replace(".", "/")
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _is_type_checking(test):
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _module_level(stmts, keep):
    """Yield module-level statements of the wanted kinds, skipping `if TYPE_CHECKING:` bodies."""
    for n in stmts:
        if isinstance(n, keep):
            yield n
        if isinstance(n, ast.If):
            if not _is_type_checking(n.test):
                yield from _module_level(n.body, keep)
            yield from _module_level(n.orelse, keep)
        elif isinstance(n, ast.Try):
            for block in (n.body, n.orelse, n.finalbody, *[h.body for h in n.handlers]):
                yield from _module_level(block, keep)
        elif isinstance(n, ast.With):
            yield from _module_level(n.body, keep)


def _defined_names(path):
    names = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for n in _module_level(tree.body, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign,
                                       ast.AnnAssign, ast.Import, ast.ImportFrom, ast.For)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            names.add(n.target.id)
        elif isinstance(n, ast.Import):
            for a in n.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                names.add(a.asname or a.name)
        elif isinstance(n, ast.For):
            for sub in ast.walk(n.target):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


def check_compile():
    c = Check("every Python file compiles")
    count = 0
    for p in _py_files():
        count += 1
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")  # writes nothing
        except SyntaxError as exc:
            c.problems.append("%s:%s: %s" % (_rel(p), exc.lineno, exc.msg))
    c.info.append("%d files" % count)
    return c


def check_imports_resolve():
    c = Check("every project import resolves to a real module and name")
    roots = tuple(CODE_DIRS)
    cache = {}
    for p in _py_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.split(".")[0] in roots:
                target = _module_path(node.module)
                if target is None:
                    c.problems.append("%s:%d: module '%s' not found" % (_rel(p), node.lineno, node.module))
                    continue
                if target not in cache:
                    cache[target] = _defined_names(target)
                for a in node.names:
                    if a.name == "*" or a.name in cache[target]:
                        continue
                    if _module_path(node.module + "." + a.name) is not None:
                        continue
                    c.problems.append("%s:%d: '%s' is not defined in %s" % (_rel(p), node.lineno, a.name, node.module))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in roots and _module_path(a.name) is None:
                        c.problems.append("%s:%d: module '%s' not found" % (_rel(p), node.lineno, a.name))
    return c


def check_no_import_cycles():
    c = Check("no circular imports among app modules (module-level imports only)")
    graph = {}
    for p in _py_files(("app",)):
        mod = _rel(p)[:-3].replace("/", ".")
        mod = mod[: -len(".__init__")] if mod.endswith(".__init__") else mod
        tree = ast.parse(p.read_text(encoding="utf-8"))
        edges = set()
        for n in _module_level(tree.body, (ast.Import, ast.ImportFrom)):
            if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module and n.module.startswith("app"):
                edges.add(n.module)
                for a in n.names:
                    if _module_path(n.module + "." + a.name) is not None:
                        edges.add(n.module + "." + a.name)
            elif isinstance(n, ast.Import):
                edges.update(a.name for a in n.names if a.name.startswith("app"))
        graph[mod] = {e for e in edges if _module_path(e) is not None and e != mod}

    state, stack = {}, []

    def dfs(node):
        state[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if state.get(nxt) == 1:
                c.problems.append("cycle: " + " -> ".join(stack[stack.index(nxt):] + [nxt]))
            elif nxt not in state and nxt in graph:
                dfs(nxt)
        stack.pop()
        state[node] = 2

    for m in sorted(graph):
        if m not in state:
            dfs(m)
    c.info.append("%d modules" % len(graph))
    return c


def check_env_matches_settings():
    c = Check("every setting is documented in .env.example, and nothing undocumented is listed")
    tree = ast.parse((BACKEND / "app/core/config.py").read_text(encoding="utf-8"))
    fields = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == "Settings":
            fields = {s.target.id for s in n.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)}
    wanted = {f.upper() for f in fields - SETTINGS_WITHOUT_ENV}
    listed = set(re.findall(r"^\s*#?\s*([A-Z][A-Z0-9_]*)=", (BACKEND / ".env.example").read_text(encoding="utf-8"), re.M))
    for missing in sorted(wanted - listed):
        c.problems.append("setting %s is missing from .env.example" % missing)
    for extra in sorted(listed - wanted):
        c.problems.append(".env.example lists %s, which is not a setting" % extra)
    c.info.append("%d settings" % len(wanted))
    return c


def _scan_files():
    roots = [BACKEND / d for d in ("app", "tests", "scripts", "docs", "data/seed", "data/eval")]
    singles = [BACKEND / "README.md", BACKEND / ".env.example", BACKEND.parent / "docker-compose.yml", BACKEND.parent / "README.md"]
    for r in roots:
        if r.is_dir():
            for p in sorted(r.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md", ".json", ".txt", ".yml", ".ini", ".example"}:
                    yield p
    for s in singles:
        if s.is_file():
            yield s


def check_no_secrets_committed():
    c = Check("no real-looking secrets in source, docs, data or examples")
    google_key = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
    private_key = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
    url_pw = re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^:\s/]+:([^@\s]+)@")
    literal = re.compile(r"""(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["'][A-Za-z0-9_\-]{20,}["']""")
    for p in _scan_files():
        text = p.read_text(encoding="utf-8", errors="ignore")
        rel = p.relative_to(BACKEND.parent).as_posix()
        if google_key.search(text):
            c.problems.append("%s: looks like a Google API key" % rel)
        if private_key.search(text):
            c.problems.append("%s: contains a private key block" % rel)
        if not rel.startswith("backend/tests/"):
            for m in url_pw.finditer(text):
                if m.group(1) not in PLACEHOLDER_PASSWORDS:
                    c.problems.append("%s: database URL with a non-placeholder password" % rel)
            if rel.startswith("backend/app/") and literal.search(text):
                c.problems.append("%s: hard-coded credential-like string" % rel)
    gitignore = (BACKEND.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    if ".env" not in [l.strip() for l in gitignore]:
        c.problems.append(".gitignore does not exclude .env")
    return c


def check_secret_access_is_limited():
    c = Check("secret values are read in only three places")
    for p in _py_files(("app",)):
        if "get_secret_value(" in p.read_text(encoding="utf-8") and _rel(p) not in SECRET_ACCESS_ALLOWED:
            c.problems.append("%s reads a secret value" % _rel(p))
    return c


def _main_guard_nodes(tree):
    ids = set()
    for n in tree.body:
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name) and n.test.left.id == "__name__":
            ids.update(id(x) for x in ast.walk(n))
    return ids


def check_logging_is_safe():
    c = Check("logging never records exceptions' text, learner text, prompts, or secrets")
    for p in _py_files(("app",)):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        guarded = _main_guard_nodes(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Name) and f.id == "print" and id(node) not in guarded:
                c.problems.append("%s:%d: print() outside a __main__ block" % (_rel(p), node.lineno))
            if isinstance(f, ast.Attribute) and f.attr in LOG_METHODS and isinstance(f.value, ast.Name) and f.value.id in {"logger", "logging"}:
                if f.attr == "exception":
                    c.problems.append("%s:%d: logger.exception() writes a traceback" % (_rel(p), node.lineno))
                for arg in node.args[1:]:
                    if isinstance(arg, ast.Name) and arg.id in BAD_LOG_NAMES | SENSITIVE_NAMES:
                        c.problems.append("%s:%d: logs the value of '%s'" % (_rel(p), node.lineno, arg.id))
                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id in {"str", "repr"}:
                        c.problems.append("%s:%d: logs str()/repr() of a value" % (_rel(p), node.lineno))
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Attribute) and sub.attr in SENSITIVE_NAMES and not isinstance(sub.value, ast.Call):
                            c.problems.append("%s:%d: logs attribute '.%s'" % (_rel(p), node.lineno, sub.attr))
                if node.args and isinstance(node.args[0], ast.JoinedStr):
                    c.problems.append("%s:%d: f-string in a log call (values may leak)" % (_rel(p), node.lineno))
    return c


def check_no_dangerous_calls():
    c = Check("no eval/exec/pickle/shell=True, and SQL is never built from strings")
    for p in _py_files(("app",)):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
                if name in {"eval", "exec"}:
                    c.problems.append("%s:%d: %s()" % (_rel(p), node.lineno, name))
                if name == "text" and node.args and not isinstance(node.args[0], ast.Constant):
                    c.problems.append("%s:%d: SQL text() built from a non-constant" % (_rel(p), node.lineno))
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        c.problems.append("%s:%d: shell=True" % (_rel(p), node.lineno))
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if any(m.split(".")[0] in {"pickle", "marshal"} for m in mods):
                    c.problems.append("%s:%d: imports pickle/marshal" % (_rel(p), node.lineno))
    return c


def _function_defs(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name: n for n in _module_level(tree.body, (ast.FunctionDef,)) if isinstance(n, ast.FunctionDef)}


def _signature_problem(fd, call):
    if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
        return None  # uses *args / **kwargs: cannot be checked statically
    a = fd.args
    pos = [x.arg for x in a.posonlyargs + a.args]
    kwonly = [x.arg for x in a.kwonlyargs]
    required_pos = pos[: len(pos) - len(a.defaults)]
    required_kw = [x.arg for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is None]
    given = [k.arg for k in call.keywords]
    if len(call.args) > len(pos) and not a.vararg:
        return "passes %d positional arguments but %s() accepts %d" % (len(call.args), fd.name, len(pos))
    clash = [k for k in given if k in pos[: len(call.args)]]
    if clash:
        return "gives argument '%s' twice" % clash[0]
    allowed = set(pos[len(call.args):]) | set(kwonly)
    unknown = [k for k in given if k not in allowed]
    if unknown and not a.kwarg:
        return "unknown keyword argument '%s' for %s()" % (unknown[0], fd.name)
    missing = [r for r in required_pos[len(call.args):] if r not in given] + [r for r in required_kw if r not in given]
    if missing:
        return "missing argument '%s' for %s()" % (missing[0], fd.name)
    return None


def check_call_signatures():
    c = Check("calls to project functions match their definitions (argument count and keyword names)")
    cache, checked = {}, 0
    for p in _py_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        known = {}
        for name, fd in cache.setdefault(p, _function_defs(p)).items():
            known[name] = fd
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and node.module.split(".")[0] in CODE_DIRS:
                target = _module_path(node.module)
                if target is None:
                    continue
                defs = cache.setdefault(target, _function_defs(target))
                for a in node.names:
                    if a.name in defs:
                        known[a.asname or a.name] = defs[a.name]
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in known:
                fd = known[node.func.id]
                if fd.decorator_list:
                    continue  # decorated functions may change their signature
                checked += 1
                problem = _signature_problem(fd, node)
                if problem:
                    c.problems.append("%s:%d: %s" % (_rel(p), node.lineno, problem))
    c.info.append("%d calls checked" % checked)
    return c


def _route_dependencies():
    used = set()
    for p in sorted((BACKEND / "app/api").glob("*.py")):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Depends" and n.args and isinstance(n.args[0], ast.Name):
                used.add(n.args[0].id)
    return used


def check_test_overrides_target_real_dependencies():
    c = Check("tests only override dependencies that some route really uses (catches stale API tests)")
    used = _route_dependencies()
    pattern = re.compile(r"dependency_overrides\[(\w+)\]")
    for p in _py_files(("tests",)):
        for key in sorted(set(pattern.findall(p.read_text(encoding="utf-8")))):
            if key not in used:
                c.problems.append("%s overrides '%s', which no route depends on" % (_rel(p), key))
    return c


def code_routes():
    routes = set()
    for p in sorted((BACKEND / "app/api").glob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        prefix = ""
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "APIRouter":
                for kw in n.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        prefix = kw.value.value
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef):
                for d in n.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in {"get", "post"} \
                            and getattr(d.func.value, "id", "") == "router" and d.args and isinstance(d.args[0], ast.Constant):
                        routes.add("%s %s%s" % (d.func.attr.upper(), prefix, d.args[0].value))
    return routes


def check_routes_are_documented():
    c = Check("every API route appears in docs/api_reference.md")
    doc = BACKEND / "docs/api_reference.md"
    if not doc.is_file():
        c.problems.append("docs/api_reference.md does not exist")
        return c
    text = doc.read_text(encoding="utf-8")
    routes = code_routes()
    for r in sorted(routes):
        if r not in text:
            c.problems.append("route '%s' is not documented" % r)
    c.info.append("%d routes" % len(routes))
    return c


def run_all():
    return [
        check_compile(), check_imports_resolve(), check_no_import_cycles(), check_env_matches_settings(),
        check_no_secrets_committed(), check_secret_access_is_limited(), check_logging_is_safe(),
        check_no_dangerous_calls(), check_test_overrides_target_real_dependencies(), check_call_signatures(), check_routes_are_documented(),
    ]


def main():
    failed = 0
    for check in run_all():
        status = "PASS" if check.passed else "FAIL"
        extra = ("  (" + "; ".join(check.info) + ")") if check.info else ""
        print("%s  %s%s" % (status, check.name, extra))
        for problem in check.problems:
            print("        - " + problem)
        failed += not check.passed
    print("\n%s" % ("All static checks passed." if not failed else "%d check(s) failed." % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

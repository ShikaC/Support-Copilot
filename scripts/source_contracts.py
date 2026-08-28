from __future__ import annotations

import ast
import re
from pathlib import Path


JAVA_CONTROLLER_ROOT = "services/support-copilot-api/src/main/java"
FASTAPI_MAIN = "services/support-copilot-ai/app/main.py"
JAVA_MAPPING = re.compile(
    r"@(Get|Post|Patch|Put|Delete)Mapping(?:\((?P<arguments>[^)]*)\))?",
    re.DOTALL,
)
REQUEST_MAPPING = re.compile(
    r"@RequestMapping(?:\((?P<arguments>[^)]*)\))?", re.DOTALL
)
NAMED_MAPPING_PATH = re.compile(
    r"\b(?:path|value)\s*=\s*(?P<value>\{[^}]*\}|\"(?:\\.|[^\"])*\")",
    re.DOTALL,
)
MAPPING_PATH_ASSIGNMENT = re.compile(r"\b(?:path|value)\s*=")
STRING_LITERAL = re.compile(r'"(?:\\.|[^"\\])*"')
FASTAPI_MAPPING = re.compile(
    r'@app\.(get|post|patch|put|delete)\(\s*"([^"]+)"', re.IGNORECASE
)
DOCUMENTED_API_ROW = re.compile(
    r"^\|\s*(GET|POST|PATCH|PUT|DELETE)\s*\|\s*`([^`]+)`\s*\|"
)
DOCUMENTED_COMMAND_ROW = re.compile(
    r"^\|\s*(verify-[a-z0-9-]+)\s*\|\s*`([^`]+)`\s*\|\s*$"
)
EXECUTED_COMMAND_ID = re.compile(
    r"^\s*run_documented_gate\s+(verify-[a-z0-9-]+)\b", re.MULTILINE
)


class DocumentationContractError(RuntimeError):
    pass


def join_route(base: str, suffix: str) -> str:
    if not suffix:
        return base
    return f"{base.rstrip('/')}/{suffix.lstrip('/')}"


def mapping_paths(arguments: str | None) -> tuple[str, ...]:
    if arguments is None or not arguments.strip():
        return ("",)
    named = NAMED_MAPPING_PATH.search(arguments)
    if named is not None:
        literals = STRING_LITERAL.findall(named.group("value"))
        return tuple(ast.literal_eval(literal) for literal in literals)
    if MAPPING_PATH_ASSIGNMENT.search(arguments):
        raise DocumentationContractError("non-literal mapping path")
    stripped = arguments.lstrip()
    if stripped.startswith('"'):
        literal = STRING_LITERAL.match(stripped)
        if literal is None:
            raise DocumentationContractError("invalid mapping path literal")
        return (ast.literal_eval(literal.group()),)
    if stripped.startswith("{"):
        closing = stripped.find("}")
        if closing == -1:
            raise DocumentationContractError("invalid mapping path array")
        literals = STRING_LITERAL.findall(stripped[: closing + 1])
        if not literals:
            raise DocumentationContractError("non-literal mapping path")
        return tuple(ast.literal_eval(literal) for literal in literals)
    if re.match(r"[A-Za-z_]\w*\s*=", stripped):
        return ("",)
    raise DocumentationContractError("non-literal mapping path")


def java_routes(source: str) -> set[tuple[str, str]]:
    base_matches = list(REQUEST_MAPPING.finditer(source))
    if len(base_matches) != 1:
        raise DocumentationContractError("Java controller is missing @RequestMapping")
    base_paths = mapping_paths(base_matches[0].group("arguments"))
    if len(base_paths) != 1 or not base_paths[0]:
        raise DocumentationContractError("Java controller requires one literal base path")
    routes: set[tuple[str, str]] = set()
    for match in JAVA_MAPPING.finditer(source):
        for suffix in mapping_paths(match.group("arguments")):
            routes.add((match.group(1).upper(), join_route(base_paths[0], suffix)))
    return routes


def fastapi_routes(source: str) -> set[tuple[str, str]]:
    return {
        (match.group(1).upper(), match.group(2))
        for match in FASTAPI_MAPPING.finditer(source)
    }


def source_api_routes(repo_root: Path) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    controllers = sorted((repo_root / JAVA_CONTROLLER_ROOT).rglob("*Controller.java"))
    if not controllers:
        raise DocumentationContractError("no Java controllers were discovered")
    for controller in controllers:
        routes.update(java_routes(controller.read_text(encoding="utf-8")))
    routes.update(fastapi_routes((repo_root / FASTAPI_MAIN).read_text(encoding="utf-8")))
    return routes


def documented_api_routes(operations_doc: str) -> set[tuple[str, str]]:
    return {
        (match.group(1), match.group(2))
        for line in operations_doc.splitlines()
        if (match := DOCUMENTED_API_ROW.match(line)) is not None
    }


def documented_verification_commands(operations_doc: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for line in operations_doc.splitlines()
        if (match := DOCUMENTED_COMMAND_ROW.match(line)) is not None
    }


def executed_verification_ids(verifier_source: str) -> set[str]:
    return set(EXECUTED_COMMAND_ID.findall(verifier_source))


def ai_modes(config_source: str) -> set[str]:
    tree = ast.parse(config_source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "ai_mode":
            continue
        annotation = node.annotation
        if not isinstance(annotation, ast.Subscript):
            break
        if not isinstance(annotation.value, ast.Name) or annotation.value.id != "Literal":
            break
        slices = (
            annotation.slice.elts
            if isinstance(annotation.slice, ast.Tuple)
            else [annotation.slice]
        )
        values = {
            item.value
            for item in slices
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
        if values:
            return values
    raise DocumentationContractError("could not derive AI_MODE values from Settings.ai_mode")


def settings_environment_names(config_source: str) -> set[str]:
    tree = ast.parse(config_source)
    settings_class = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "Settings"
        ),
        None,
    )
    if settings_class is None:
        raise DocumentationContractError("could not find Settings class")
    names: set[str] = set()
    for node in settings_class.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        names.add(node.target.id.upper())
        if not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if keyword.arg != "validation_alias":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                names.add(keyword.value.value)
    return names

"""Source-code extraction with syntax-aware Python symbol support."""

from __future__ import annotations

import ast
from typing import Any

from idp_brain.ingestion.extractors.base import (
    ArtifactExtractionContext,
    ExtractionCandidate,
    ExtractionDiagnostic,
    ExtractionResult,
    LineRange,
    decode_utf8,
    make_result,
)


class SourceCodeExtractor:
    name = "builtin-source-code"
    version = "1"
    supported_artifact_roles = frozenset({"source_code"})

    def extract(
        self,
        artifact: ArtifactExtractionContext,
        stream: bytes,
    ) -> ExtractionResult:
        text, diagnostics = decode_utf8(self.name, artifact, stream)
        if artifact.language != "python":
            return make_result(
                extractor_name=self.name,
                extractor_version=self.version,
                artifact=artifact,
                candidates=(),
                diagnostics=(
                    *diagnostics,
                    ExtractionDiagnostic(
                        severity="warning",
                        code="unsupported_language",
                        message=(
                            "no configured grammar for "
                            f"{artifact.language or 'unknown'}"
                        ),
                        locator=artifact.logical_locator,
                    ),
                ),
            )
        tree_sitter_result = _extract_python_with_tree_sitter(
            artifact=artifact,
            stream=stream,
            diagnostics=diagnostics,
        )
        if tree_sitter_result is not None:
            return tree_sitter_result
        return _extract_python_with_ast(
            extractor_name=self.name,
            extractor_version=self.version,
            artifact=artifact,
            text=text,
            diagnostics=diagnostics,
        )


def _extract_python_with_tree_sitter(
    *,
    artifact: ArtifactExtractionContext,
    stream: bytes,
    diagnostics: tuple[ExtractionDiagnostic, ...],
) -> ExtractionResult | None:
    try:
        import tree_sitter_python
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    parser = Parser(Language(tree_sitter_python.language()))
    tree = parser.parse(stream)
    root = tree.root_node
    candidates: list[ExtractionCandidate] = []
    imports = tuple(sorted(_tree_sitter_imports(root)))
    candidates.extend(_tree_sitter_symbol_candidates(artifact, root, imports, ()))
    for module_import in imports:
        candidates.append(
            ExtractionCandidate(
                candidate_type="import",
                text=None,
                locator=f"{artifact.logical_locator}:import:{module_import}",
                language="python",
                metadata={"module": module_import, "parser": "tree-sitter"},
            )
        )
    parser_diagnostics = diagnostics
    if root.has_error:
        parser_diagnostics = (
            *diagnostics,
            ExtractionDiagnostic(
                severity="error",
                code="source_parse_error",
                message="tree-sitter reported a syntax error",
                locator=artifact.logical_locator,
            ),
        )
    return make_result(
        extractor_name=SourceCodeExtractor.name,
        extractor_version=SourceCodeExtractor.version,
        artifact=artifact,
        candidates=sorted(candidates, key=lambda c: c.locator),
        diagnostics=parser_diagnostics,
    )


def _extract_python_with_ast(
    *,
    extractor_name: str,
    extractor_version: str,
    artifact: ArtifactExtractionContext,
    text: str,
    diagnostics: tuple[ExtractionDiagnostic, ...],
) -> ExtractionResult:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return make_result(
            extractor_name=extractor_name,
            extractor_version=extractor_version,
            artifact=artifact,
            candidates=(),
            diagnostics=(
                *diagnostics,
                ExtractionDiagnostic(
                    severity="error",
                    code="source_parse_error",
                    message=exc.msg,
                    locator=artifact.logical_locator,
                ),
            ),
        )
    candidates: list[ExtractionCandidate] = []
    imports = _imports(tree)
    candidates.extend(_ast_symbol_candidates(artifact, tree, imports, ()))
    for module_import in imports:
        candidates.append(
            ExtractionCandidate(
                candidate_type="import",
                text=None,
                locator=f"{artifact.logical_locator}:import:{module_import}",
                language="python",
                metadata={"module": module_import},
            )
        )
    return make_result(
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        artifact=artifact,
        candidates=sorted(candidates, key=lambda c: c.locator),
        diagnostics=diagnostics,
    )


def _walk_tree_sitter(node: Any) -> list[Any]:
    nodes = [node]
    for child in node.named_children:
        nodes.extend(_walk_tree_sitter(child))
    return nodes


def _tree_sitter_symbol_candidates(
    artifact: ArtifactExtractionContext,
    node: Any,
    imports: tuple[str, ...],
    parent_path: tuple[str, ...],
) -> list[ExtractionCandidate]:
    candidates: list[ExtractionCandidate] = []
    next_parent_path = parent_path
    if node.type in {"class_definition", "function_definition"}:
        candidate = _tree_sitter_symbol_candidate(
            artifact,
            node,
            imports,
            parent_path,
        )
        if candidate is not None:
            candidates.append(candidate)
            next_parent_path = candidate.symbol_path
    for child in node.named_children:
        candidates.extend(
            _tree_sitter_symbol_candidates(
                artifact,
                child,
                imports,
                next_parent_path,
            )
        )
    return candidates


def _tree_sitter_imports(root: Any) -> set[str]:
    imports: set[str] = set()
    for node in _walk_tree_sitter(root):
        if node.type == "import_statement":
            text = node.text.decode("utf-8", errors="replace")
            imports.update(_import_names_from_statement(text))
        elif node.type == "import_from_statement":
            module = node.child_by_field_name("module_name")
            if module is None:
                module = node.child_by_field_name("name")
            if module is not None:
                imports.add(module.text.decode("utf-8", errors="replace"))
    return imports


def _import_names_from_statement(statement: str) -> set[str]:
    cleaned = statement.removeprefix("import").strip()
    return {
        part.strip().split(" as ", maxsplit=1)[0]
        for part in cleaned.split(",")
        if part.strip()
    }


def _tree_sitter_symbol_candidate(
    artifact: ArtifactExtractionContext,
    node: Any,
    imports: tuple[str, ...],
    parent_path: tuple[str, ...],
) -> ExtractionCandidate | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = name_node.text.decode("utf-8", errors="replace")
    symbol_type = "class" if node.type == "class_definition" else "function"
    signature = _tree_sitter_signature(node)
    docstring = _tree_sitter_docstring(node)
    start_line = node.start_point.row + 1
    end_line = node.end_point.row + 1
    return ExtractionCandidate(
        candidate_type="symbol",
        text=docstring,
        locator=f"{artifact.logical_locator}:L{start_line}-L{end_line}",
        line_range=LineRange(start_line, end_line),
        symbol_path=(*parent_path, name),
        signature_text=signature,
        language="python",
        metadata={
            "symbol_type": symbol_type,
            "imports": imports,
            "parser": "tree-sitter",
        },
    )


def _tree_sitter_signature(node: Any) -> str:
    name_node = node.child_by_field_name("name")
    name = (
        name_node.text.decode("utf-8", errors="replace")
        if name_node is not None
        else "unknown"
    )
    if node.type == "class_definition":
        return f"class {name}"
    params = node.child_by_field_name("parameters")
    params_text = (
        params.text.decode("utf-8", errors="replace") if params is not None else "()"
    )
    return f"def {name}{params_text}"


def _tree_sitter_docstring(node: Any) -> str | None:
    body = node.child_by_field_name("body")
    if body is None:
        return None
    for child in body.named_children:
        if child.type != "expression_statement":
            continue
        text: str = child.text.decode("utf-8", errors="replace").strip()
        if (
            (text.startswith('"""') and text.endswith('"""'))
            or (text.startswith("'''") and text.endswith("'''"))
            or (text.startswith('"') and text.endswith('"'))
            or (text.startswith("'") and text.endswith("'"))
        ):
            return text.strip("\"'")
        return None
    return None


def _symbol_candidate(
    artifact: ArtifactExtractionContext,
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    imports: tuple[str, ...],
    parent_path: tuple[str, ...] = (),
) -> ExtractionCandidate:
    symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"
    end_line = getattr(node, "end_lineno", node.lineno)
    return ExtractionCandidate(
        candidate_type="symbol",
        text=ast.get_docstring(node),
        locator=f"{artifact.logical_locator}:L{node.lineno}-L{end_line}",
        line_range=LineRange(node.lineno, end_line),
        symbol_path=(*parent_path, node.name),
        signature_text=_signature(node),
        language="python",
        metadata={"symbol_type": symbol_type, "imports": imports},
    )


def _imports(tree: ast.AST) -> tuple[str, ...]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return tuple(sorted(imports))


def _ast_symbol_candidates(
    artifact: ArtifactExtractionContext,
    node: ast.AST,
    imports: tuple[str, ...],
    parent_path: tuple[str, ...],
) -> list[ExtractionCandidate]:
    candidates: list[ExtractionCandidate] = []
    next_parent_path = parent_path
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        candidate = _symbol_candidate(artifact, node, imports, parent_path)
        candidates.append(candidate)
        next_parent_path = candidate.symbol_path
    for child in ast.iter_child_nodes(node):
        candidates.extend(
            _ast_symbol_candidates(artifact, child, imports, next_parent_path)
        )
    return candidates


def _signature(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(_expr_name(base) for base in node.bases)
        return f"class {node.name}({bases})" if bases else f"class {node.name}"
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = [arg.arg for arg in node.args.posonlyargs + node.args.args]
    if node.args.vararg is not None:
        args.append("*" + node.args.vararg.arg)
    args.extend(arg.arg for arg in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        args.append("**" + node.args.kwarg.arg)
    return f"{prefix} {node.name}({', '.join(args)})"


def _expr_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_expr_name(node.value)}.{node.attr}"
    return type(node).__name__

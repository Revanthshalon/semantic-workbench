# Step 5: Python Parsing Implementation Plan

**Goal:** Read the Python source of every project into nodes and edges, resolve references inside a project and across projects, and keep the graph up to date file by file.

**Architecture:** Four parts that do not know each other. A walker chooses the files. A parser turns one file's bytes into nodes and unresolved references, knowing nothing of other files. A resolver turns references into edges, working on data only. A use case drives the three and the store. Because the parser sees one file at a time, a changed file costs one parse.

**Tech stack:** `tree-sitter`, `tree-sitter-python`, `ignore`, `globset`, `blake3`.

**Spec:** [domain-model.md](../domain-model.md), [storage-model.md](../storage-model.md#how-the-store-is-written), [usage-guide.md](../usage-guide.md#workbench-index). Capabilities I1 to I6, I10, X4, X10.

**Read first:** [00-overview.md](./00-overview.md).

**Widened by [python-parsing.md](../python-parsing.md).** That page proposes reading all of Python, plain binaries and FastAPI (I14 to I18). This plan is its first slice, and its phases P1 to P7 follow this plan's tasks.

## Global constraints

- A file that fails to parse is never an error. It gets a `File` node, a record with `Failed` and the parser's message, and no nodes below it. The index goes on and ends in success.
- A file is read again only when its content hash differs from its record, when its record says `GrammarUnavailable`, or when `--force` is given.
- Skipped always: what `.gitignore` excludes, the folders `.git`, `node_modules`, `.venv` and `.workbench`, and what a project's `exclude` patterns match.
- Every edge made here has the `TreeSitter` provenance.
- A reference that cannot be resolved stays an unresolved reference. Nothing is guessed.
- Indexing the same files twice gives the same node ids and the same edges.

## Review focus

- A file that is not UTF-8 is recorded as `Failed`, not skipped silently and not a crash. Task 2.
- A relative import, `from . import x` or `from ..models import Invoice`, is resolved against the importing file's own package. Task 4.
- A star import, `from shared_api.models import *`, gives one `Imports` edge to the module's file and no edge to its members. Calls to names it brought in stay unresolved. Task 4.
- A name defined twice in one file gives two nodes with ordinals `0` and `1`. A reference to the name resolves to the last one, as Python does. Task 2 and Task 4.
- A symbolic link that points back into its own folder does not make the walker loop. Task 1.

## What Release 1 reads from Python

| Node kind | From |
|---|---|
| `File` | Every `.py` file |
| `Class` | `class` |
| `Function` | `def` at module level, or inside a function |
| `Method` | `def` inside a class |
| `Property` | A method decorated with `@property` |
| `Constant` | A module-level assignment to a name in capitals |
| `Variable` | Any other module-level assignment |
| `Import` | Each name an `import` statement binds |

| Reference kind | From |
|---|---|
| `Imports` | `import a.b`, `from a import b`, with or without `as` |
| `Calls` | A call expression. One that resolves to a class becomes `Instantiates` |
| `Extends` | A base class in a class statement |
| `Decorates` | A decorator on a function or a class |

Parameters, enum members, type annotations and attribute access are not read in Release 1.

## File structure

| File | Holds |
|---|---|
| `src/adapters/driven/fs/walk.rs` | `Files::walk` |
| `src/adapters/driven/parse/languages/python/mod.rs` | `PythonParser` |
| `src/adapters/driven/parse/languages/python/definitions.rs` | Nodes and `Contains` edges |
| `src/adapters/driven/parse/languages/python/references.rs` | Unresolved references |
| `src/use_cases/index/symbols.rs` | `SymbolTable` |
| `src/use_cases/index/resolve.rs` | Resolution inside a project |
| `src/use_cases/index/resolve_imports.rs` | Resolution across projects |
| `src/use_cases/index/code.rs` | The incremental indexing of code |
| `tests/fixtures/acme/*/src/**/*.py` | The Acme Shop source |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 5A | 1 | C0, 2C | `fs/walk.rs` |
| 5B | 2 | C0 | `python/mod.rs`, `python/definitions.rs` |
| 5C | 3 | 5B | `python/references.rs` |
| 5D | 4 | C0 | `index/symbols.rs`, `index/resolve.rs` |
| 5E | 5 | 5D | `index/resolve_imports.rs` |
| 5F | 6 | C0, 5A | `index/code.rs` |
| 5G | 7 | 4G, 5C, 5E, 5F, 3C | the fixture's `.py` files, and the end-to-end tests |

5A, 5B and 5D can start together, by three developers, the day C0 is merged. None of them needs another: the walker is tested on temp folders, the parser on strings of Python, and the resolver on nodes built by hand. 5F is tested with a parser written in the test that returns fixed nodes, so it does not wait for 5B or 5C.

## Task 1: Choose the files to read

**Files:** create `src/adapters/driven/fs/walk.rs`.

**Produces:** the `walk` method of the `Files` port for `DiskFiles`:

```rust
fn walk(&self, root: &Path, exclude: &[String]) -> Result<Vec<RelPath>, FilesError>;
```

It returns every file below `root`, sorted, as paths from `root`. Symbolic links are not followed.

**Tests:**

| Test | Asserts |
|---|---|
| `gitignored_file_is_skipped` | With `build/` in `.gitignore`, `build/x.py` is absent |
| `fixed_folders_are_skipped` | `.git`, `node_modules`, `.venv` and `.workbench` are absent with no `.gitignore` |
| `exclude_pattern_is_skipped` | `**/*_pb2.py` removes `a/b_pb2.py` and keeps `a/b.py` |
| `nested_gitignore_is_honoured` | A `.gitignore` in a subfolder applies below it |
| `result_is_sorted_and_relative` | `["a.py", "pkg/b.py"]` |
| `link_into_its_own_folder_does_not_loop` | The walk ends |
| `invalid_exclude_pattern_is_an_error` | `FilesError::Pattern` naming the pattern |

**Commit:** `feat(index): choose the files of a project`

## Task 2: Python definitions

**Files:** create `src/adapters/driven/parse/languages/python/mod.rs`, `definitions.rs`.

**Produces:**

```rust
pub struct PythonParser;                       // implements `LanguageParser`
pub fn module_path(file: &RelPath) -> String;  // "src/billing/worker.py" -> "billing.worker"
```

`module_path` drops a leading `src/`, drops `.py`, turns `/` into `.`, and drops a trailing `.__init__`. A node's qualified name is the module path, then the names of the classes and functions around it, joined by dots.

Each node carries its span, its signature (the `def` or `class` line up to the colon), its doc string, `is_async`, and its decorators. Each has a `Contains` edge from the node around it, or from the `File`.

**Tests**, each on a string of Python:

| Test | Asserts |
|---|---|
| `module_path_drops_src_and_init` | `src/shared_api/models.py` gives `shared_api.models`; `pkg/__init__.py` gives `pkg` |
| `class_and_method_are_found` | `class Invoice:` with `def total(self):` gives a `Class` `m.Invoice` and a `Method` `m.Invoice.total`, with `Contains` from file to class to method |
| `module_function_is_a_function` | Kind `Function` |
| `async_def_sets_is_async` | `is_async == true` |
| `property_decorator_gives_a_property` | Kind `Property`, and `decorators == ["property"]` |
| `capital_assignment_is_a_constant` | `MAX = 3` gives a `Constant`; `count = 0` a `Variable` |
| `doc_string_and_signature_are_kept` | `doc == "An invoice."`, `signature == "def total(self) -> Decimal"` |
| `span_covers_the_whole_definition` | Lines count from 1, and the end line is the last line of the body |
| `name_defined_twice_gets_ordinals` | Two nodes for `f`, with different ids |
| `same_source_gives_the_same_ids` | Parsing twice gives equal node lists |
| `syntax_error_is_a_parse_error` | `Err(ParseError)` with the line |
| `bytes_that_are_not_utf8_are_a_parse_error` | `Err(ParseError)` |

**Commit:** `feat(parse): read Python definitions`

## Task 3: Python references

**Files:** create `src/adapters/driven/parse/languages/python/references.rs`.

**Produces:** `PythonParser::parse` now fills `unresolved`. Each reference has `from` (the node the reference appears in, or the `File` at module level), the name as written, its kind and its site. Each `import` statement also gives an `Import` node for every name it binds.

**Tests:**

| Test | Asserts |
|---|---|
| `import_module` | `import shared_api.models` gives one `Imports` reference named `shared_api.models`, from the file |
| `from_import_with_alias` | `from shared_api.models import Invoice as Inv` gives the name `shared_api.models.Invoice`, and an `Import` node named `Inv` |
| `relative_import_keeps_its_dots` | `from ..models import Invoice` gives the name `..models.Invoice` |
| `call_inside_a_function` | `def f(): g()` gives a `Calls` reference named `g`, from `f` |
| `method_call_on_self` | `self.total()` gives the name `self.total` |
| `dotted_call` | `models.Invoice()` gives the name `models.Invoice` |
| `base_class` | `class A(Base):` gives an `Extends` reference named `Base`, from `A` |
| `decorator` | `@retry` gives a `Decorates` reference named `retry`, from the function |
| `two_calls_on_two_lines_are_two_references` | Different sites, different ids |

**Commit:** `feat(parse): read Python references`

## Task 4: Resolve references inside a project

**Files:** create `src/use_cases/index/symbols.rs`, `src/use_cases/index/resolve.rs`.

**Produces:**

```rust
pub struct SymbolTable { /* nodes by project and qualified name; import bindings by file */ }
impl SymbolTable {
    pub fn add_file(&mut self, file: &FileRef, module_path: &str, nodes: &[Node]);
    pub fn remove_file(&mut self, file: &FileRef);
    pub fn lookup(&self, project: &ProjectId, qualified_name: &str) -> Option<&Node>;
}

pub fn resolve(reference: &UnresolvedReference, from: &Node, table: &SymbolTable) -> Option<Edge>;
```

A name is looked up in this order, and the first hit wins:

1. A name the file imported: the `Import` node's target, then the rest of the dotted name below it.
2. `self.<name>`: a method of the class around `from`.
3. A definition in the same file, the last one when there are several.
4. The name as a qualified name in the project.

A `Calls` reference whose target is a `Class` gives an `Instantiates` edge. A relative import is turned into an absolute name from the importing file's module path before step 4.

**Tests**, on nodes built by hand:

| Test | Asserts |
|---|---|
| `call_to_a_function_in_the_same_file` | A `Calls` edge to it, with the reference's site |
| `call_to_an_imported_function` | Through `from pkg.util import helper`, the edge ends at `pkg.util.helper` |
| `call_through_an_alias` | `import pkg.util as u` then `u.helper()` ends at `pkg.util.helper` |
| `self_method_call` | Ends at the method of the same class |
| `call_to_a_class_instantiates` | Kind `Instantiates` |
| `relative_import_resolves` | From `pkg.sub.mod`, `..models.Invoice` ends at `pkg.models.Invoice` |
| `last_definition_wins` | Of two functions named `f`, the edge ends at ordinal `1` |
| `star_import_gives_one_edge_to_the_file` | An `Imports` edge to the `File`, and a later call to a starred name is `None` |
| `unknown_name_stays_unresolved` | `None` |

**Commit:** `feat(index): resolve references inside a project`

## Task 5: Resolve imports across projects

**Files:** create `src/use_cases/index/resolve_imports.rs`.

**Produces:**

```rust
pub struct ImportNames { /* import name -> ProjectId, from the configuration and the manifests */ }
impl ImportNames { pub fn project_for(&self, dotted: &str) -> Option<&ProjectId>; }

pub fn resolve_across(reference: &UnresolvedReference, from: &Node, names: &ImportNames, table: &SymbolTable) -> Option<Edge>;
```

`project_for` takes the first part of a dotted name: `shared_api.models.Invoice` gives the project whose import name is `shared_api`. `resolve_across` is tried only after `resolve` returns `None`. It looks the whole name up in that project; when the name is a module and not a definition, the edge ends at the module's `File`.

**Tests:**

| Test | Asserts |
|---|---|
| `import_of_a_class_in_another_project` | From `billing-api`, `shared_api.models.Invoice` gives an `Imports` edge to Class `Invoice` of `shared-api`, with `specifier == "shared_api.models"` |
| `import_of_a_module_ends_at_its_file` | `import shared_api.models` ends at `File` `src/shared_api/models.py` |
| `call_through_a_cross_project_import` | `Invoice()` after the import gives `Instantiates` to the class in `shared-api` |
| `unknown_import_name_stays_unresolved` | `import requests` gives `None` |
| `import_into_an_excluded_file_stays_unresolved` | The project is known and the node is absent: `None` |

**Commit:** `feat(index): resolve imports across projects`

## Task 6: Index code incrementally

**Files:** create `src/use_cases/index/code.rs`.

**Produces:**

```rust
pub struct IndexCode<F, P> { /* files, parsers by extension */ }
impl<F: Files, P: LanguageParser> IndexCode<F, P> {
    pub async fn run<W: IndexWriter>(&self, writer: &mut W, projects: &[Project], known: &[FileRecord], names: &ImportNames, options: &IndexOptions) -> Result<CodeSummary, IndexError>;
}
pub struct CodeSummary { pub files_read: u64, pub files_skipped: u64, pub failed_files: Vec<FileRef> }
```

For each project, or the one `--project` names: walk, hash each file, and compare with `known`. A file is read when its hash differs, when its record is `GrammarUnavailable`, or with `--force`. A record whose file is gone is removed. Every file `replace_file` or `remove_file` returns is read again in the same run, once. When all files are in, each unresolved reference is tried with `resolve`, then `resolve_across`.

A file with an extension no parser claims gets no node and no record, unless it is a binary's entry, which keeps the `File` node of step 4.

**Tests**, on `MemoryStore`, with a parser written in the test:

| Test | Asserts |
|---|---|
| `unchanged_file_is_skipped` | The parser is called once over two runs |
| `changed_file_is_read_again` | Twice |
| `force_reads_everything` | Twice, with no change |
| `project_option_limits_the_run` | Files of the other project are not walked |
| `deleted_file_is_removed` | Its record and nodes are gone |
| `failed_parse_is_recorded_and_the_run_succeeds` | Status `Failed` with the message; `Ok`; the file is in `failed_files` |
| `grammar_unavailable_is_read_again` | The parser is called although the hash is unchanged |
| `dependent_file_is_read_again_when_its_target_goes` | Renaming a class in `a.py` makes `b.py`, which called it, be parsed again, once |
| `reference_resolves_once_its_target_arrives` | `b.py` indexed before `a.py`: after the run the edge exists and the reference is gone |

**Commit:** `feat(index): index code file by file`

## Task 7: Acme Shop with source, end to end

**Files:** create the `.py` files of `tests/fixtures/acme/`; modify `src/use_cases/index/mod.rs` to call `IndexCode` after the workspace layer, inside the same writer.

The source is small and exact: `shared-api` defines `Invoice` in `src/shared_api/models.py`; billing's `api.py` and `worker.py` and ledger's `api.py` and `consumer.py` each import it; `worker.py` defines `send_invoice`, which creates an `Invoice`.

**Tests**, on the SQLite store:

| Test | Asserts |
|---|---|
| `worker_imports_invoice_across_projects` | An `Imports` edge from `File` `worker.py` of `billing-api` to Class `Invoice` of `shared-api`, `TreeSitter` |
| `send_invoice_instantiates_invoice` | An `Instantiates` edge with a site in `worker.py` |
| `entry_files_are_now_parsed` | The four Python entry files have status `Parsed`; `web-app`'s `main.ts` still has `GrammarUnavailable` |
| `indexed_files_equal_the_fixture_value` | The node ids and edges equal `fixtures::acme()` |
| `indexing_twice_changes_nothing` | Equal graphs, and the second run reads no file |
| `graph_is_valid` | `Graph::validate` returns nothing |

**Commit:** `feat(index): index Python source across projects`

## Done when

- The Acme Shop workspace, indexed from files, equals `fixtures::acme()`.
- A second index reads nothing and changes nothing.
- A file that cannot be parsed is listed, and the index still succeeds.

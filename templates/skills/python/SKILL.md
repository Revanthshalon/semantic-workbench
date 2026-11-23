---
name: python
description: Conventions for writing and changing Python code in this workspace. Read before editing any .py file.
---

# Python

> **TO_REFINE: rough draft.** The project owner will refine these conventions. Every rule below is a placeholder until then.

## Types

- Annotate every parameter and every return type, including `-> None`.
- Annotate fields on classes. Prefer `X | None` to `Optional[X]`.
- Put imports that only serve type checking under `if TYPE_CHECKING:`.

Annotations also help Workbench: a call on an annotated parameter or field resolves directly, without waiting for every caller to agree.

## Layout and tools

- One project, one `pyproject.toml`, code under `src/<import_name>/`.
- Dependencies with the project's manager (`uv` or `poetry`). A local dependency on another project is a path dependency, so Workbench can read it.
- Format and lint with `ruff`. Type-check with `mypy` or `pyright`. `TO_REFINE`: which, and how strict.

## Code

- Small functions with one job. A module-level side effect only in an entry file.
- Raise specific exceptions; never a bare `except:`.
- Configuration through a settings class (such as pydantic `BaseSettings`), never `os.environ` read in many places.
- HTTP clients and message producers are created once and passed in, not built inside every function.

## Tests

- `pytest`. Tests under `tests/`, named `test_*.py`. Shared fixtures in `conftest.py`.
- One behaviour per test. Name the test after the behaviour.
- For a FastAPI route, test through `TestClient(app)` with the full path.
- Before changing shared code, run `workbench impact <node> --tests` and run what it lists.

## Across projects

- An HTTP call to another project, or a message to a topic or queue, needs a `links` entry in `.workbench/config.yml`. `workbench status` warns when one is missing.
- Before changing a model in a shared library, check its API and event contracts with `workbench impact`.

# JBLibs development rules

## Shared terminal interaction contract

- `c_menu`, `input.py` and `term.py` are shared framework code. Fix generic terminal/menu/input behavior here, not separately in each consumer.
- A valid accepted menu/choice action that can hand control to application work must provide immediate visible feedback before the application callback starts. This prevents repeated key presses while a slow action is already running.
- Use the shared processing-feedback contract instead of hand-written `print("working...")` messages:
  - callable `c_menu_item` actions inherit `c_menu.processingText`;
  - `select()` and `confirm()` provide the same immediate feedback;
  - `processingText=""` explicitly disables it;
  - canonical placeholder is `{value}`; `%v%` is a supported compact alias.
- The feedback is emitted only after a valid accepted choice. ESC, invalid keys and incomplete multi-key choices must not emit it.
- Submenu navigation does not need processing feedback because the immediate screen transition is already visible feedback.
- Do not enable selected-value feedback for secret-bearing input such as passwords, tokens or credentials. General free-form `get_input()` remains opt-in/non-progress by default.
- Processing feedback must be flushed before the application callback starts.
- Keep the API backward compatible: add new optional parameters only at the end of existing signatures unless a breaking change is explicitly intended.

## Versioning and verification

- When a source file has its own `__VERSION__`/version marker, update it for behavior changes according to compatibility impact.
- Keep the package `__version__` and README version current for released JBLibs behavior.
- Shared UI changes require focused tests for both the library behavior and at least one consuming sys_apps path after the submodule pointer is updated.

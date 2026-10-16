I added four tests to `tests/test_termui.py` and left production code untouched. With the change applied, all of `tests/test_termui.py` passes (229 passed, 23 skipped). With the production change stashed, three of the four new tests fail.

- **`test_progress_bar_update_min_steps_remainder_applied_on_exit`:** `update(3)`, `update(2)`, `update(2)` on a length-7 bar with `update_min_steps=5`. After the loop `pos` is 5 with 2 steps pending. After the `with` block exits, `pos == 7`, `_completed_intervals == 0`, `finished` is true and `pct == 1.0`.
- **`test_progress_bar_update_min_steps_iteration_final_position`:** a faked TTY and iterating 7 items with threshold 5 end with `pos == 7` and no pending steps. It needs the TTY fake because the non-TTY path never calls `update`.
- **`test_progress_bar_update_min_steps_final_render_tty`:** the last rendered line shows `7/7` and `100%`, and the output ends with a newline. Before the `with` block exits, `7/7` has not been rendered.
- **`test_progress_bar_no_pending_steps_exit_no_extra_render`:** with nothing pending, exit leaves `_last_line` unchanged. It passes with and without the fix.

```json
{"tests_added": ["tests/test_termui.py::test_progress_bar_update_min_steps_remainder_applied_on_exit", "tests/test_termui.py::test_progress_bar_update_min_steps_iteration_final_position", "tests/test_termui.py::test_progress_bar_update_min_steps_final_render_tty", "tests/test_termui.py::test_progress_bar_no_pending_steps_exit_no_extra_render"], "summary": "Added tests covering the sub-threshold remainder being applied and rendered on progress bar exit, via manual update and TTY iteration, plus a guard that nothing extra renders when no steps are pending. Three of the four fail without the fix and pass with it."}
```

from django_admin_runner.context import (
    _clear_execution_context,
    _set_execution_context,
    is_admin_runner,
    set_result_html,
)


class TestIsAdminRunner:
    def test_returns_false_outside_execution(self):
        assert is_admin_runner() is False

    def test_returns_true_during_execution(self):
        _set_execution_context()
        try:
            assert is_admin_runner() is True
        finally:
            _clear_execution_context()

    def test_returns_false_after_clear(self):
        _set_execution_context()
        _clear_execution_context()
        assert is_admin_runner() is False


class TestSetResultHtml:
    def test_stores_value_during_execution(self):
        ctx = _set_execution_context()
        try:
            set_result_html("<div>Result</div>")
            assert ctx["result_html"] == "<div>Result</div>"
        finally:
            _clear_execution_context()

    def test_last_writer_wins(self):
        ctx = _set_execution_context()
        try:
            set_result_html("<div>First</div>")
            set_result_html("<div>Second</div>")
            assert ctx["result_html"] == "<div>Second</div>"
        finally:
            _clear_execution_context()

    def test_noop_outside_execution(self):
        # Should not raise
        set_result_html("<div>Noop</div>")

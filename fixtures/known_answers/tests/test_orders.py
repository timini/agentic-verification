from unittest import mock

from known import orders


def test_save_returns_id():
    assert orders.save_order(7, "book") == 7


def test_save_returns_id_again():
    # Same lines as test_save_returns_id, also checks persistence: overlap but not redundant.
    assert orders.save_order(8, "pen") == 8
    assert orders.DB[8] == "pen"


def test_audit_log_runs():
    orders.audit_log("hello")


def test_is_adult_boundary():
    assert orders.is_adult(18) is True
    assert orders.is_adult(17) is False


def test_discount_small():
    assert orders.discount(50) == 0


def test_notify_mocked():
    m = orders.Mailer()
    with mock.patch.object(orders.Mailer, "send", return_value=True):
        assert orders.notify(m, "a@b") is True

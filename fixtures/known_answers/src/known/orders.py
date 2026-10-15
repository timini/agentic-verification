"""Known-answer fixture. Each function documents the result the audit must report."""

EVENTS: list[str] = []
DB: dict[int, str] = {}


def publish(event: str) -> None:
    EVENTS.append(event)


def save_order(order_id: int, item: str) -> int:
    # Tests check only the return value: deleting publish() must survive (call-delete),
    # while body replacement is killed. This is the H3 pattern.
    DB[order_id] = item
    publish(f"created:{order_id}")
    return order_id


def audit_log(message: str) -> None:
    # Covered but nothing asserts on it: every body replacement must survive (pseudo-tested).
    print(message)


def is_adult(age: int) -> bool:
    # Boundary is asserted at 18, so the >= mutant is killed.
    return age >= 18


def discount(total: int) -> int:
    # Only "0" survives: tests use totals where the discount is 0 or check non-negativity loosely.
    if total > 100:
        return total // 10
    return 0


def never_called(x: int) -> int:
    # Not covered by any test: mutants must be "uncovered", never survivors.
    return x * 2


class Mailer:
    def send(self, to: str) -> bool:
        return bool(to)


def notify(mailer: Mailer, to: str) -> bool:
    # Tests replace Mailer.send with a mock, so mutants of send() are not activated.
    return mailer.send(to)

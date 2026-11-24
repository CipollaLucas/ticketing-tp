from uuid import uuid4

from app.ticketing_core.application.queries import (
    TicketResultPage,
    get_my_tickets,
    get_order,
)


class FakeQueries:
    def __init__(self):
        self.calls = []

    def get_order(self, order_id, actor_id):
        self.calls.append(("order", order_id, actor_id))
        return "receipt"

    def my_tickets(self, actor_id, limit, offset):
        self.calls.append(("tickets", actor_id, limit, offset))
        return TicketResultPage((), 0, limit, offset)


def test_order_query_delegates_only_to_port():
    fake = FakeQueries()
    oid, actor = uuid4(), uuid4()
    assert get_order(oid, actor, fake) == "receipt"
    assert fake.calls == [("order", oid, actor)]


def test_tickets_query_preserves_pagination():
    fake = FakeQueries()
    actor = uuid4()
    page = get_my_tickets(actor, 12, 4, fake)
    assert (page.total, page.limit, page.offset) == (0, 12, 4)
    assert fake.calls == [("tickets", actor, 12, 4)]

"""Pure cutover abort decision guard regression tests."""
import unittest

from h5_abort_guard import Decision, Reconciliation, decide_abort


class AbortGuardTests(unittest.TestCase):
    def make(self, new=(), legacy=(), frozen=True, single=True):
        return Reconciliation(
            new_confirmed_ticket_ids=frozenset(new),
            legacy_known_ticket_ids=frozenset(legacy),
            new_writes_frozen=frozen,
            verified_single_writer=single,
        )

    def test_prewrite_abort(self):
        self.assertIs(decide_abort(self.make()), Decision.SAFE_PREWRITE_ABORT)

    def test_new_sale_missing_in_legacy_blocks(self):
        self.assertIs(
            decide_abort(self.make(new=("ticket-1",))),
            Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT,
        )

    def test_cannot_abort_during_writes(self):
        self.assertIs(
            decide_abort(self.make(new=("a",), legacy=("a",), frozen=False)),
            Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT,
        )

    def test_cannot_abort_without_single_writer(self):
        self.assertIs(
            decide_abort(self.make(new=("a",), legacy=("a",), single=False)),
            Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT,
        )

    def test_matching_data_never_automatically_authorizes_rollback(self):
        self.assertIs(
            decide_abort(self.make(new=("a",), legacy=("a",))),
            Decision.RECONCILIATION_REVIEW_REQUIRED,
        )

    def test_partial_reconciliation_blocks(self):
        self.assertIs(
            decide_abort(self.make(new=("a", "b"), legacy=("a",))),
            Decision.BLOCK_UNRECONCILED_POSTWRITE_ABORT,
        )


if __name__ == "__main__":
    unittest.main()

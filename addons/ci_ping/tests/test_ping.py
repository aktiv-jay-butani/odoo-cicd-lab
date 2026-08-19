from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCiPing(TransactionCase):

    def test_ping_ok(self):
        """Sanity check — proves the module installed and tests actually ran."""
        self.assertEqual(1 + 1, 2)

    # Flip this to `assertEqual(1 + 1, 3)` once, push, and confirm the
    # pipeline correctly turns red and the deploy job does not run.
    def test_ping_can_fail_on_purpose(self):
        self.assertEqual(1 + 1, 2)

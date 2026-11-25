import unittest

import fetcher
import providers


class TokocryptoLegacyAdapterGuardTests(unittest.TestCase):
    def test_provider_factory_fails_closed_for_legacy_tokocrypto_adapter(self):
        with self.assertRaisesRegex(
            ValueError, "legacy Tokocrypto adapter is disabled"
        ):
            providers.build("tokocrypto")

    def test_generic_fetcher_source_rejects_tokocrypto_identity(self):
        with self.assertRaisesRegex(
            ValueError, "legacy Tokocrypto Source is disabled"
        ):
            fetcher.Source(
                name="tokocrypto",
                style="binance_style",
                base_url="https://www.tokocrypto.site",
            )

    def test_tokocrypto_guard_is_case_insensitive(self):
        with self.assertRaisesRegex(
            ValueError, "legacy Tokocrypto Source is disabled"
        ):
            fetcher.Source(
                name="TOKOCRYPTO",
                style="open_v1",
                base_url="https://www.tokocrypto.com",
            )


if __name__ == "__main__":
    unittest.main()

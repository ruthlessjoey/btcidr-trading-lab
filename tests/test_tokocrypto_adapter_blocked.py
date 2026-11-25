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
            ValueError, "legacy generic Tokocrypto Source is disabled"
        ):
            fetcher.Source(
                name="tokocrypto",
                style="binance_style",
                base_url="https://www.tokocrypto.site",
            )

    def test_tokocrypto_guard_is_case_insensitive(self):
        with self.assertRaisesRegex(
            ValueError, "legacy generic Tokocrypto Source is disabled"
        ):
            fetcher.Source(
                name="TOKOCRYPTO",
                style="open_v1",
                base_url="https://www.tokocrypto.com",
            )

    def test_tokocrypto_hosts_are_rejected_even_with_other_source_names(self):
        blocked_urls = (
            "https://www.tokocrypto.site",
            "https://api.tokocrypto.site",
            "https://www.tokocrypto.com",
            "https://cloudme-toko.2meta.app",
        )
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaisesRegex(
                    ValueError, "legacy generic Tokocrypto Source is disabled"
                ):
                    fetcher.Source(
                        name="renamed-provider",
                        style="binance_style",
                        base_url=url,
                    )


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from AutomateWeb import (
    Product,
    ReportFiles,
    SmartPriceError,
    demo_products,
    format_brl,
    generate_reports,
    is_unwanted_result,
    main,
    parse_brl_price,
    parse_rating,
    products_to_dataframe,
    read_smtp_settings,
    run_pipeline,
    shorten_label,
)


class ParsingTests(unittest.TestCase):
    def test_parse_brazilian_prices(self):
        self.assertEqual(parse_brl_price("R$ 4.299,90"), 4299.90)
        self.assertEqual(parse_brl_price("1.299"), 1299.0)
        self.assertEqual(parse_brl_price("999,50"), 999.50)
        self.assertEqual(parse_brl_price("999.50"), 999.50)

    def test_parse_rating(self):
        self.assertEqual(parse_rating("4,7 de 5 estrelas"), 4.7)
        self.assertIsNone(parse_rating(None))

    def test_currency_format(self):
        self.assertEqual(format_brl(4299.9), "R$ 4.299,90")

    def test_accessory_filter_respects_query(self):
        self.assertTrue(is_unwanted_result("Capa para Galaxy S24", "Galaxy S24"))
        self.assertFalse(is_unwanted_result("Capa para Galaxy S24", "capa Galaxy S24"))

    def test_chart_label_is_compact_and_limited(self):
        label = shorten_label("  Notebook   Dell G15 com um título muito longo  ", 24)
        self.assertLessEqual(len(label), 24)
        self.assertEqual(label, "Notebook Dell G15 com…")

    def test_smtp_settings_use_gmail_defaults(self):
        values = {
            "SMTP_USER": "remetente@gmail.com",
            "SMTP_PASSWORD": "senha-de-app",
        }
        with patch.dict(os.environ, values, clear=True):
            self.assertEqual(
                read_smtp_settings(),
                ("smtp.gmail.com", 587, "remetente@gmail.com", "senha-de-app", True),
            )


class PipelineTests(unittest.TestCase):
    def test_demo_data_is_reproducible_and_explicit(self):
        first = demo_products("notebook", 3)
        second = demo_products("notebook", 3)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertTrue(all("FICTÍCIOS" in product.source for product in first))

    def test_empty_products_raise_clear_error(self):
        with self.assertRaises(SmartPriceError):
            products_to_dataframe([])

    @patch("AutomateWeb.load_env_file")
    @patch("AutomateWeb.run_pipeline")
    def test_missing_smtp_stops_before_collection(self, pipeline, load_env):
        with patch.dict(os.environ, {}, clear=True):
            result = main(
                [
                    "Notebook Dell G15",
                    "--modo",
                    "real",
                    "--email",
                    "destino@example.com",
                ]
            )
        self.assertEqual(result, 1)
        pipeline.assert_not_called()
        load_env.assert_called_once()

    @patch("AutomateWeb.load_env_file")
    @patch("AutomateWeb.send_email")
    @patch("AutomateWeb.run_pipeline")
    def test_email_failure_does_not_hide_generated_reports(
        self, pipeline, send_email, load_env
    ):
        product = Product(
            name="Notebook real de teste",
            price=4999.90,
            rating=4.7,
            url="https://www.amazon.com.br/dp/B000000001",
            source="Amazon Brasil — COLETA REAL",
        )
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            pipeline.return_value = ReportFiles(
                run_dir=run_dir,
                spreadsheet=run_dir / "comparativo_real.xlsx",
                chart=run_dir / "grafico_real.html",
                summary=run_dir / "resumo_execucao.json",
                mode="real",
                query="Notebook Dell G15",
                products=(product,),
            )
            send_email.side_effect = SmartPriceError("falha SMTP simulada")
            values = {
                "SMTP_USER": "remetente@gmail.com",
                "SMTP_PASSWORD": "senha-de-app",
            }
            with patch.dict(os.environ, values, clear=True):
                result = main(
                    [
                        "Notebook Dell G15",
                        "--modo",
                        "real",
                        "--email",
                        "destino@example.com",
                    ]
                )

        self.assertEqual(result, 3)
        pipeline.assert_called_once()
        send_email.assert_called_once()
        load_env.assert_called_once()

    def test_demo_report_has_own_directory_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            files = generate_reports(
                demo_products("notebook", 3),
                Path(directory),
                query="notebook",
                mode="demo",
            )
            self.assertEqual(files.run_dir.parent.name, "demo")
            self.assertTrue(files.spreadsheet.exists())
            self.assertTrue(files.chart.exists())
            self.assertTrue(files.summary.exists())
            summary = json.loads(files.summary.read_text(encoding="utf-8"))
            self.assertEqual(summary["execution"]["mode"], "demo")
            self.assertTrue(summary["execution"]["is_demo"])
            self.assertEqual(summary["execution"]["count"], 3)

    @patch("AutomateWeb.collect_with_selenium")
    @patch("AutomateWeb.discover_amazon_links")
    def test_real_mode_never_falls_back_to_demo(self, discover, collect):
        discover.return_value = ["https://www.amazon.com.br/dp/B000000001"]
        collect.return_value = [
            Product(
                name="Notebook real de teste",
                price=4999.90,
                rating=4.7,
                url="https://www.amazon.com.br/dp/B000000001",
                source="Amazon Brasil — COLETA REAL",
            )
        ]
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"SCRAPINGBEE_API_KEY": "test-key"}
        ):
            files = run_pipeline(
                "Notebook Dell G15",
                mode="real",
                limit=1,
                output_dir=Path(directory),
            )
            summary = json.loads(files.summary.read_text(encoding="utf-8"))
            self.assertEqual(files.run_dir.parent.name, "real")
            self.assertFalse(summary["execution"]["is_demo"])
            self.assertEqual(summary["execution"]["source"], "Amazon Brasil — COLETA REAL")
            self.assertIn("amazon.com.br", summary["products"][0]["Link"])
            self.assertNotIn("example.com", summary["products"][0]["Link"])
            discover.assert_called_once()
            collect.assert_called_once()


if __name__ == "__main__":
    unittest.main()

"""Smart Price Compare: coleta preços e gera relatórios comparativos.

O modo ``demo`` funciona sem rede, navegador ou credenciais. O modo ``real``
usa a ScrapingBee para descobrir produtos e o Selenium para ler as páginas.
Cada execução recebe uma pasta própria para nunca misturar dados reais e demo.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import smtplib
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import quote_plus

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "saida"
LOGGER = logging.getLogger("smart-price-compare")
CHART_LABEL_MAX_LENGTH = 48


class SmartPriceError(RuntimeError):
    """Erro esperado e apresentável ao usuário."""


@dataclass(frozen=True, slots=True)
class Product:
    """Produto normalizado, pronto para relatório."""

    name: str
    price: float
    rating: float | None
    url: str
    source: str


@dataclass(frozen=True, slots=True)
class ReportFiles:
    """Resultado completo de uma execução."""

    run_dir: Path
    spreadsheet: Path
    chart: Path
    summary: Path
    mode: str
    query: str
    products: tuple[Product, ...]


def load_env_file(path: Path | None = None) -> None:
    """Carrega CHAVE=VALOR do .env ao lado do script por padrão."""

    env_path = path or DEFAULT_ENV_FILE
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def parse_brl_price(value: str) -> float:
    """Converte textos como ``R$ 4.299,90`` ou ``4299.90`` para float."""

    cleaned = re.sub(r"[^0-9,.]", "", value)
    if not cleaned:
        raise ValueError(f"Preço inválido: {value!r}")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    return float(cleaned)


def parse_rating(value: str | None) -> float | None:
    """Extrai a nota de textos como ``4,7 de 5 estrelas``."""

    if not value:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", value)
    return float(match.group().replace(",", ".")) if match else None


def format_brl(value: float) -> str:
    """Formata número como moeda brasileira sem depender do locale do sistema."""

    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def shorten_label(value: str, max_length: int = CHART_LABEL_MAX_LENGTH) -> str:
    """Compacta um texto e limita seu tamanho para uso visual no gráfico."""

    if max_length < 2:
        raise ValueError("O limite do rótulo deve ser de pelo menos 2 caracteres.")
    compact = " ".join(str(value).split())
    if len(compact) <= max_length:
        return compact
    shortened = compact[: max_length - 1].rstrip()
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0].rstrip()
    return shortened + "…"


def is_unwanted_result(title: str, query: str) -> bool:
    """Remove acessórios, exceto quando o próprio usuário os pesquisou."""

    accessory_terms = {
        "capa",
        "capinha",
        "case",
        "película",
        "pelicula",
        "carregador",
        "suporte",
    }
    normalized_title = title.casefold()
    normalized_query = query.casefold()
    return any(
        term in normalized_title and term not in normalized_query
        for term in accessory_terms
    )


def demo_products(query: str, limit: int = 5) -> list[Product]:
    """Cria dados fictícios determinísticos para demonstração local."""

    count = max(1, min(limit, 10))
    base = 850 + (sum(map(ord, query.casefold())) % 500)
    return [
        Product(
            name=f"{query.title()} — opção fictícia {index + 1}",
            price=round(base * (1 + index * 0.087), 2),
            rating=round(4.1 + (index % 5) * 0.15, 1),
            url=f"https://example.com/demonstracao/{quote_plus(query)}/{index + 1}",
            source="DEMONSTRAÇÃO — DADOS FICTÍCIOS",
        )
        for index in range(count)
    ]


def discover_amazon_links(query: str, api_key: str, limit: int) -> list[str]:
    """Descobre URLs canônicas de produtos na busca da Amazon."""

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise SmartPriceError(
            "Dependências do modo real ausentes. Execute: pip install -r requirements.txt"
        ) from exc

    search_url = f"https://www.amazon.com.br/s?k={quote_plus(query)}"
    try:
        response = requests.get(
            "https://app.scrapingbee.com/api/v1",
            params={"api_key": api_key, "url": search_url, "render_js": "true"},
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SmartPriceError(f"Falha ao consultar a ScrapingBee: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    links: list[str] = []
    seen_asins: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        match = re.search(r"/dp/([A-Z0-9]{10})", href, flags=re.IGNORECASE)
        if not match:
            continue
        title = anchor.get_text(" ", strip=True)
        asin = match.group(1).upper()
        if asin in seen_asins or is_unwanted_result(title, query):
            continue
        seen_asins.add(asin)
        links.append(f"https://www.amazon.com.br/dp/{asin}")
        if len(links) >= limit:
            break

    if not links:
        raise SmartPriceError(
            "Nenhum produto foi encontrado. A página pode ter mudado ou bloqueado a coleta."
        )
    return links


def _first_text(driver: object, selectors: Iterable[str]) -> str | None:
    from selenium.webdriver.common.by import By

    for selector in selectors:
        for element in driver.find_elements(By.CSS_SELECTOR, selector):
            text = element.get_attribute("textContent") or element.get_attribute("title")
            if text and text.strip():
                return text.strip()
    return None


def collect_with_selenium(
    links: Sequence[str], *, headless: bool = True, wait_seconds: int = 15
) -> list[Product]:
    """Coleta nome, preço e avaliação mantendo cada registro consistente."""

    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        raise SmartPriceError(
            "Selenium não está instalado. Execute: pip install -r requirements.txt"
        ) from exc

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1200")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")

    products: list[Product] = []
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        for position, link in enumerate(links, start=1):
            LOGGER.info("Coletando produto real %s/%s", position, len(links))
            try:
                driver.get(link)
                WebDriverWait(driver, wait_seconds).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#productTitle"))
                )
                name = _first_text(driver, ["#productTitle"]) or f"Produto {position}"
                raw_price = _first_text(
                    driver,
                    [
                        "#corePrice_feature_div span.a-price span.a-offscreen",
                        "#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen",
                        "#apex_desktop span.a-price span.a-offscreen",
                        "span.a-price span.a-offscreen",
                    ],
                )
                if not raw_price:
                    LOGGER.warning("Preço não localizado em %s", link)
                    continue
                raw_rating = _first_text(
                    driver,
                    ["#acrPopover", "[data-hook='rating-out-of-text']", "span[data-hook='rating-out-of-text']"],
                )
                products.append(
                    Product(
                        name=name,
                        price=parse_brl_price(raw_price),
                        rating=parse_rating(raw_rating),
                        url=link,
                        source="Amazon Brasil — COLETA REAL",
                    )
                )
            except Exception as exc:  # uma página não deve interromper todo o lote
                LOGGER.warning("Produto real ignorado (%s): %s", link, exc)
    finally:
        if driver is not None:
            driver.quit()

    if not products:
        raise SmartPriceError("Nenhum produto real retornou um preço válido.")
    return products


def products_to_dataframe(products: Sequence[Product], query: str = "") -> pd.DataFrame:
    if not products:
        raise SmartPriceError("Não há produtos para gerar o relatório.")
    frame = pd.DataFrame(asdict(product) for product in products)
    frame = frame.rename(
        columns={
            "name": "Produto",
            "price": "Preço (R$)",
            "rating": "Avaliação",
            "url": "Link",
            "source": "Origem",
        }
    ).sort_values("Preço (R$)", ignore_index=True)
    if query:
        frame.insert(0, "Consulta", query)
    return frame


def _create_chart(frame: pd.DataFrame, run_dir: Path, mode: str, query: str) -> Path:
    """Gera gráfico legível sem remover títulos completos dos relatórios."""

    is_demo = mode == "demo"
    prefix = "DEMONSTRAÇÃO — DADOS FICTÍCIOS" if is_demo else "COLETA REAL — AMAZON BRASIL"
    color = "#f59e0b" if is_demo else "#2563eb"
    try:
        import plotly.express as px

        chart_path = run_dir / f"grafico_{mode}.html"
        chart_frame = frame.copy()
        chart_frame["Rótulo"] = [
            f"{index}. {shorten_label(product)}"
            for index, product in enumerate(chart_frame["Produto"], start=1)
        ]
        chart_frame["Título completo"] = chart_frame["Produto"].map(
            lambda value: html.escape(str(value))
        )
        chart_frame["Preço formatado"] = chart_frame["Preço (R$)"].map(format_brl)
        chart_frame["Avaliação exibida"] = chart_frame["Avaliação"].map(
            lambda value: "Não disponível" if pd.isna(value) else f"{float(value):.1f} de 5"
        )
        chart_frame["Origem exibida"] = chart_frame["Origem"].map(
            lambda value: html.escape(str(value))
        )
        figure = px.bar(
            chart_frame,
            x="Preço (R$)",
            y="Rótulo",
            orientation="h",
            title=(
                "Comparativo de preços"
                f"<br><sup>{prefix} · Consulta: {html.escape(query)}</sup>"
            ),
            text="Preço formatado",
            custom_data=[
                "Título completo",
                "Preço formatado",
                "Avaliação exibida",
                "Origem exibida",
            ],
            color_discrete_sequence=[color],
        )
        figure.update_traces(
            texttemplate="%{text}",
            textposition="auto",
            cliponaxis=False,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br><br>"
                "Preço: %{customdata[1]}<br>"
                "Avaliação: %{customdata[2]}<br>"
                "Origem: %{customdata[3]}<extra></extra>"
            ),
        )
        figure.update_layout(
            template="plotly_white",
            height=max(520, 210 + len(chart_frame) * 85),
            margin={"l": 370, "r": 90, "t": 110, "b": 70},
            bargap=0.35,
            hoverlabel={"align": "left"},
            title={"x": 0.02, "xanchor": "left"},
        )
        figure.update_yaxes(title_text=None, autorange="reversed", automargin=True)
        figure.update_xaxes(title_text="Preço (R$)", rangemode="tozero", tickprefix="R$ ")
        figure.write_html(
            chart_path,
            include_plotlyjs="cdn",
            config={"responsive": True, "displaylogo": False},
        )
        return chart_path
    except ImportError:
        import matplotlib.pyplot as plt

        chart_path = run_dir / f"grafico_{mode}.png"
        labels = [
            f"{index}. {shorten_label(product)}"
            for index, product in enumerate(frame["Produto"], start=1)
        ]
        figure, axis = plt.subplots(figsize=(12, max(5, 2 + len(frame) * 0.7)))
        bars = axis.barh(labels, frame["Preço (R$)"], color=color)
        axis.invert_yaxis()
        axis.set_title(f"[{prefix}] Comparativo: {query}")
        axis.set_xlabel("Preço (R$)")
        axis.bar_label(
            bars,
            labels=[format_brl(float(value)) for value in frame["Preço (R$)"]],
            padding=5,
        )
        figure.tight_layout()
        figure.savefig(chart_path, dpi=150)
        plt.close(figure)
        return chart_path


def generate_reports(
    products: Sequence[Product],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    query: str = "consulta",
    mode: str = "demo",
) -> ReportFiles:
    """Gera uma pasta exclusiva com Excel, gráfico e resumo JSON."""

    if mode not in {"demo", "real"}:
        raise SmartPriceError(f"Modo desconhecido: {mode}")
    generated_at = datetime.now().astimezone()
    run_id = generated_at.strftime("%Y%m%d_%H%M%S_%f")
    run_dir = output_dir / mode / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    frame = products_to_dataframe(products, query)
    source = "DEMONSTRAÇÃO — DADOS FICTÍCIOS" if mode == "demo" else "Amazon Brasil — COLETA REAL"
    spreadsheet = run_dir / f"comparativo_{mode}.xlsx"
    summary = run_dir / "resumo_execucao.json"

    metadata = pd.DataFrame(
        [
            ["Modo", mode.upper()],
            ["Dados fictícios", "SIM" if mode == "demo" else "NÃO"],
            ["Origem", source],
            ["Consulta", query],
            ["Data da execução", generated_at.isoformat()],
            ["Quantidade coletada", len(frame)],
        ],
        columns=["Campo", "Valor"],
    )
    with pd.ExcelWriter(spreadsheet, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Resultados", index=False)
        metadata.to_excel(writer, sheet_name="Execução", index=False)

    chart = _create_chart(frame, run_dir, mode, query)
    summary.write_text(
        json.dumps(
            {
                "execution": {
                    "run_id": run_id,
                    "generated_at": generated_at.isoformat(),
                    "mode": mode,
                    "is_demo": mode == "demo",
                    "query": query,
                    "source": source,
                    "count": len(frame),
                },
                "lowest_price": float(frame["Preço (R$)"].min()),
                "products": frame.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ReportFiles(
        run_dir=run_dir,
        spreadsheet=spreadsheet,
        chart=chart,
        summary=summary,
        mode=mode,
        query=query,
        products=tuple(products),
    )


def read_smtp_settings() -> tuple[str, int, str, str, bool]:
    """Lê e valida o SMTP antes que uma coleta paga seja iniciada."""

    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    raw_port = os.getenv("SMTP_PORT", "587").strip()
    sender = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    if not sender or not password:
        raise SmartPriceError(
            "Para enviar e-mail, configure SMTP_USER e SMTP_PASSWORD no arquivo .env. "
            "No Gmail, use uma senha de app em SMTP_PASSWORD, não a senha normal."
        )
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise SmartPriceError("SMTP_PORT deve conter um número, por exemplo 587.") from exc
    if not host or not 1 <= port <= 65535:
        raise SmartPriceError("Configure SMTP_HOST e uma SMTP_PORT válida no arquivo .env.")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
    return host, port, sender, password, use_tls


def send_email(recipient: str, query: str, files: ReportFiles) -> None:
    """Envia o relatório usando configurações SMTP do ambiente."""

    host, port, sender, password, use_tls = read_smtp_settings()

    mode_label = "DEMO — DADOS FICTÍCIOS" if files.mode == "demo" else "COLETA REAL"
    message = EmailMessage()
    message["Subject"] = f"[{mode_label}] Comparativo de preços: {query}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Olá!\n\nModo da execução: {mode_label}.\n"
        "Seguem anexos os resultados do Smart Price Compare.\n"
        "Preços reais podem mudar; confirme-os no site antes da compra."
    )
    for path in (files.spreadsheet, files.chart, files.summary):
        maintype, subtype = "application", "octet-stream"
        if path.suffix == ".html":
            maintype, subtype = "text", "html"
        elif path.suffix == ".png":
            maintype, subtype = "image", "png"
        elif path.suffix == ".json":
            maintype, subtype = "application", "json"
        with path.open("rb") as attachment:
            message.add_attachment(
                attachment.read(), maintype=maintype, subtype=subtype, filename=path.name
            )

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls()
            smtp.login(sender, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise SmartPriceError(f"Não foi possível enviar o e-mail: {exc}") from exc


def run_pipeline(
    query: str,
    *,
    mode: str = "demo",
    limit: int = 5,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    recipient: str | None = None,
    headless: bool = True,
) -> ReportFiles:
    """Executa o fluxo completo sem permitir fallback silencioso entre modos."""

    query = query.strip()
    if not query:
        raise SmartPriceError("Informe um produto para pesquisar.")
    limit = max(1, min(limit, 10))
    if recipient:
        read_smtp_settings()

    if mode == "demo":
        LOGGER.info("MODO DEMO: gerando dados fictícios identificados como demonstração")
        products = demo_products(query, limit)
    elif mode == "real":
        LOGGER.info("MODO REAL: consultando ScrapingBee e coletando dados da Amazon Brasil")
        api_key = os.getenv("SCRAPINGBEE_API_KEY", "")
        if not api_key:
            raise SmartPriceError(
                f"Configure SCRAPINGBEE_API_KEY em {DEFAULT_ENV_FILE}."
            )
        links = discover_amazon_links(query, api_key, limit)
        products = collect_with_selenium(links, headless=headless)
    else:
        raise SmartPriceError(f"Modo desconhecido: {mode}")

    files = generate_reports(products, output_dir, query=query, mode=mode)
    if recipient:
        send_email(recipient, query, files)
    return files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coleta e compara preços, gerando Excel, gráfico e JSON."
    )
    parser.add_argument("produto", nargs="?", help="produto pesquisado")
    parser.add_argument("--modo", choices=("demo", "real"), default="demo")
    parser.add_argument("--limite", type=int, default=5, help="de 1 a 10 resultados")
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--email", help="destinatário; se omitido, não envia e-mail")
    parser.add_argument("--mostrar-navegador", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser


def _configure_logging(debug: bool) -> None:
    """Mostra logs do aplicativo no stdout sem ativar debug de bibliotecas HTTP."""

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    LOGGER.handlers.clear()
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.DEBUG if debug else logging.INFO)
    LOGGER.propagate = False


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.debug)
    load_env_file()
    product = args.produto
    if not product and sys.stdin.isatty():
        product = input("Digite o nome do produto: ").strip()
    if not product:
        print("ERRO: informe o produto. Use --help para ver as opções.", file=sys.stderr)
        return 2

    if args.email:
        try:
            read_smtp_settings()
        except SmartPriceError as exc:
            print(f"ERRO: {exc}", file=sys.stderr)
            print(
                "A coleta não foi iniciada, evitando consumo de créditos da ScrapingBee.",
                file=sys.stderr,
            )
            return 1

    try:
        files = run_pipeline(
            product,
            mode=args.modo,
            limit=args.limite,
            output_dir=args.saida,
            headless=not args.mostrar_navegador,
        )
    except SmartPriceError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    label = "DEMONSTRAÇÃO — DADOS FICTÍCIOS" if files.mode == "demo" else "COLETA REAL — AMAZON BRASIL"
    print(f"\nMODO: {label}")
    print(f"CONSULTA: {files.query}")
    print(f"PRODUTOS COLETADOS: {len(files.products)}")
    for index, result in enumerate(files.products, start=1):
        rating = f" | avaliação {result.rating:.1f}" if result.rating is not None else ""
        print(f"{index}. {result.name} | {format_brl(result.price)}{rating}")
        print(f"   {result.url}")
    print("\nARQUIVOS DESTA EXECUÇÃO:")
    for path in (files.spreadsheet, files.chart, files.summary):
        print(f"- {path.resolve()}")
    if args.email:
        try:
            send_email(args.email, product, files)
        except SmartPriceError as exc:
            print(
                f"\nAVISO: os relatórios foram gerados, mas o e-mail não foi enviado: {exc}",
                file=sys.stderr,
            )
            print("Os arquivos locais acima continuam válidos.", file=sys.stderr)
            return 3
        print(f"E-mail enviado para {args.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

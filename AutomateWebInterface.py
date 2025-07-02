import pandas as pd
import requests
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import plotly.express as px

from bs4 import BeautifulSoup
import dadosPrivados
import random
import smtplib
from email.message import EmailMessage
from time import sleep


API_KEY = dadosPrivados.chaveApiScrapingBee()
LinksProd = []

nomeProduto = sys.argv[1]
email2 = sys.argv[2]

navegador = webdriver.Chrome()
valorProd = []
avaliacoesProd = []
dadosCompletos = {
    "Preço": valorProd,
    "Avaliações": avaliacoesProd,
    "Link Produto": LinksProd
}


url = f"https://www.amazon.com.br/s?k={nomeProduto}"

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/109.0",
]

agentesSelecionados = random.choice(user_agents)

params = {
    "api_key": API_KEY,
    "url": url,
    "render_js": "true", 
    # "stealth_proxy": "true",
    # "custom_headers": f'{{"User-Agent": "{agentesSelecionados}"}}'
}

response = requests.get("https://app.scrapingbee.com/api/v1", params=params)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        if "/dp/" in link['href']:

            titulo = link.get_text(strip=True).lower()
            indesejado = ["capinha", "capa", "case", "pelicula", "capinhas", "capas", "cases", "peliculas", "motorola", "xiaomi", "iphone"]
            if nomeProduto != indesejado:
                indesejado = ["capinha", "capa", "case", "pelicula", "capinhas", "capas", "cases", "peliculas", "motorola", "xiaomi", "iphone"]
                if any(palavra in titulo for palavra in indesejado):
                    continue

            full_link = f"https://www.amazon.com.br{link['href'].split('?')[0]}"

            def acessoPreco():
                navegador.get(full_link)

                try:
                    WebDriverWait(navegador, 5).until(
                        EC.visibility_of_element_located((By.XPATH, '//*[@id="corePriceDisplay_desktop_feature_div"]/div[1]/span[2]/span[2]/span[2]'))
                    )

                    return True

                except TimeoutException as erroTimeout:

                    return False
                    

            if acessoPreco() == True:
                LinksProd.append(full_link)
            else:
                continue

            if len(LinksProd) == 10:
                break
    
    print("Links Encontrados: ")
    for link in LinksProd:
        print(f"-------> {link} <-------")


    
for linksCel in LinksProd:
    navegador.get(linksCel)

    cPreco = 0
    cAvaliacao = 0

    try:
        sleep(3)
        print()

        print(f"Acessando VALOR: {linksCel}")
        elemento01 = WebDriverWait(navegador, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="corePriceDisplay_desktop_feature_div"]/div[1]/span[2]/span[2]/span[2]'))
        )

        cPreco += 1

        texto_elemento01 = elemento01.text
        valorProd.append(texto_elemento01)

    except Exception as erro:
        print(f"Não foi possível acessar o {cPreco}° XPATH do elemento. {erro}")

        try:
            print(f"Vamos tentar por um XPATH mais genérico e menos propenso a mudanças...")
            elemento03 = WebDriverWait(navegador, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//div[@id="corePriceDisplay_desktop_feature_div"]//span[contains(@class, "a-price-whole")]'))
            )

            cPreco += 1
            texto_elemento03 = elemento03.text
            valorProd.append(texto_elemento03)

        except Exception as erro:
            print(f"Não foi possível acessar o {cPreco}° XPATH GENÉRICO do elemento. {erro}")

            try:
                print(f"Vamos tentar pelo CSS_SELECTOR...")
                elemento05 = WebDriverWait(navegador, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '#corePriceDisplay_desktop_feature_div > div.a-section.a-spacing-none.aok-align-center.aok-relative > span.a-price.aok-align-center.reinventPricePriceToPayMargin.priceToPay > span:nth-child(2) > span.a-price-whole'))
                )

                cPreco += 1
                texto_elemento05 = elemento05.text
                valorProd.append(texto_elemento05)
                
            except Exception as erro:
                print(f"Não foi possível acessar o {cPreco}° CSS_SELECTOR do elemento. {erro}")
            

    try:
        sleep(3)
        print()
        print(f"Acessando AVALIAÇÃO: {linksCel}")
        elemento02 = WebDriverWait(navegador, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="acrPopover"]/span/a/span'))
        )

        cAvaliacao += 1
        texto_elemento02 = elemento02.text
        avaliacoesProd.append(texto_elemento02)

    except Exception as erro:
        print(f"Não foi possível acessar o {cAvaliacao}° XPATH do elemento. {erro}")

        try:
            elemento04 = WebDriverWait(navegador, 10).until(
                EC.visibility_of_element_located((By.XPATH, '//div[@id="acrPopover"]//span[contains(@class, "a-size-small a-color-base")]'))
            )

            cAvaliacao += 1
            texto_elemento04 = elemento04.text
            avaliacoesProd.append(texto_elemento04)

        except Exception as erro:
            print(f"Não foi possível acessar o {cAvaliacao}° XPATH GENÉRICO do elemento. {erro}")

            try:
                elemento06 = WebDriverWait(navegador, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '#acrPopover > span > a > span'))
                )

                cAvaliacao += 1
                texto_elemento06 = elemento06.text
                avaliacoesProd.append(texto_elemento06)

            except Exception as erro:
                print(f"Não foi possível acessar o {cAvaliacao}° CSS_SELECTOR do elemento. {erro}")


    print(valorProd)
    print(avaliacoesProd)
    
print(dadosCompletos)


tabela = pd.DataFrame.from_dict(dadosCompletos, orient="columns")

df = pd.DataFrame(tabela)

# df.to_excel("AutomateWeb", index=False)

print(f"Dados do produto: {nomeProduto}")
print(df)

df["Produto"] = [f"{nomeProduto} {i+1}" for i in range(len(df))]

df["Preço"] =  df["Preço"].astype(float)

fig = px.bar(df,  
             x="Produto", 
             y="Preço", 
             title=f"Comparativo de Preços - {nomeProduto}",
             labels={"Preço": "Preço (R$)", "Link Produto": "Produto"},
             text="Preço")

fig.update_layout(
    yaxis=dict(range=[0, df["Preço"].max() + 1]),
    xaxis_tickangle=-45
)

fig.write_image("grafico_comparativo.png")
fig.show()

def enviar_email():
    bodyEmail = """
    <p>Olá, Tudo bem?!</p>
    <hr>
    <p>Estamos felizes em enviar as informações que você solicitou sobre o produto!</p>
    <p>Segue abaixo a tabela com os detalhes dos produtos disponíveis, incluindo nomes e links para compra.
    Além disso, anexamos um gráfico interativo para facilitar a visualização dos dados.</p>
    <p>Qualquer dúvida, estamos à disposição!</p>
    <p>Atenciosamente,<br>Equipe <strong>Diagonal</strong> 🚀</p> 
    """

    msg = EmailMessage()
    emails = dadosPrivados.dadosEmail()

    msg['Subject'] = f"Informações do {nomeProduto}!"
    msg['From'] = emails["email1"]
    msg['To'] = email2

    senhaEmail = emails["code"]

    msg.add_header('Content-Type', 'text/html')
    msg.set_payload(bodyEmail)

    on = smtplib.SMTP('smtp.gmail.com', 587)
    on.starttls()

    on.login(msg['From'], senhaEmail)

    with open("AutomateWeb.xlsx", "rb") as f:
        msg.add_attachment(f.read(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename='AutomateWeb.xlsx')
    
    with open("grafico_comparativo.png", "rb") as f:
        msg.add_attachment(f.read(), maintype='image', subtype='png', filename='grafico_comparativo.png')

    try:
        on.sendmail(msg['From'], [msg['To']], msg.as_string().encode('utf-8'))
        print('Email Enviado!')
    except Exception as e:
        print(f'Ocorreu um erro: {e}')

enviar_email()

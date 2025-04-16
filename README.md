# comparativoPreco
Ferramenta automatizada de comparação de preços e avaliações de produtos (Amazon) usando Python, Web Scraping e envio de e-mail com análise gráfica.

# 🛒 Smart Price Compare

Ferramenta desenvolvida em Python para automatizar a busca por preços e avaliações de produtos, a partir de uma pesquisa feita pelo usuário. Ideal para quem deseja tomar decisões de compra mais inteligentes e informadas.

---

## 🚀 Funcionalidades

✅ Captura automática dos produtos com base em um termo de busca  
✅ Extração dos **links reais** dos produtos diretamente da Amazon  
✅ Acesso aos produtos com **Selenium**, evitando bloqueios e captchas  
✅ Coleta de **preço** e **avaliação** de cada item  
✅ Organização dos dados em **tabela (Pandas)**  
✅ Geração de **gráfico comparativo** com Plotly  
✅ Envio de e-mail com os resultados anexados (tabela + gráfico)

---

## 🧪 Tecnologias Utilizadas

- 🧠 **Python 3**
- 🕷️ **ScrapingBee API RESTful** – simula navegador e evita bloqueios
- 🥣 **BeautifulSoup** – transforma HTML em dados legíveis
- 🌐 **Selenium** – acessa links, extrai dados e interage com a página
- 📊 **Pandas** – organiza e exporta os dados em .xlsx
- 📈 **Plotly** – gera gráficos comparativos com visual moderno
- 📬 **smtplib + EmailMessage** – envia e-mail com os anexos

---

📎 Exemplo de Saída
Tabela Excel com os dados coletados

Gráfico de comparação de preços

Ambos os arquivos são enviados por e-mail automaticamente

---

🤖 Próximos passos
 Suporte a outros e-commerces (Mercado Livre, Magazine Luiza)

 Interface gráfica com Tkinter ou Flask

 Deploy web com formulário de entrada

 ---

 🧑‍💻 Autor
Desenvolvido por Carlos Vinícius – apaixonado por automações, scraping e soluções inteligentes para o dia a dia.
Conecte-se comigo no LinkedIn -> https://www.linkedin.com/in/vin%C3%ADcius-domingos-12a50b325/

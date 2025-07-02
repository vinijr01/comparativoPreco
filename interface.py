import flet as ft
import subprocess

# componentes que serão inicializados
def main (page: ft.Page):
    page.bgcolor = '#000000'
    page.scroll = ft.ScrollMode.AUTO

    def change_main_image(e):
        for elem in options.controls:
            if elem == e.control:
                elem.opacity = 1
                main_image.src = elem.content.src
            else:
                elem.opacity = 0.5

        main_image.update()
        options.update()

    snackbar = ft.SnackBar(
        content=ft.Text(""),
        bgcolor=ft.Colors.GREEN,
        behavior=ft.SnackBarBehavior.FLOATING,
        show_close_icon=True,
        duration=2000  # em ms
    )

    page.snack_bar = snackbar
    page.overlay.append(snackbar)

    def executar_script_automacao(e):
        try:
            nome = nome_produto.value.strip()
            email = email_destino.value.strip()

            if not nome or not email:
                snackbar.content.value = "⚠️ Preencha todos os campos!"
                snackbar.bgcolor = ft.Colors.ORANGE
                page.show_snack_bar()
                return

            subprocess.run(["python", "AutomateWebInterface.py", nome, email], check=True)

            snackbar.content.value = "✅ Script executado com sucesso!"
            snackbar.bgcolor = ft.Colors.GREEN
            page.show_snack_bar()

        except subprocess.CalledProcessError as err:
            snackbar.content.value = f"❌ Erro ao executar o script!"
            snackbar.bgcolor = ft.Colors.RED
            page.show_snack_bar()



    product_images =  ft.Container(
        col={'xs': 12, 'md': 6},
        bgcolor=ft.Colors.WHITE,
        padding=ft.padding.all(30),
        aspect_ratio=9/16,

        content=ft.Column(
            # alignment= ft.MainAxisAlignment.CENTER,
            controls=[
                main_image := ft.Image(
                    src="imagens/imagemPrincipal1.png",
                ),

                options := ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            content=ft.Image(
                                src="imagens/8.png",
                                width=80,
                                height=80,
                                opacity=1,
                            ),
                            on_click=change_main_image
                        ),

                        ft.Container(
                            content=ft.Image(
                                src="imagens/9.png",
                                width=80,
                                height=80,
                                opacity=1,
                            ),
                            on_click=change_main_image
                        ),

                        ft.Container(
                            content=ft.Image(
                                src="imagens/10.png",
                                width=80,
                                height=80,
                                opacity=1,
                            ),
                            on_click=change_main_image
                        ),
                    ]
                )
            ]
        )
    )
    product_details = ft.Container(
        col={'xs': 12, 'md': 6},
        padding= ft.padding.all(30),
        bgcolor = ft.Colors.BLACK87,
        aspect_ratio=9/16,

        content=ft.Column(
            controls=[
                ft.Text(
                    value='PRODUTOS',
                    color=ft.Colors.BLUE,
                    weight=ft.FontWeight.BOLD
                ),

                ft.Text(
                    value='Preços com Descontos',
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                    size=30
                ),

                ft.Text(
                    value='Um pesquisador de preços onde você escreve o nome do produto e ele te retorna o mais em conta!',
                    color=ft.Colors.GREY,
                    italic=True
                ),

                ft.Tabs (
                    selected_index=1,
                    indicator_color=ft.Colors.BLUE,
                    label_color=ft.Colors.BLUE,
                    height=150,
                    # unselected_label_color=ft.Colors.GREY,

                    tabs=[
                        ft.Tab(
                            text='Descrição',
                            content=ft.Container(
                                padding=ft.padding.all(10),
                                content=ft.Text(
                                    value="""
Este software foi desenvolvido para ajudar consumidores a compararem preços e avaliações de produtos em tempo real.

A aplicação automatiza a coleta de informações de sites como a Amazon, usando tecnologias modernas como:

🔹 ScrapingBee API – para obter o conteúdo da página HTML, mesmo com JavaScript dinâmico  
🔹 BeautifulSoup – para extrair os links corretos dos produtos  
🔹 Selenium – para acessar os links e coletar dados de preços e avaliações  
🔹 Pandas – para organizar os dados em formato tabular  
🔹 Plotly – para gerar gráficos comparativos de preços  
🔹 Envio por e-mail – o usuário recebe automaticamente a tabela e o gráfico com os resultados

O objetivo principal é economizar tempo do usuário e facilitar decisões de compra com base em dados reais e atualizados.
"""
                                )
                            )
                        ),

                        ft.Tab(
                            text='Como Usar?',
                                content=ft.Container(
                                padding=ft.padding.all(10),
                                content=ft.Text(
                                    value="""
1- Digite no campo de busca o nome do produto que você deseja comparar (ex: "Samsung S24").

2- O software fará todo o trabalho:
-> Acessa a Amazon
-> Captura os links dos produtos mais relevantes
-> Extrai automaticamente os preços e avaliações

3- Em poucos segundos, você verá uma tabela com os dados e um gráfico comparativo dos preços.

4- Por fim, você poderá enviar as informações para seu e-mail com apenas 1 clique.

Dica: verifique sua conexão com a internet para garantir que o carregamento dos dados ocorra corretamente.
"""
                                )
                            )
                        )
                    ]
                ),
                ft.ResponsiveRow(
                    columns=12,
                    controls=[
                        nome_produto := ft.TextField(
                            col=6,
                            label="Digite o nome do produto",
                            label_style=ft.TextStyle(color=ft.Colors.WHITE, size=12),
                            hint_text="Ex: Samsung S24",
                            border_color=ft.Colors.BLUE,
                            focused_border_color="deeporange600",
                            on_change=lambda e: print(f"Texto digitado: {e.control.value}")
                        ),

                        email_destino := ft.TextField(
                            col=6,
                            label="Digite o e-mail que receberá",
                            label_style=ft.TextStyle(color=ft.Colors.WHITE, size=12),
                            hint_text="Ex: myemail@email.com",
                            border_color=ft.Colors.BLUE,
                            focused_border_color="deeporange600",
                            on_change=lambda e: print(f"Texto digitado: {e.control.value}")
                        )
                    ]
                ),

                ft.Container(
                    margin=ft.margin.only(top=30),
                    content=ft.ElevatedButton(
                        width=900,
                        text="Pesquisar",
                        on_click=executar_script_automacao,
                        style=ft.ButtonStyle(
                            padding=ft.Padding(20, 20, 20, 20),
                            side=ft.BorderSide(width=2, color=ft.Colors.BLUE),
                            color=ft.Colors.BLUE,
                            bgcolor=ft.Colors.WHITE,
                        ),
                    )
                )
            ]
        )
    )

    layout = ft.Container (
        # configurações para layout da interface
        width= 900,
        margin= ft.margin.all(30),
        shadow= ft.BoxShadow(blur_radius=300, color=ft.Colors.CYAN),

        # dados dentro da interface
        content=ft.ResponsiveRow (
            # componentes de responsividade e espaços
            columns= 12,
            spacing= 0,
            run_spacing= 0,
            controls= [
                product_images,
                product_details
            ]
        )
    )

    page.add(layout)

if __name__ == '__main__':
    # gera a aplicação = onde estão todos os detalhes
    ft.app(target=main)
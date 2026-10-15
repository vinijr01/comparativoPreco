"""Interface desktop do Smart Price Compare construída com Flet."""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import flet as ft


AUTOMATION_SCRIPT = Path(__file__).with_name("AutomateWebInterface.py")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def main(page: ft.Page) -> None:
    page.title = "Smart Price Compare"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#07111f"
    page.padding = 24
    page.scroll = ft.ScrollMode.AUTO

    title = ft.Text("Smart Price Compare", size=34, weight=ft.FontWeight.BOLD)
    subtitle = ft.Text(
        "Automação RPA para coletar, organizar e comparar preços.",
        color="#a8b3c7",
        size=16,
    )
    product_field = ft.TextField(
        label="Produto",
        hint_text="Ex.: notebook para trabalho",
        autofocus=True,
        prefix_icon=ft.Icons.SEARCH,
    )
    mode_field = ft.Dropdown(
        label="Modo de execução",
        value="demo",
        options=[
            ft.dropdown.Option("demo", "DEMO — dados fictícios, sem API"),
            ft.dropdown.Option("real", "REAL — Amazon via ScrapingBee + Selenium"),
        ],
    )
    mode_notice_text = ft.Text(
        "DEMONSTRAÇÃO: os resultados serão fictícios e identificados como tal.",
        color="#fbbf24",
        weight=ft.FontWeight.W_600,
    )
    mode_notice = ft.Container(
        padding=12,
        border_radius=8,
        bgcolor="#3a2a0b",
        content=mode_notice_text,
    )

    def update_mode_notice(event: ft.ControlEvent) -> None:
        del event
        if mode_field.value == "real":
            mode_notice_text.value = (
                "COLETA REAL: os relatórios mostrarão Amazon Brasil como origem."
            )
            mode_notice_text.color = "#86efac"
            mode_notice.bgcolor = "#12351f"
        else:
            mode_notice_text.value = (
                "DEMONSTRAÇÃO: os resultados serão fictícios e identificados como tal."
            )
            mode_notice_text.color = "#fbbf24"
            mode_notice.bgcolor = "#3a2a0b"
        page.update()

    mode_field.on_change = update_mode_notice
    limit_field = ft.Slider(min=1, max=10, divisions=9, value=5, label="{value}")
    show_browser_field = ft.Checkbox(
        label="Mostrar o Chrome durante a coleta real",
        value=False,
    )
    email_field = ft.TextField(
        label="E-mail destinatário (opcional)",
        hint_text="O remetente e a senha de app são lidos do arquivo .env",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
    )
    status = ft.Text("Pronto para executar.", color="#a8b3c7", selectable=True)
    progress = ft.ProgressBar(visible=False, color="#38bdf8")

    def show_message(message: str, color: str) -> None:
        page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    async def run_automation(event: ft.ControlEvent) -> None:
        del event
        product = (product_field.value or "").strip()
        recipient = (email_field.value or "").strip()
        if not product:
            show_message("Informe o produto que deseja pesquisar.", "#b45309")
            return
        if recipient and not EMAIL_PATTERN.match(recipient):
            show_message("Informe um e-mail válido ou deixe o campo vazio.", "#b45309")
            return

        run_button.disabled = True
        progress.visible = True
        status.value = "Executando a automação..."
        page.update()

        command = [
            sys.executable,
            str(AUTOMATION_SCRIPT),
            product,
            "--modo",
            mode_field.value or "demo",
            "--limite",
            str(int(limit_field.value or 5)),
        ]
        if recipient:
            command.extend(["--email", recipient])
        if mode_field.value == "real" and show_browser_field.value:
            command.append("--mostrar-navegador")

        child_environment = os.environ.copy()
        child_environment["PYTHONUTF8"] = "1"

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(AUTOMATION_SCRIPT.parent),
            env=child_environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        run_button.disabled = False
        progress.visible = False

        if process.returncode == 0:
            status.value = stdout.decode("utf-8", errors="replace").strip()
            selected_mode = "reais" if mode_field.value == "real" else "de demonstração"
            show_message(f"Relatórios {selected_mode} gerados com sucesso.", "#15803d")
        else:
            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()
            message = "\n".join(part for part in (output, error) if part)
            status.value = message or "A execução falhou sem detalhes."
            if process.returncode == 3:
                show_message(
                    "Relatórios gerados, mas não foi possível enviar o e-mail.",
                    "#b45309",
                )
            else:
                show_message("Não foi possível concluir a execução.", "#b91c1c")
        page.update()

    run_button = ft.ElevatedButton(
        "Gerar comparação",
        icon=ft.Icons.PLAY_ARROW_ROUNDED,
        on_click=run_automation,
        style=ft.ButtonStyle(
            bgcolor="#2563eb",
            color="#ffffff",
            padding=18,
        ),
    )

    card = ft.Container(
        width=760,
        padding=30,
        border_radius=18,
        bgcolor="#111c2e",
        border=ft.border.all(1, "#24324a"),
        content=ft.Column(
            spacing=18,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color="#38bdf8", size=42),
                        ft.Column([title, subtitle], spacing=2, expand=True),
                    ]
                ),
                ft.Divider(color="#24324a"),
                product_field,
                mode_field,
                mode_notice,
                ft.Text("Quantidade máxima de resultados", weight=ft.FontWeight.W_600),
                limit_field,
                show_browser_field,
                email_field,
                run_button,
                progress,
                ft.Container(
                    padding=16,
                    border_radius=10,
                    bgcolor="#0b1525",
                    content=status,
                ),
                ft.Text(
                    "Cada execução recebe uma pasta própria em saida/demo ou saida/real. "
                    "Assim, relatórios antigos nunca são confundidos com a coleta atual.",
                    size=12,
                    color="#8291aa",
                ),
            ],
        ),
    )
    page.add(ft.Row([card], alignment=ft.MainAxisAlignment.CENTER))


if __name__ == "__main__":
    ft.app(target=main)

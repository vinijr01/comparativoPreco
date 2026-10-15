"""Entrada de linha de comando mantida por compatibilidade.

O projeto antigo duplicava toda a automação neste arquivo. Agora a regra de
negócio vive em ``AutomateWeb.py`` e esta entrada apenas a reutiliza.
"""

from AutomateWeb import main


if __name__ == "__main__":
    raise SystemExit(main())

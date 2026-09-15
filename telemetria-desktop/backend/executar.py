#!/usr/bin/env python3
"""
Porta de entrada do backend; so chama o main() de telemetria.api.
Use --sim para a fonte simulada, --recalcular para os agregados antigos.
"""
from telemetria.api import main

if __name__ == "__main__":
    main()

"""consistencia: ano de fabricacao e modelo, placa, texto e checks

Revision ID: 0008
Revises: 0007

O que muda:

- `veiculo.ano` vira `ano_modelo`, e nasce `ano_fabricacao`, preenchido com
  o proprio ano do modelo nos carros que ja existem - e o unico valor que
  passa no CHECK sem inventar nada. O teto (ano corrente) NAO e CHECK: com
  data atual dentro, a restricao mudaria de significado sozinha.
- Texto opcional vazio vira NULL (`placa`, `motor`, `contato`,
  `observacao`), e o texto existente e normalizado como a entrada faz
  agora: sem espaco nas pontas, sem espaco repetido.
- Placa fora do padrao (antigo ABC1234 ou Mercosul ABC1D23) vira NULL. Nao
  ha como corrigir uma placa errada sem adivinhar; NULL e o "nao sei"
  honesto, e a pessoa preenche de novo pela edicao do carro.
- E-mail: CHECK de minusculas e indice unico em lower(email).
- CHECKs de integridade em veiculo, cliente, usuario, sessao e
  tokenacesso. A tabela `amostra` fica sem CHECK de proposito: dado
  estranho de sensor nao pode fazer o INSERT falhar no meio da gravacao.

O downgrade desfaz a estrutura. As placas anuladas nao voltam - o valor
invalido nao foi guardado em lugar nenhum. E o downgrade devolve "" as
colunas opcionais, entao falha se uma conta tiver dois carros ativos sem
placa (o indice unico antigo tratava "" como placa repetida).

SQL congelado, sem importar nada de `telemetria/`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalizar(tabela: str, coluna: str, opcional: bool) -> None:
    """Corta as pontas e colapsa espaco repetido; opcional vazio vira NULL."""
    limpo = f"btrim(regexp_replace({coluna}, '\\s+', ' ', 'g'))"
    valor = f"NULLIF({limpo}, '')" if opcional else limpo
    op.execute(f"UPDATE {tabela} SET {coluna} = {valor} WHERE {coluna} IS NOT NULL")


def _texto_ck(coluna: str, opcional: bool) -> str:
    base = f"{coluna} <> '' AND {coluna} = btrim({coluna})"
    return f"{coluna} IS NULL OR ({base})" if opcional else base


def upgrade() -> None:
    # --- ano de fabricacao e ano do modelo
    op.alter_column("veiculo", "ano", new_column_name="ano_modelo")
    op.add_column("veiculo", sa.Column("ano_fabricacao", sa.Integer(), nullable=True))
    op.execute("UPDATE veiculo SET ano_fabricacao = ano_modelo")
    op.alter_column("veiculo", "ano_fabricacao", nullable=False)
    op.create_check_constraint(
        "ck_veiculo_ano_fabricacao_piso", "veiculo", "ano_fabricacao >= 1950"
    )
    op.create_check_constraint(
        "ck_veiculo_ano_modelo",
        "veiculo",
        "ano_modelo = ano_fabricacao OR ano_modelo = ano_fabricacao + 1",
    )

    # --- placa: opcional de verdade, e no formato
    op.alter_column("veiculo", "placa", nullable=True)
    op.execute(
        "UPDATE veiculo SET placa = NULL "
        "WHERE placa !~ '^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'"
    )
    op.create_check_constraint(
        "ck_veiculo_placa_formato",
        "veiculo",
        "placa IS NULL OR placa ~ '^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'",
    )

    # --- texto curto
    for tabela, coluna in (("veiculo", "motor"), ("cliente", "contato"), ("sessao", "observacao")):
        op.alter_column(tabela, coluna, nullable=True)
        _normalizar(tabela, coluna, opcional=True)
        op.create_check_constraint(f"ck_{tabela}_{coluna}", tabela, _texto_ck(coluna, True))
    for tabela in ("cliente", "usuario"):
        _normalizar(tabela, "nome", opcional=False)
        op.create_check_constraint(f"ck_{tabela}_nome", tabela, _texto_ck("nome", False))

    op.create_check_constraint("ck_veiculo_quilometragem", "veiculo", "quilometragem >= 0")

    # --- e-mail sem diferenciar maiusculas
    op.execute("UPDATE usuario SET email = lower(btrim(email))")
    op.create_check_constraint("ck_usuario_email_minusculo", "usuario", "email = lower(email)")
    op.create_index(
        "ux_usuario_email_lower", "usuario", [sa.text("lower(email)")], unique=True
    )

    # --- sessao
    op.create_check_constraint(
        "ck_sessao_encerramento",
        "sessao",
        "encerrada_em IS NULL OR encerrada_em >= iniciada_em",
    )
    op.create_check_constraint(
        "ck_sessao_status", "sessao", "(status = 'ATIVA') = (encerrada_em IS NULL)"
    )
    op.create_check_constraint(
        "ck_sessao_agregados",
        "sessao",
        "(total_amostras IS NULL OR total_amostras >= 0)"
        " AND (amostras_completas IS NULL OR amostras_completas >= 0)"
        " AND (amostras_completas IS NULL OR total_amostras IS NULL"
        " OR amostras_completas <= total_amostras)"
        " AND (rpm_pico IS NULL OR rpm_pico >= 0)"
        " AND (vss_pico IS NULL OR vss_pico >= 0)",
    )
    op.create_check_constraint(
        "ck_sessao_limites",
        "sessao",
        "(limite_shift_light_rpm IS NULL OR limite_shift_light_rpm > 0)"
        " AND (limite_rpm_alto IS NULL OR limite_rpm_alto > 0)"
        " AND (limite_temp_alta_c IS NULL OR limite_temp_alta_c > 0)"
        " AND (limite_vbat_baixa IS NULL OR limite_vbat_baixa > 0)"
        " AND (limite_rpm_marcha_lenta IS NULL OR limite_rpm_marcha_lenta > 0)"
        " AND (limite_ect_operacao_c IS NULL OR limite_ect_operacao_c > 0)",
    )

    # --- token
    op.create_check_constraint("ck_tokenacesso_validade", "tokenacesso", "expira_em > criado_em")


def downgrade() -> None:
    op.drop_constraint("ck_tokenacesso_validade", "tokenacesso", type_="check")
    for nome in ("ck_sessao_limites", "ck_sessao_agregados", "ck_sessao_status",
                 "ck_sessao_encerramento"):
        op.drop_constraint(nome, "sessao", type_="check")

    op.drop_index("ux_usuario_email_lower", table_name="usuario")
    op.drop_constraint("ck_usuario_email_minusculo", "usuario", type_="check")
    op.drop_constraint("ck_veiculo_quilometragem", "veiculo", type_="check")

    for tabela in ("cliente", "usuario"):
        op.drop_constraint(f"ck_{tabela}_nome", tabela, type_="check")
    for tabela, coluna in (("veiculo", "motor"), ("cliente", "contato"), ("sessao", "observacao")):
        op.drop_constraint(f"ck_{tabela}_{coluna}", tabela, type_="check")
        op.execute(f"UPDATE {tabela} SET {coluna} = '' WHERE {coluna} IS NULL")
        op.alter_column(tabela, coluna, nullable=False)

    op.drop_constraint("ck_veiculo_placa_formato", "veiculo", type_="check")
    op.execute("UPDATE veiculo SET placa = '' WHERE placa IS NULL")
    op.alter_column("veiculo", "placa", nullable=False)

    op.drop_constraint("ck_veiculo_ano_modelo", "veiculo", type_="check")
    op.drop_constraint("ck_veiculo_ano_fabricacao_piso", "veiculo", type_="check")
    op.drop_column("veiculo", "ano_fabricacao")
    op.alter_column("veiculo", "ano_modelo", new_column_name="ano")

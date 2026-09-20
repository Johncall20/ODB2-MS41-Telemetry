"""limites por veiculo para quem nao tem

Revision ID: 0002
Revises: 0001

Migration de DADOS, nao de esquema. Sustenta o invariante "todo veiculo tem
uma linha de limites com os seis valores preenchidos", do qual o modelo
depende: as colunas de `limitesveiculo` sao NOT NULL, e um veiculo sem
linha estoura na leitura.

No fluxo normal quem cria a linha e `repositorios/veiculos.criar()`, na
mesma transacao do veiculo. Esta migration existe para o que entra por
fora: carga de dados, importacao de outro banco, ou uma linha perdida por
um bug. **Num banco vazio ela nao faz nada** - e o esperado.

O SQL esta CONGELADO aqui, escrito a mao, e nao importa nada de
`telemetria/`. Migration tem de continuar significando o que significava no
dia em que foi escrita; se chamasse uma funcao do app, mudar essa funcao
reescreveria o passado - o mesmo `upgrade` passaria a fazer outra coisa.
Por isso os valores sugeridos aparecem como literais, mesmo existindo uma
constante igual em `modelos/limites.py`: se a constante mudar amanha, esta
migration tem de continuar gravando o que gravou hoje.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO limitesveiculo (
            veiculo_id, shift_light_rpm, rpm_alto, temp_alta_c,
            vbat_baixa, rpm_marcha_lenta, ect_operacao_c
        )
        SELECT v.id, 6200, 6800, 105, 11.8, 1100, 80
          FROM veiculo v
         WHERE NOT EXISTS (
               SELECT 1 FROM limitesveiculo lv WHERE lv.veiculo_id = v.id
         )
        """
    )


def downgrade() -> None:
    """Nao ha volta possivel, e tentar uma seria pior.

    Apagar as linhas criadas aqui deixaria veiculos sem limites - o estado
    que o invariante proibe - e nao ha como distinguir a linha que esta
    migration criou daquela que o usuario editou depois.
    """
    pass

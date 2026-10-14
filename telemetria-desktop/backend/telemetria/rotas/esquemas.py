"""
Os formatos que entram e saem pelas rotas: entradas Pydantic, que validam,
e os montadores de dicionario que mais de uma rota reaproveita.
"""

from datetime import date
from typing import Annotated, Optional

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    ValidationInfo,
    field_validator,
)

from ..modelos import (
    CAMPOS_LIMITE,
    Cambio,
    Cliente,
    Combustivel,
    Evento,
    PapelUsuario,
    PerfilEcu,
    TipoEvento,
    Usuario,
    Veiculo,
)
from ..normalizacao import (
    ANO_MINIMO,
    PLACA_VALIDA,
    normalizar_email,
    normalizar_placa,
    texto_curto,
    texto_longo,
    texto_opcional,
)
from ..servicos.autenticacao import SENHA_MINIMA


def _obrigatorio(valor: str) -> str:
    """Normaliza e recusa o que sobrar vazio. A frase vai para o campo."""
    limpo = texto_curto(valor)
    if not limpo:
        raise ValueError("preencha este campo")
    return limpo


# Os dois tipos de texto curto vindo do usuario. Todo campo de texto de
# entrada usa um deles, entao a regra de espaco mora num lugar so
# (`normalizacao.py`): obrigatorio vazio e 422, opcional vazio e None.
# BeforeValidator no opcional para `null` e "" chegarem ao mesmo None.
TextoObrigatorio = Annotated[str, AfterValidator(_obrigatorio)]
TextoOpcional = Annotated[Optional[str], BeforeValidator(texto_opcional)]

# Teto das notas da sessao. O banco tem o mesmo, num CHECK (migration 0011).
NOTAS_MAXIMO = 2000


def _notas(valor: Optional[str]) -> Optional[str]:
    """Normaliza (quebras de linha preservadas) e confere o tamanho depois
    disso - o espaco cortado das pontas nao conta contra o teto."""
    texto = texto_longo(valor)
    if texto is not None and len(texto) > NOTAS_MAXIMO:
        raise ValueError(
            f"as notas têm {len(texto)} caracteres; o máximo é {NOTAS_MAXIMO}"
        )
    return texto


# Texto de varias linhas (as notas da sessao). Vazio vira None, como o
# TextoOpcional, mas sem colapsar as quebras de linha.
TextoLongo = Annotated[Optional[str], BeforeValidator(_notas)]

# Km do painel: inteiro nao negativo, ou nada.
Km = Optional[Annotated[int, Field(ge=0)]]


def _placa(valor: Optional[str]) -> Optional[str]:
    """Normaliza e confere o formato. Vazio e carro sem placa (None)."""
    placa = normalizar_placa(valor)
    if not placa:
        return None
    if not PLACA_VALIDA.match(placa):
        raise ValueError("placa inválida: use o padrão ABC1234 ou ABC1D23")
    return placa


class VeiculoEntrada(BaseModel):
    """O formulario de veiculo, vindo da tela."""

    # Marca e modelo vem do catalogo: a entrada traz so o MODELO, e a
    # marca sai dele. Se o modelo e do catalogo ou da propria conta, quem
    # confere e a rota (`_modelo_do_carro`) - depende da conta logada.
    modelo_id: int
    # Obrigatorios no formulario, anulaveis no banco: carro de antes deles
    # aparece "Nao informado", e editar pede que se preencha.
    combustivel: Combustivel
    cambio: Cambio
    perfil_ecu: PerfilEcu
    # O ano do modelo vem ANTES da fabricacao de proposito: o validator da
    # fabricacao confere a relacao entre os dois, e o Pydantic so entrega
    # em `info.data` os campos declarados antes.
    ano_modelo: int
    ano_fabricacao: int
    # Normalizada e validada na entrada, entao POST e PUT gravam igual.
    placa: Annotated[Optional[str], BeforeValidator(_placa)] = None
    motor: TextoOpcional = None
    # Nula = nao informada. Zero e um valor de verdade (carro zero km).
    quilometragem: Km = None

    # O dono. Opcional na ENTRADA porque a conta PARTICULAR nao escolhe
    # cliente - a rota preenche com o implicito dela. Para o
    # PROFISSIONAL a rota exige um dos dois: `cliente_id` ou
    # `meus_carros`, que e o carro da propria conta (o cliente implicito,
    # que o front nao precisa conhecer pelo id - ele pode nem existir
    # ainda). Os dois juntos sao contraditorios e dao 422, em vez de um
    # vencer em silencio. A checagem mora em `_dono_do_carro()`, e nao num
    # validator daqui, porque depende do papel da conta logada.
    cliente_id: Optional[int] = None
    meus_carros: bool = False

    @field_validator("ano_modelo")
    @classmethod
    def _ano_modelo(cls, valor: int) -> int:
        """Do piso ate o ano que vem: o modelo pode estar um ano a frente."""
        teto = date.today().year + 1
        if not ANO_MINIMO <= valor <= teto:
            raise ValueError(f"o ano do modelo tem de ficar entre {ANO_MINIMO} e {teto}")
        return valor

    @field_validator("ano_fabricacao")
    @classmethod
    def _ano_fabricacao(cls, valor: int, info: ValidationInfo) -> int:
        """Do piso ate o ano corrente, e igual ao modelo ou um a menos.

        O teto e daqui, e nao um CHECK: com a data atual dentro, a
        restricao do banco mudaria de significado sozinha.
        """
        atual = date.today().year
        if valor < ANO_MINIMO:
            raise ValueError(f"o ano de fabricação não pode ser anterior a {ANO_MINIMO}")
        if valor > atual:
            raise ValueError(f"o ano de fabricação não pode passar de {atual}")
        modelo = info.data.get("ano_modelo")
        if modelo is not None and modelo not in (valor, valor + 1):
            raise ValueError("o ano de fabricação tem de ser o do modelo ou o anterior")
        return valor


class ModeloEntrada(BaseModel):
    """O "Nao encontrei meu modelo": so o nome, normalizado."""

    nome: TextoObrigatorio


class InicioSessao(BaseModel):
    """O que a tela manda para comecar a gravar: o carro e os seis limites
    DESTA sessao, todos obrigatorios.

    Planos no corpo, ao lado de `veiculo_id`, e nao aninhados: assim o
    erro de cada um cai no campo certo do 422 (`campos.shift_light_rpm`).
    `gt=0` aqui; a ordem entre eles (`rpm_marcha_lenta < shift_light_rpm <
    rpm_alto`) e `problema_nos_limites()`, conferida pela rota.
    """

    veiculo_id: int
    # As notas e o km do painel, opcionais e planos como os limites. O km
    # fica so na sessao ate ela ser ENCERRADA: so entao (e se for a mais
    # recente) ele passa ao carro - sessao descartada nao mexe no carro.
    observacao: TextoLongo = None
    km: Km = None
    shift_light_rpm: int = Field(gt=0)
    rpm_alto: int = Field(gt=0)
    temp_alta_c: int = Field(gt=0)
    vbat_baixa: float = Field(gt=0)
    rpm_marcha_lenta: int = Field(gt=0)
    ect_operacao_c: int = Field(gt=0)

    def limites(self) -> dict:
        """Os seis valores, como o snapshot e o detector os recebem."""
        return {campo: getattr(self, campo) for campo in CAMPOS_LIMITE}


class EdicaoSessao(BaseModel):
    """O PATCH de uma sessao: so as notas e o km, a qualquer momento.

    `extra="forbid"`: qualquer outro campo e 422, em vez de ser ignorado -
    a sessao nao edita mais nada (limite, datas, agregado). O que nao vem
    no corpo nao muda; `null` (ou nota em branco) limpa. Quem distingue os
    dois e `model_fields_set`.
    """

    model_config = ConfigDict(extra="forbid")

    observacao: TextoLongo = None
    km: Km = None

    def campos(self) -> dict:
        """So o que veio no corpo."""
        return {campo: getattr(self, campo) for campo in self.model_fields_set}


class CadastroEntrada(BaseModel):
    """O formulario de criar conta.

    `EmailStr` valida o formato; o resto da normalizacao e nossa, para o
    banco ter uma forma so do mesmo e-mail.
    """

    nome: TextoObrigatorio
    email: EmailStr
    # A regra de tamanho e do backend, nao da tela: validacao so no React
    # cai por terra em qualquer cliente que nao seja o navegador.
    senha: str = Field(min_length=SENHA_MINIMA)
    papel: PapelUsuario = PapelUsuario.PROFISSIONAL

    @field_validator("email")
    @classmethod
    def _email_normalizado(cls, valor: str) -> str:
        return normalizar_email(valor)


class LoginEntrada(BaseModel):
    """E-mail e senha. Sem `min_length` na senha de proposito: senha curta
    aqui e credencial errada, e a resposta tem de ser a mesma de senha
    errada - um 422 diferente contaria que a conta existe."""

    email: EmailStr
    senha: str

    @field_validator("email")
    @classmethod
    def _email_normalizado(cls, valor: str) -> str:
        return normalizar_email(valor)


def usuario_publico(usuario: Usuario) -> dict:
    """O que uma conta mostra de si.

    Campo a campo, nunca `model_dump()`: assim o `senha_hash` nao escapa
    hoje, e a coluna sensivel que alguem acrescentar amanha tambem nao.
    """
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "papel": usuario.papel.value,
        "criado_em": usuario.criado_em,
    }


class PerfilEntrada(BaseModel):
    """Nome e e-mail da conta. `senha_atual` so e exigida pela rota quando
    o e-mail muda: trocar o e-mail e trocar o que entra no login."""

    nome: TextoObrigatorio
    email: EmailStr
    senha_atual: str = ""

    @field_validator("email")
    @classmethod
    def _email_normalizado(cls, valor: str) -> str:
        return normalizar_email(valor)


class SenhaEntrada(BaseModel):
    """Troca de senha. Sem `min_length` na nova de proposito: o 422 do
    Pydantic sai como lista e a tela mostraria "HTTP 422". A regra de
    tamanho e conferida na rota, com a frase."""

    senha_atual: str
    senha_nova: str


class ExclusaoEntrada(BaseModel):
    """Exclusao da conta: a senha e o proprio e-mail, digitado de novo.
    O backend confere o e-mail tambem - uma chamada de fora da tela nao
    pula a confirmacao."""

    senha: str
    confirmacao: str


class ClienteEntrada(BaseModel):
    """O formulario de cliente."""

    nome: TextoObrigatorio
    # Texto livre (telefone, e-mail, o que a oficina usar): so normalizado.
    contato: TextoOpcional = None


class PapelEntrada(BaseModel):
    """A troca de papel, nos ajustes da conta."""

    papel: PapelUsuario


def cliente_publico(cliente: Cliente) -> dict:
    """O que um cliente mostra. Campo a campo, como o usuario."""
    return {
        "id": cliente.id,
        "nome": cliente.nome,
        "contato": cliente.contato,
        "implicito": cliente.implicito,
        "arquivado_em": cliente.arquivado_em,
    }


def problema_nos_limites(valores: dict) -> dict[str, str]:
    """Os erros de ordem entre os limites, por campo; vazio se estao certos.

    A positividade ja foi conferida pelo `InicioSessao` (`gt=0`). Aqui fica
    o que so se ve com os seis juntos: `rpm_marcha_lenta < shift_light_rpm
    < rpm_alto`. O erro cai no campo que a pessoa provavelmente quis mexer
    - o shift light quando ele passa do giro alto, a marcha lenta quando
    ela passa do shift light -, e os dois podem vir juntos.
    """
    erros: dict[str, str] = {}
    if valores["shift_light_rpm"] >= valores["rpm_alto"]:
        erros["shift_light_rpm"] = (
            f"o shift light ({valores['shift_light_rpm']} rpm) tem de ficar abaixo "
            f"do giro alto ({valores['rpm_alto']} rpm)"
        )
    if valores["rpm_marcha_lenta"] >= valores["shift_light_rpm"]:
        erros["rpm_marcha_lenta"] = (
            f"a marcha lenta ({valores['rpm_marcha_lenta']} rpm) tem de ficar abaixo "
            f"do shift light ({valores['shift_light_rpm']} rpm)"
        )
    return erros


# INICIO_SESSAO e FIM_SESSAO existem em toda sessao; nao dizem nada sobre o
# que aconteceu no motor. As telas so mostram os eventos anomalos.
EVENTOS_DE_ROTINA = {TipoEvento.INICIO_SESSAO, TipoEvento.FIM_SESSAO}


def eventos_notaveis(eventos: list[Evento]) -> list[str]:
    """Tipos de evento anomalo da sessao, sem repetir, na ordem em que
    apareceram. A tela mostra o primeiro e um "+N" com o resto."""
    vistos: list[str] = []
    for e in sorted(eventos, key=lambda e: e.id or 0):
        if e.tipo in EVENTOS_DE_ROTINA:
            continue
        if e.tipo.value not in vistos:
            vistos.append(e.tipo.value)
    return vistos


def veiculo_resumido(veiculo: Veiculo | None) -> dict | None:
    """So o que as telas de sessao mostram do carro.

    `arquivado_em` vai junto porque a sessao de um veiculo arquivado
    continua listada, e a tela precisa marcar a placa.
    """
    if veiculo is None:
        return None
    return {
        "id": veiculo.id,
        "placa": veiculo.placa,
        "marca": veiculo.nome_marca,
        "modelo": veiculo.nome_modelo,
        "descricao": veiculo.descricao(),
        "ano_modelo": veiculo.ano_modelo,
        "ano_fabricacao": veiculo.ano_fabricacao,
        # A quilometragem atual, para a tela da sessao comparar com o km
        # digitado antes de salvar (confirmacao de km menor).
        "quilometragem": veiculo.quilometragem,
        "arquivado_em": veiculo.arquivado_em,
    }


def veiculo_publico(veiculo: Veiculo) -> dict:
    """O veiculo inteiro como a API devolve.

    `marca` e `modelo` continuam saindo como TEXTO - agora o nome do
    catalogo -, e `descricao` e o nome do carro pronto para exibir (sem o
    "Outra" na marca Outra): as telas que so mostram o carro leem ela e
    nao montam nada. Os ids vao junto para o formulario, e
    `modelo_customizado` diz que o modelo e da conta, nao da FIPE.
    """
    return {
        **veiculo.model_dump(),
        "marca": veiculo.nome_marca,
        "modelo": veiculo.nome_modelo,
        "descricao": veiculo.descricao(),
        "marca_id": veiculo.modelo.marca_id if veiculo.modelo else None,
        "modelo_customizado": bool(veiculo.modelo and veiculo.modelo.customizado()),
    }

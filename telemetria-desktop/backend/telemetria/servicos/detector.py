"""
Onde uma leitura vira evento. Cada regra tem histerese: dispara na subida
e so rearma quando o valor volta - senao uma sessao geraria centenas de
linhas iguais. Campo com `valid` apagado nao dispara nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..modelos import Amostra, Evento, Limites, TipoEvento, campos_invalidos

MARGEM_RPM = 300
MARGEM_TEMP = 4
MARGEM_VBAT = 0.3


@dataclass
class DetectorEventos:
    """Acompanha a sessao leitura a leitura e diz o que virou evento.

    Guarda estado entre chamadas (a histerese), entao cada sessao precisa
    de um detector novo.
    """

    limites: Limites
    _armado_shift: bool = field(default=True, init=False)
    _armado_rpm: bool = field(default=True, init=False)
    _armado_temp: bool = field(default=True, init=False)
    _armado_vbat: bool = field(default=True, init=False)
    _ciclos_incompletos: int = field(default=0, init=False)

    def avaliar(self, a: Amostra) -> list[Evento]:
        """Examina uma leitura e devolve os eventos que ela disparou.

        Chamada a cada amostra: nao pode consultar banco nem nada caro.
        """
        eventos: list[Evento] = []
        lim = self.limites

        if a.valido("rpm"):
            if a.rpm >= lim.shift_light_rpm and self._armado_shift:
                self._armado_shift = False
                eventos.append(self._novo(a, TipoEvento.SHIFT_LIGHT, f"{a.rpm} rpm"))
            elif a.rpm < lim.shift_light_rpm - MARGEM_RPM:
                self._armado_shift = True

            if a.rpm >= lim.rpm_alto and self._armado_rpm:
                self._armado_rpm = False
                eventos.append(
                    self._novo(a, TipoEvento.RPM_ALTO, f"{a.rpm} rpm, acima de {lim.rpm_alto}")
                )
            elif a.rpm < lim.rpm_alto - MARGEM_RPM:
                self._armado_rpm = True

        if a.valido("ect"):
            if a.ect >= lim.temp_alta_c and self._armado_temp:
                self._armado_temp = False
                eventos.append(
                    self._novo(a, TipoEvento.TEMP_ALTA, f"agua a {a.ect} C")
                )
            elif a.ect < lim.temp_alta_c - MARGEM_TEMP:
                self._armado_temp = True

        # Bateria e a unica regra que dispara na descida: alarme quando a
        # tensao CAI abaixo do limite, e rearma quando sobe de volta com a
        # margem. Por isso as comparacoes vao ao contrario das de cima.
        if a.valido("vbat"):
            if a.vbat <= lim.vbat_baixa and self._armado_vbat:
                self._armado_vbat = False
                eventos.append(
                    self._novo(
                        a,
                        TipoEvento.BATERIA_BAIXA,
                        f"{a.vbat:.2f} V, abaixo de {lim.vbat_baixa}",
                    )
                )
            elif a.vbat > lim.vbat_baixa + MARGEM_VBAT:
                self._armado_vbat = True

        # Leitura incompleta persistente indica problema no barramento K-line,
        # nao no motor. Registra so depois de 5 ciclos seguidos com falha.
        if not a.completa():
            self._ciclos_incompletos += 1
            if self._ciclos_incompletos == 5:
                faltando = ", ".join(campos_invalidos(a.valid))
                eventos.append(
                    self._novo(
                        a,
                        TipoEvento.LEITURA_INCOMPLETA,
                        f"5 ciclos seguidos sem: {faltando}",
                    )
                )
        else:
            self._ciclos_incompletos = 0

        return eventos

    @staticmethod
    def _novo(a: Amostra, tipo: TipoEvento, mensagem: str) -> Evento:
        """Evento carimbado com a hora da AMOSTRA, nao a de agora - e o que
        faz a marca cair no ponto certo do grafico."""
        return Evento(sessao_id=a.sessao_id, tipo=tipo, mensagem=mensagem, criado_em=a.recebida_em)

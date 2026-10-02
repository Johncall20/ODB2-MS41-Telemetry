/*
  O mapa do app: que endereco abre que tela.

  Toda rota mora dentro do Shell, que desenha a sidebar. Mexe aqui quem
  criar uma tela nova.
*/
import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./layout/Shell.jsx";
import { ExigeSessao, SoDeslogado, SoProfissional } from "./layout/Guarda.jsx";
import { Login } from "./paginas/Login.jsx";
import { CriarConta } from "./paginas/CriarConta.jsx";
import { Cliente } from "./paginas/Cliente.jsx";
import { ClienteFormulario } from "./paginas/ClienteFormulario.jsx";
import { Clientes } from "./paginas/Clientes.jsx";
import { Conta } from "./paginas/Conta.jsx";
import { Veiculos } from "./paginas/Veiculos.jsx";
import { Veiculo } from "./paginas/Veiculo.jsx";
import { VeiculoFormulario } from "./paginas/VeiculoFormulario.jsx";
import { Sessoes } from "./paginas/Sessoes.jsx";
import { Sessao } from "./paginas/Sessao.jsx";
import { Analise } from "./paginas/Analise.jsx";
import { Exportar } from "./paginas/Exportar.jsx";
import { Relatorios } from "./paginas/Relatorios.jsx";
import { AoVivo } from "./paginas/AoVivo.jsx";
import { LimitesVeiculo } from "./paginas/LimitesVeiculo.jsx";

/*
  Itens 2 a 6 construidos, mais Relatorios (item 9) e os limites por
  veiculo - os dois sem node no Figma. Faltam login (item 7) e conexao
  (item 8), ainda indecisos.

  Nao ha /ajustes: limite e por carro, entao a tela dele fica pendurada no
  veiculo, em /veiculos/:id/limites.
*/
export function Rotas() {
  return (
    <Routes>
      {/* Fora do Shell: sem sidebar, e so para quem nao tem sessao. */}
      <Route element={<SoDeslogado />}>
        <Route path="/login" element={<Login />} />
        <Route path="/criar-conta" element={<CriarConta />} />
      </Route>

      {/* Tudo daqui para baixo exige sessao. A guarda vem POR FORA do
          Shell: sem ela, o TelemetriaProvider do Shell abriria o
          websocket e chamaria /api/status antes de haver login. */}
      <Route element={<ExigeSessao />}>
      <Route element={<Shell />}>
        <Route index element={<Navigate to="/veiculos" replace />} />
        <Route path="/veiculos" element={<Veiculos />} />
        <Route path="/veiculos/novo" element={<VeiculoFormulario />} />
        <Route path="/veiculos/:id" element={<Veiculo />} />
        <Route path="/veiculos/:id/editar" element={<VeiculoFormulario />} />
        <Route path="/veiculos/:id/limites" element={<LimitesVeiculo />} />
        <Route path="/ao-vivo" element={<AoVivo />} />
        <Route path="/sessoes" element={<Sessoes />} />
        <Route path="/sessoes/:id" element={<Sessao />} />
        <Route path="/sessoes/:id/analise" element={<Analise />} />
        <Route path="/sessoes/:id/exportar" element={<Exportar />} />
        <Route path="/relatorios" element={<Relatorios />} />
        {/* Clientes e so do PROFISSIONAL. Para o PARTICULAR a guarda
            redireciona a /veiculos em vez de sumir com a rota: um link
            salvo de quando a conta era outra leva aos carros, nao a um
            404. */}
        <Route element={<SoProfissional />}>
          <Route path="/clientes" element={<Clientes />} />
          <Route path="/clientes/novo" element={<ClienteFormulario />} />
          <Route path="/clientes/:id" element={<Cliente />} />
          <Route path="/clientes/:id/editar" element={<ClienteFormulario />} />
        </Route>
        <Route path="/conta" element={<Conta />} />
        <Route path="*" element={<Navigate to="/veiculos" replace />} />
      </Route>
      </Route>
    </Routes>
  );
}

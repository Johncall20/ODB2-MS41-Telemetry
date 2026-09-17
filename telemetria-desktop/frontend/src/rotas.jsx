/*
  O mapa do app: que endereco abre que tela.

  Toda rota mora dentro do Shell, que desenha a sidebar. Mexe aqui quem
  criar uma tela nova.
*/
import { Navigate, Route, Routes } from "react-router-dom";
import { Shell } from "./layout/Shell.jsx";
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
        <Route path="*" element={<Navigate to="/veiculos" replace />} />
      </Route>
    </Routes>
  );
}

import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import s from "./Migalha.module.css";

/**
 * Link de volta no topo da tela. O icone da lucide herda currentColor,
 * entao acompanha o hover do link sozinho.
 */
export function Migalha({ para, children }) {
  return (
    <Link className={s.migalha} to={para}>
      <ChevronLeft size={20} aria-hidden="true" />
      {children}
    </Link>
  );
}

import { ChevronRight } from "lucide-react";
import s from "./Seta.module.css";

/** Seta de "abre este item", na ultima coluna das tabelas. */
export function Seta() {
  return <ChevronRight className={s.seta} size={21} aria-hidden="true" />;
}

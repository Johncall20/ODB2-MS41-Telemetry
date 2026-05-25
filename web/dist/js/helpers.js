/* =========================================================================
   helpers.js
   Funções utilitárias puras, sem estado de UI.
   ========================================================================= */
'use strict';

(function () {
  var helpers = {};

  /* requestAnimationFrame com fallback (Safari antigo / sem suporte) */
  helpers.requestFrame = window.requestAnimationFrame ||
    window.webkitRequestAnimationFrame ||
    function (cb) { return setTimeout(cb, 16); };

  /* Limita v ao intervalo [a, b] */
  helpers.clamp = function (v, a, b) {
    return Math.min(b, Math.max(a, v));
  };

  /* Suavização exponencial em direção ao alvo (frame-rate independente) */
  helpers.smoothTowards = function (current, target, dt, response) {
    var alpha = 1 - Math.exp(-response * dt);
    return current + (target - current) * alpha;
  };

  /* Formata um valor numérico com N casas; "--" quando inválido */
  helpers.formatValue = function (v, decimals) {
    if (v === null || v === undefined || isNaN(v)) return '--';
    var n = Number(v);
    if (!isFinite(n)) return '--';
    return n.toFixed(decimals);
  };

  /* JSON.parse que nunca lança (retorna null em erro) */
  helpers.safeParseJSON = function (s) {
    try { return JSON.parse(s); }
    catch (e) { return null; }
  };

  DASH.helpers = helpers;
})();

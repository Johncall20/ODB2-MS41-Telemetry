/* =========================================================================
   viewport.js
   Ajustes dependentes do tamanho da janela:
     - setVh(): corrige o "100vh" no Safari iOS via variável --vh
     - fitTilesToViewport(): escala a grade de tiles para nunca cortar
   ========================================================================= */
'use strict';

(function () {
  var viewport = {};

  // referências resolvidas no init
  var rightCol = null;
  var tilesRoot = null;

  viewport.init = function () {
    rightCol  = document.querySelector('.right');
    tilesRoot = document.getElementById('tiles');
  };

  /* Define --vh = 1% da altura real da janela (workaround do 100vh no iOS) */
  viewport.setVh = function () {
    var vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', vh + 'px');
  };

  /* Faz a grade de tiles caber na altura disponível (sem cortar topo/base) */
  viewport.fitTilesToViewport = function () {
    if (!rightCol || !tilesRoot) return;

    // reset primeiro
    tilesRoot.style.transform = '';
    tilesRoot.style.webkitTransform = '';
    tilesRoot.style.width = '';

    // força layout
    var availH = rightCol.clientHeight;
    var needH  = tilesRoot.scrollHeight;

    if (!availH || !needH) return;

    // um "respiro" pra não encostar nas bordas (Safari tem rounding)
    var PAD = 24;
    availH = Math.max(0, availH - PAD);

    if (needH > availH) {
      var s = availH / needH;

      // não deixa reduzir demais (pra continuar legível)
      s = Math.max(0.78, Math.min(1, s));

      tilesRoot.style.transform = 'scale(' + s + ')';
      tilesRoot.style.webkitTransform = 'scale(' + s + ')';

      // compensa a largura pra não "afinar" e não sobrar buracos
      tilesRoot.style.width = (100 / s) + '%';
    }
  };

  DASH.viewport = viewport;
})();

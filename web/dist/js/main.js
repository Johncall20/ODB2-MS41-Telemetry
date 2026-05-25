/* =========================================================================
   main.js
   Orquestra os módulos: loop de animação, renderização dos tiles, tratamento
   de resize/orientação e inicialização. Carregado por ÚLTIMO.
   ========================================================================= */
'use strict';

(function () {
  var helpers   = DASH.helpers;
  var cfg       = DASH.config;
  var gauge     = DASH.gauge;
  var tilesMod  = DASH.tiles;
  var telemetry = DASH.telemetry;
  var viewport  = DASH.viewport;
  var net       = DASH.net;

  var clamp         = helpers.clamp;
  var smoothTowards = helpers.smoothTowards;
  var formatValue   = helpers.formatValue;
  var requestFrame  = helpers.requestFrame;

  var targetState  = telemetry.targetState;
  var displayState = telemetry.displayState;

  var tilesRoot = null;
  var tileNodes = null;

  /* Renderiza gauge + tiles a partir do estado exibido */
  function renderFromDisplay() {
    var rpm = Number(displayState.rpm) || 0;

    gauge.render(rpm);

    if (!tileNodes) tileNodes = tilesRoot.getElementsByClassName('tile');

    var i;
    for (i = 0; i < tileNodes.length; i++) {
      var tile = tileNodes[i];
      var spec = tile._spec;
      if (!spec) continue;

      var v = displayState[spec.key];
      tile._valueEl.textContent = formatValue(v, spec.decimals);

      var denom = (spec.max - spec.min);
      var tt = denom > 0 ? (Number(v) - spec.min) / denom : 0;
      var pct = clamp(tt, 0, 1);

      tile._fillEl.style.width = (pct * 100) + '%';
    }

    viewport.fitTilesToViewport();
  }

  /* Loop principal: suaviza display -> target e renderiza */
  var lastT = 0;
  function tick(t) {
    if (!lastT) lastT = t;
    var dt = (t - lastT) / 1000.0;
    if (dt < 0) dt = 0;
    if (dt > 0.05) dt = 0.05;
    lastT = t;

    displayState.rpm = smoothTowards(displayState.rpm, targetState.rpm, dt, 18);

    displayState.fuelPressure = smoothTowards(displayState.fuelPressure, targetState.fuelPressure, dt, 10);
    displayState.oilPressure  = smoothTowards(displayState.oilPressure,  targetState.oilPressure,  dt, 10);
    displayState.tps          = smoothTowards(displayState.tps,          targetState.tps,          dt, 12);
    displayState.map          = smoothTowards(displayState.map,          targetState.map,          dt, 10);
    displayState.afr          = smoothTowards(displayState.afr,          targetState.afr,          dt, 10);
    displayState.lambda       = smoothTowards(displayState.lambda,       targetState.lambda,       dt, 10);
    displayState.speed        = smoothTowards(displayState.speed,        targetState.speed,        dt, 12);
    displayState.ignAdv       = smoothTowards(displayState.ignAdv,       targetState.ignAdv,       dt, 10);
    displayState.intakeTemp   = smoothTowards(displayState.intakeTemp,   targetState.intakeTemp,   dt, 8);
    displayState.engineTemp   = smoothTowards(displayState.engineTemp,   targetState.engineTemp,   dt, 8);
    displayState.battery      = smoothTowards(displayState.battery,      targetState.battery,      dt, 8);

    displayState.gear = targetState.gear;

    renderFromDisplay();
    requestFrame(tick);
  }

  /* Recalcula geometria do gauge e re-renderiza (após resize) */
  function resizeAll() {
    gauge.resize();
    renderFromDisplay();
    renderFromDisplay(); // 2x: reforço p/ medições de layout no Safari
    viewport.fitTilesToViewport();
  }

  /* Registra os eventos de janela (Safari iOS precisa de "reforço") */
  function bindEvents() {
    window.addEventListener('resize', function () {
      setTimeout(resizeAll, 0);
      setTimeout(resizeAll, 120);

      viewport.fitTilesToViewport();
      setTimeout(viewport.fitTilesToViewport, 160);
    }, false);

    window.addEventListener('orientationchange', function () {
      setTimeout(viewport.setVh, 60);
      setTimeout(viewport.setVh, 240);

      setTimeout(resizeAll, 60);
      setTimeout(resizeAll, 240);

      setTimeout(viewport.fitTilesToViewport, 240);
    }, false);

    window.addEventListener('load', function () {
      resizeAll();
      setTimeout(resizeAll, 120);
      setTimeout(viewport.fitTilesToViewport, 180);
    }, false);
  }

  /* Bootstrap da aplicação */
  function init() {
    tilesRoot = document.getElementById('tiles');

    viewport.init();
    viewport.setVh();

    gauge.init();
    tilesMod.buildTiles(tilesRoot);

    bindEvents();

    resizeAll();
    net.connect();
    requestFrame(tick);
  }

  init();
})();

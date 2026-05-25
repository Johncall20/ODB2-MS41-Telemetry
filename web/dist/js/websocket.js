/* =========================================================================
   websocket.js
   Conexão WebSocket com o servidor de telemetria, reconexão automática e
   fallback para dados mock quando a conexão cai/falha.
   ========================================================================= */
'use strict';

(function () {
  var cfg = DASH.config;
  var telemetry = DASH.telemetry;
  var safeParseJSON = DASH.helpers.safeParseJSON;

  var net = {};

  var ws = null;
  var retryTimer = null;
  var mock = null;
  var mockTimer = null;

  /* Monta a URL do WS no mesmo host/porta (ws:// ou wss:// conforme o http) */
  function resolvedWsUrl() {
    var proto = (window.location.protocol === 'https:') ? 'wss://' : 'ws://';
    return proto + window.location.host + '/ws';
  }

  /* Liga o gerador mock que alimenta o estado-alvo periodicamente */
  function startMock() {
    if (mockTimer) return;
    mock = telemetry.createMockTelemetry();
    var target = telemetry.targetState;

    mockTimer = setInterval(function () {
      mock.tick(0.08);

      target.rpm = mock.rpm;
      target.gear = mock.gear;
      target.fuelPressure = mock.fuelPressure;
      target.oilPressure = mock.oilPressure;
      target.tps = mock.tps;
      target.map = mock.map;
      target.afr = mock.afr;
      target.lambda = mock.lambda;
      target.speed = mock.speed;
      target.ignAdv = mock.ignAdv;
      target.intakeTemp = mock.intakeTemp;
      target.engineTemp = mock.engineTemp;
      target.battery = mock.battery;
    }, cfg.MOCK_INTERVAL_MS);
  }

  function stopMock() {
    if (mockTimer) { clearInterval(mockTimer); mockTimer = null; }
    mock = null;
  }

  function scheduleRetry() {
    if (retryTimer) return;
    retryTimer = setTimeout(function () {
      retryTimer = null;
      net.connect();
    }, cfg.WS_RETRY_MS);
  }

  /* Abre (ou reabre) a conexão WebSocket */
  net.connect = function () {
    var url = resolvedWsUrl();
    try {
      ws = new WebSocket(url);
    } catch (e) {
      startMock();
      scheduleRetry();
      return;
    }

    ws.onopen = function () { stopMock(); };

    ws.onmessage = function (ev) {
      var msg = safeParseJSON(ev.data);
      if (!msg || typeof msg !== 'object') return;
      if (msg.type === 'telemetry' && msg.data && typeof msg.data === 'object') {
        telemetry.mergeFromServer(telemetry.targetState, msg.data);
      }
    };

    ws.onerror = function () {};

    ws.onclose = function () {
      startMock();
      scheduleRetry();
    };
  };

  DASH.net = net;
})();

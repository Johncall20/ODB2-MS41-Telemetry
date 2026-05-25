/* =========================================================================
   telemetry.js
   Estados de telemetria (alvo x exibido), mapeamento das mensagens do
   servidor e gerador de dados mock (usado quando o WebSocket cai).
   ========================================================================= */
'use strict';

(function () {
  var telemetry = {};

  /* Estado "alvo": valores recebidos do servidor (ou mock) */
  telemetry.targetState = {
    rpm: 0, gear: 1,
    fuelPressure: 0, oilPressure: 0, tps: 0, map: 0,
    afr: 0, lambda: 0, speed: 0, ignAdv: 0,
    intakeTemp: 0, engineTemp: 0, battery: 0
  };

  /* Estado "exibido": converge suavemente para o alvo a cada frame */
  telemetry.displayState = {
    rpm: 0, gear: 1,
    fuelPressure: 0, oilPressure: 0, tps: 0, map: 0,
    afr: 0, lambda: 0, speed: 0, ignAdv: 0,
    intakeTemp: 0, engineTemp: 0, battery: 0
  };

  /* Mapeia uma mensagem do servidor para o estado-alvo.
     Faz conversões de unidade (ex.: kPa -> bar absoluto no MAP). */
  telemetry.mergeFromServer = function (state, msgData) {
    if (!msgData) return state;

    if (msgData.rpm !== undefined) state.rpm = msgData.rpm;
    if (msgData.vss !== undefined) state.speed = msgData.vss;
    if (msgData.tps !== undefined) state.tps = msgData.tps;

    // kPa -> bar (abs)
    if (msgData.map_kpa !== undefined) state.map = (Number(msgData.map_kpa) / 100.0);

    if (msgData.iat !== undefined) state.intakeTemp = msgData.iat;
    if (msgData.ect !== undefined) state.engineTemp = msgData.ect;

    if (msgData.lambda !== undefined) state.lambda = msgData.lambda;
    if (msgData.afr !== undefined) state.afr = msgData.afr;

    if (msgData.battery !== undefined) state.battery = msgData.battery;
    if (msgData.fuelPressure !== undefined) state.fuelPressure = msgData.fuelPressure;
    if (msgData.oilPressure !== undefined) state.oilPressure = msgData.oilPressure;
    if (msgData.ignAdv !== undefined) state.ignAdv = msgData.ignAdv;
    if (msgData.gear !== undefined) state.gear = msgData.gear;

    return state;
  };

  /* Gerador de telemetria fake (senoides) para demonstração / fallback */
  telemetry.createMockTelemetry = function () {
    var t = {
      gear: 3,
      rpm: 4380,
      fuelPressure: 5.27,
      oilPressure: 4.82,
      tps: 87,
      map: -0.92,
      afr: 13.60,
      lambda: 0.89,
      speed: 125,
      ignAdv: 32.25,
      intakeTemp: 47,
      engineTemp: 92,
      battery: 13.36,
      phase: 0
    };

    t.tick = function (dt) {
      t.phase += dt;

      t.rpm = 1200 + (Math.sin(t.phase * 1.20) * 0.5 + 0.5) * 6500;
      t.gear = 1 + Math.floor((t.phase * 0.35) % 6);

      t.fuelPressure = 3.8 + Math.sin(t.phase * 0.8) * 1.6;
      t.oilPressure = 4.6 + Math.sin(t.phase * 0.6) * 1.8;
      t.tps = (Math.sin(t.phase * 1.1) * 0.5 + 0.5) * 100;
      t.map = -0.9 + Math.sin(t.phase * 0.9) * 1.1;

      t.afr = 13.2 + Math.sin(t.phase * 0.7) * 1.2;
      t.lambda = 0.90 + Math.sin(t.phase * 0.7) * 0.12;
      t.speed = (Math.sin(t.phase * 0.5) * 0.5 + 0.5) * 220;
      t.ignAdv = -2 + (Math.sin(t.phase * 0.9) * 0.5 + 0.5) * 40;

      t.intakeTemp = 20 + (Math.sin(t.phase * 0.35) * 0.5 + 0.5) * 40;
      t.engineTemp = 75 + (Math.sin(t.phase * 0.25) * 0.5 + 0.5) * 30;
      t.battery = 13.1 + Math.sin(t.phase * 0.4) * 0.6;
    };

    return t;
  };

  DASH.telemetry = telemetry;
})();

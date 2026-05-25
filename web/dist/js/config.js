/* =========================================================================
   config.js
   Namespace global compartilhado + todas as constantes de configuração.
   Carregado PRIMEIRO (antes dos demais scripts).
   ========================================================================= */
'use strict';

/* Namespace único usado para compartilhar estado/funções entre os módulos.
   Mantém tudo fora do escopo global "solto" (compatível com Safari antigo). */
var DASH = window.DASH || (window.DASH = {});

DASH.config = {
  /* ----- Gauge RPM ----- */
  RPM_MAX: 8000,
  START: Math.PI * 0.90,   // ângulo inicial do arco
  SWEEP: Math.PI * 1.23,   // varredura total do arco

  /* ----- Shift overlay (histerese) ----- */
  SHIFT_ON: 5500.0,
  SHIFT_OFF: 5300.0,
  SHIFT_RPM_DOTS: 6500,    // referência p/ acender os dots

  /* ----- WebSocket ----- */
  WS_RETRY_MS: 1200,
  MOCK_INTERVAL_MS: 80,

  /* ----- Specs dos tiles -----
     Cada tile: título, unidade, faixa (min/max), casas decimais e a chave
     correspondente no objeto de estado de telemetria. */
  tilesSpec: [
    { title: 'FUEL PRESS.', unit: 'bar',  min:   0.0, max:   8.0, decimals: 1, key: 'fuelPressure' },
    { title: 'OIL PRESS.',  unit: 'bar',  min:   0.0, max:  10.0, decimals: 1, key: 'oilPressure' },
    { title: 'TPS',         unit: '%',    min:   0.0, max: 100.0, decimals: 0, key: 'tps' },
    { title: 'MAP',         unit: 'bar',  min:   0.0, max:   2.5, decimals: 1, key: 'map' },
    { title: 'AFR',         unit: '',     min:  10.0, max:  20.0, decimals: 1, key: 'afr' },
    { title: 'LAMBDA',      unit: '',     min:   0.70, max:  1.30, decimals: 2, key: 'lambda' },
    { title: 'SPEED',       unit: 'km/h', min:   0.0, max: 260.0, decimals: 0, key: 'speed' },
    { title: 'IGN ADV.',    unit: 'deg',  min: -10.0, max:  50.0, decimals: 0, key: 'ignAdv' },
    { title: 'IAT',         unit: '°C',   min: -20.0, max:  80.0, decimals: 0, key: 'intakeTemp' },
    { title: 'ECT',         unit: '°C',   min:  40.0, max: 130.0, decimals: 0, key: 'engineTemp' },
    { title: 'BATTERY',     unit: 'V',    min:  10.0, max:  16.0, decimals: 1, key: 'battery' }
  ]
};

/* =========================================================================
   gauge.js
   Tudo relacionado ao medidor de RPM (SVG): arco de progresso, marcas
   numéricas, ponta (tip), dots, ajuste dinâmico de fonte e o SHIFT overlay
   com histerese.

   Uso: DASH.gauge.init() depois que o DOM existe; depois chamar
   resize()/render() conforme necessário.
   ========================================================================= */
'use strict';

(function () {
  var clamp = DASH.helpers.clamp;
  var cfg = DASH.config;

  var gauge = {};

  // ----- elementos (preenchidos no init) -----
  var rpmWrap, rpmSvg, rpmCenter, rpmText, rpmUnit,
      rpmTip, rpmMarks, rpmDots, shiftOverlay, arcBg, arcVal;

  // ----- geometria do arco -----
  var START = cfg.START;
  var SWEEP = cfg.SWEEP;
  var RPM_MAX = cfg.RPM_MAX;

  var CX, CY, R, CIRC, ARC_FRAC, ARC_LEN, GAP_LEN, startDeg;

  // ----- estado dos dots -----
  var dotCount = 0;

  // ----- estado do shift (histerese) -----
  var shiftOn = false;

  /* Lê o viewBox do SVG (com fallback parseando o atributo) */
  function readViewBox() {
    var vb = null;
    if (rpmSvg && rpmSvg.viewBox && rpmSvg.viewBox.baseVal) {
      vb = rpmSvg.viewBox.baseVal;
      return { w: vb.width, h: vb.height };
    }
    var s = rpmSvg.getAttribute('viewBox') || '0 0 340 340';
    var parts = s.split(/\s+/);
    return { w: Number(parts[2]) || 340, h: Number(parts[3]) || 340 };
  }

  /* Centro e raio do círculo a partir do elemento de fundo */
  function readCircleCenter() {
    var cx = Number(arcBg.getAttribute('cx')) || 0;
    var cy = Number(arcBg.getAttribute('cy')) || 0;
    var r  = Number(arcBg.getAttribute('r')) || 0;
    return { cx: cx, cy: cy, r: r };
  }

  /* Posiciona o bloco central (número/unidade) sobre o centro do círculo */
  function syncCenterFromSvg() {
    var vb = readViewBox();
    var c = readCircleCenter();
    if (!vb.w || !vb.h) return;
    rpmCenter.style.left = (c.cx / vb.w * 100) + '%';
    rpmCenter.style.top  = (c.cy / vb.h * 100) + '%';
  }

  /* Configura o dasharray/rotação de um círculo para virar arco */
  function setupArc(circleEl) {
    circleEl.setAttribute('stroke-dasharray', ARC_LEN + ' ' + GAP_LEN);
    circleEl.setAttribute('transform', 'rotate(' + startDeg + ' ' + CX + ' ' + CY + ')');
    circleEl.setAttribute('stroke-dashoffset', '0');
  }

  /* (Re)calcula a geometria do arco a partir do centro/raio atuais */
  function computeArcGeometry() {
    var c = readCircleCenter();
    CX = c.cx; CY = c.cy; R = c.r;

    CIRC = 2 * Math.PI * R;
    ARC_FRAC = SWEEP / (2 * Math.PI);
    ARC_LEN = CIRC * ARC_FRAC;
    GAP_LEN = CIRC - ARC_LEN;
    startDeg = (START * 180 / Math.PI);
  }

  /* Marcas numéricas (1..8) ao redor do arco */
  function buildMarks() {
    while (rpmMarks.firstChild) rpmMarks.removeChild(rpmMarks.firstChild);

    var vb = readViewBox();
    var rr = R - 16 * 0.95;

    var k;
    for (k = 1; k <= 8; k++) {
      var t = (k - 1) / 7;
      var a = START + SWEEP * (0.08 + t * 0.92);
      var x = CX + Math.cos(a) * rr;
      var y = CY + Math.sin(a) * rr;

      var sp = document.createElement('span');
      sp.appendChild(document.createTextNode(String(k)));
      sp.style.left = (x / vb.w * 100) + '%';
      sp.style.top  = (y / vb.h * 100) + '%';
      rpmMarks.appendChild(sp);
    }
  }

  /* Atualiza o arco preenchido e a ponta de acordo com o RPM */
  function setRpmGauge(rpm) {
    var pct = clamp((rpm || 0) / RPM_MAX, 0, 1);

    var vis = ARC_LEN * pct;
    var rest = CIRC - vis;
    arcVal.setAttribute('stroke-dasharray', vis + ' ' + rest);
    arcVal.setAttribute('transform', 'rotate(' + startDeg + ' ' + CX + ' ' + CY + ')');

    var vb = readViewBox();
    var a = START + SWEEP * pct;
    var tipR = R + (16 * 0.03);

    var x = CX + Math.cos(a) * tipR;
    var y = CY + Math.sin(a) * tipR;

    rpmTip.style.left = (x / vb.w * 100) + '%';
    rpmTip.style.top  = (y / vb.h * 100) + '%';
  }

  /* Ajusta o tamanho da fonte do número central para caber no espaço */
  function fitRpmFont() {
    var wrapRect = rpmWrap.getBoundingClientRect();
    var centerRect = rpmCenter.getBoundingClientRect();

    var base = Math.floor(Math.min(wrapRect.width, wrapRect.height) * 0.22);
    if (base < 34) base = 34;
    if (base > 120) base = 120;

    rpmText.style.fontSize = base + 'px';

    var maxW = centerRect.width;
    var tries = 0;
    while (tries < 8) {
      var tr = rpmText.getBoundingClientRect();
      if (tr.width <= maxW * 0.98) break;
      base = Math.floor(base * 0.90);
      rpmText.style.fontSize = base + 'px';
      tries++;
    }

    var u = Math.floor(base * 0.22);
    if (u < 12) u = 12;
    if (u > 18) u = 18;
    rpmUnit.style.fontSize = u + 'px';
    rpmUnit.style.marginTop = Math.floor(base * 0.12) + 'px';
  }

  /* Quantidade de dots desejada conforme a largura do gauge */
  function desiredDotCount() {
    var w = rpmWrap.getBoundingClientRect().width;
    if (w < 260) return 8;
    if (w < 320) return 10;
    if (w < 380) return 12;
    if (w < 460) return 14;
    return 16;
  }

  /* Reconstrói os dots somente se a quantidade desejada mudou */
  function rebuildDotsIfNeeded() {
    var want = desiredDotCount();
    if (want === dotCount) return;

    dotCount = want;
    while (rpmDots.firstChild) rpmDots.removeChild(rpmDots.firstChild);

    var i;
    for (i = 0; i < dotCount; i++) rpmDots.appendChild(document.createElement('i'));

    var wrapW = rpmWrap.getBoundingClientRect().width;
    var size = Math.floor(wrapW * 0.022);
    if (size < 7) size = 7;
    if (size > 12) size = 12;

    var gap = Math.floor(size * 0.65);
    if (gap < 4) gap = 4;
    if (gap > 8) gap = 8;

    rpmDots.style.height = (size + 6) + 'px';

    var dots = rpmDots.getElementsByTagName('i');
    for (i = 0; i < dots.length; i++) {
      dots[i].style.width = size + 'px';
      dots[i].style.height = size + 'px';
      dots[i].style.marginLeft = (i === 0) ? '0' : gap + 'px';
    }
  }

  /* Acende/apaga os dots conforme o RPM */
  function updateDotsOnOff(rpm) {
    if (!dotCount) return;

    var dots = rpmDots.getElementsByTagName('i');
    var on = Math.round(clamp(rpm / cfg.SHIFT_RPM_DOTS, 0, 1) * dots.length);

    var i;
    for (i = 0; i < dots.length; i++) {
      dots[i].className = (i < on) ? 'on' : '';
    }
  }

  /* SHIFT overlay com histerese (liga em SHIFT_ON, desliga em SHIFT_OFF) */
  function updateShift(rpm) {
    if (rpm >= cfg.SHIFT_ON) shiftOn = true;
    else if (rpm <= cfg.SHIFT_OFF) shiftOn = false;

    shiftOverlay.className = shiftOn ? 'shiftOverlay on' : 'shiftOverlay';
  }

  // ====== API pública ======

  /* Captura elementos do DOM e calcula a geometria inicial */
  gauge.init = function () {
    rpmWrap      = document.getElementById('rpmWrap');
    rpmSvg       = document.getElementById('rpmSvg');
    rpmCenter    = document.getElementById('rpmCenter');
    rpmText      = document.getElementById('rpmText');
    rpmUnit      = document.getElementById('rpmUnit');
    rpmTip       = document.getElementById('rpmTip');
    rpmMarks     = document.getElementById('rpmMarks');
    rpmDots      = document.getElementById('rpmDots');
    shiftOverlay = document.getElementById('shiftOverlay');
    arcBg        = document.getElementById('rpmArcBg');
    arcVal       = document.getElementById('rpmArcVal');

    computeArcGeometry();
    setupArc(arcBg);
    setupArc(arcVal);
    syncCenterFromSvg();
    buildMarks();
  };

  /* Recalcula tudo após mudança de tamanho/orientação */
  gauge.resize = function () {
    computeArcGeometry();
    setupArc(arcBg);
    setupArc(arcVal);
    syncCenterFromSvg();
    buildMarks();
    rebuildDotsIfNeeded();
    fitRpmFont();
  };

  /* Renderiza o gauge para um valor de RPM */
  gauge.render = function (rpm) {
    rpmText.textContent = String(Math.round(rpm));

    syncCenterFromSvg();
    rebuildDotsIfNeeded();
    fitRpmFont();

    setRpmGauge(rpm);
    updateShift(rpm);
    updateDotsOnOff(rpm);
  };

  /* Reconstrói as marcas (usado no boot inicial) */
  gauge.buildMarks = buildMarks;

  DASH.gauge = gauge;
})();

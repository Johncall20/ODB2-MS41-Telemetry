/* =========================================================================
   tiles.js
   Construção dos "tiles" (cartões de telemetria) a partir de tilesSpec.
   Guarda em cada nó referências (_spec / _valueEl / _fillEl) usadas
   depois na renderização.
   ========================================================================= */
'use strict';

(function () {
  var tiles = {};

  /* Cria todos os tiles dentro do container informado */
  tiles.buildTiles = function (container) {
    var spec = DASH.config.tilesSpec;
    var i;

    for (i = 0; i < spec.length; i++) {
      var s = spec[i];

      var tile = document.createElement('div');
      tile.className = 'tile';

      var title = document.createElement('div');
      title.className = 'title';
      title.appendChild(document.createTextNode(s.title));

      var value = document.createElement('div');
      value.className = 'value';
      value.appendChild(document.createTextNode('0'));

      var bar = document.createElement('div');
      bar.className = 'bar';
      var fill = document.createElement('div');
      fill.className = 'fill';
      bar.appendChild(fill);

      var ticks = document.createElement('div');
      ticks.className = 'ticks';

      var minmax = document.createElement('div');
      minmax.className = 'minmax';
      var mn = document.createElement('span');
      mn.appendChild(document.createTextNode(String(s.min)));
      var mx = document.createElement('span');
      mx.appendChild(document.createTextNode(String(s.max)));
      minmax.appendChild(mn);
      minmax.appendChild(mx);

      var unit = document.createElement('div');
      unit.className = 'unit';
      unit.appendChild(document.createTextNode(s.unit || ''));

      tile.appendChild(title);
      tile.appendChild(value);
      tile.appendChild(bar);
      tile.appendChild(ticks);
      tile.appendChild(minmax);
      tile.appendChild(unit);

      // referências usadas na renderização (evita querySelector por frame)
      tile._spec = s;
      tile._valueEl = value;
      tile._fillEl = fill;

      container.appendChild(tile);
    }
  };

  DASH.tiles = tiles;
})();

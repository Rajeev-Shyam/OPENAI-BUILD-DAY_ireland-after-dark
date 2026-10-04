export const places = [
  ['Dublin city centre', -6.2603, 53.3498], ['Dublin Docklands', -6.248, 53.348],
  ['Cork city centre', -8.4756, 51.8985], ['Galway city centre', -9.0568, 53.2707],
  ['Limerick city centre', -8.6267, 52.6638], ['Waterford city centre', -7.1101, 52.2593],
  ['Belfast city centre', -5.9301, 54.5973], ['Derry city centre', -7.3092, 54.9966],
  ['Sligo town centre', -8.4761, 54.2766], ['Athlone town centre', -7.9407, 53.4239],
  ['Kilkenny city centre', -7.2522, 52.6541], ['Wexford town centre', -6.4633, 52.3369]
];
export function searchPlaces(query) { const term = query.trim().toLowerCase(); return term ? places.filter(place => place[0].toLowerCase().includes(term)) : []; }

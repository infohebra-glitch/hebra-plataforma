// Temas del blog: agrupan las etiquetas (kicker) de los artículos para el filtro del índice.
export const TOPICS = [
  { id: 'probador', es: 'Probador', ca: 'Emprovador', en: 'Fitting room' },
  { id: 'origen', es: 'Origen', ca: 'Origen', en: 'Origin' },
  { id: 'normativa', es: 'Normativa y sector', ca: 'Normativa i sector', en: 'Regulation and industry' },
] as const;

const MAP: Record<string, string> = {
  probador: 'probador', emprovador: 'probador', 'fitting room': 'probador', 'el porqué': 'probador', 'el perquè': 'probador', 'the why': 'probador', why: 'probador', datos: 'normativa', dades: 'normativa', data: 'normativa',
  origen: 'origen', origin: 'origen', 'la ficha': 'origen', 'la fitxa': 'origen', 'the garment page': 'origen',
  normativa: 'normativa', regulation: 'normativa', 'rules': 'normativa',
};
export const topicOf = (kicker: string) => MAP[kicker.trim().toLowerCase()] ?? 'probador';

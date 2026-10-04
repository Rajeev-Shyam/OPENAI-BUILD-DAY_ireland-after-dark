const formatter = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Dublin', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
export function dublinNow(date = new Date()) {
  const parts = Object.fromEntries(formatter.formatToParts(date).map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
export function departurePayload(value, occurrence = 'earlier') {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error('Choose a valid departure date and time.');
  const nominal = Date.parse(`${value}:00Z`);
  const matches = [nominal - 3600000, nominal].filter(instant => Number.isFinite(instant) && dublinNow(new Date(instant)) === value);
  if (!matches.length) throw new Error('This time does not exist in Europe/Dublin. Choose another time.');
  return { departure_time: new Date(occurrence === 'later' ? matches.at(-1) : matches[0]).toISOString(), timezone: 'Europe/Dublin' };
}

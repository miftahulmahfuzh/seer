// US market session dates, seen from Jakarta.
// Holidays are not modelled here: the engine knows the real calendar and writes
// the true session_date; this only needs to tell "fresh" from "stale".

const ET = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', hourCycle: 'h23', weekday: 'short',
});

function etParts(now: Date) {
  const p = Object.fromEntries(ET.formatToParts(now).map(x => [x.type, x.value]));
  return { ymd: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour), weekday: p.weekday as string };
}

function addDays(ymd: string, n: number): string {
  const d = new Date(`${ymd}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

const isWeekend = (ymd: string) => [0, 6].includes(new Date(`${ymd}T12:00:00Z`).getUTCDay());

/** The US session (ET calendar date) that new picks should target right now. */
export function nextUsSession(now: Date): string {
  const { ymd, hour } = etParts(now);
  let day = !isWeekend(ymd) && hour < 16 ? ymd : addDays(ymd, 1);
  while (isWeekend(day)) day = addDays(day, 1);
  return day;
}

/** Picks are stale when the latest successful run targets an earlier session. */
export function isStale(latestSessionDate: string | null, now: Date): boolean {
  return latestSessionDate === null || latestSessionDate < nextUsSession(now);
}

/** Today's calendar date in Jakarta (WIB). */
export function wibDate(now: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jakarta' }).format(now);
}

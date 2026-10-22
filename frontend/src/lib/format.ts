/** "1 sessão", "2 sessões". Passe o plural quando não for apenas "+s". */
export function plural(count: number, one: string, many?: string): string {
  return `${count} ${count === 1 ? one : (many ?? `${one}s`)}`;
}

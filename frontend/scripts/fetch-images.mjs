// Baixa fotografias da Unsplash (Unsplash License) para uma pasta local.
// Uso: node scripts/fetch-images.mjs <pasta> <largura> <qualidade> <id>[:nome] ...
import { mkdir, writeFile } from "node:fs/promises";

const [dir, width, quality, ...items] = process.argv.slice(2);
await mkdir(dir, { recursive: true });

for (const item of items) {
  const [id, name = id] = item.split(":");
  const url = `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${width}&q=${quality}`;
  const res = await fetch(url);
  if (!res.ok) {
    console.log(`${id} FALHOU (${res.status})`);
    continue;
  }
  const buf = Buffer.from(await res.arrayBuffer());
  await writeFile(`${dir}/${name}.jpg`, buf);
  console.log(`${id} ok ${buf.length}`);
}

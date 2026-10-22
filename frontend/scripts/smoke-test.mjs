// Teste de fumaça: sobe o servidor (dev ou start), busca as rotas e reporta status HTTP.
// Uso: node scripts/smoke-test.mjs dev|start [porta]
import { spawn, execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const mode = process.argv[2] === "start" ? "start" : "dev";
const port = process.argv[3] ?? (mode === "start" ? "3112" : "3111");
const routes = [
  "/",
  "/sobre-reiki",
  "/como-funciona",
  "/locais",
  "/agenda",
  "/entrar",
  "/participante",
  "/participante/inscricoes",
  "/participante/notificacoes",
  "/ministrante",
  "/ministrante/disponibilidade",
  "/ministrante/sessoes",
  "/ministrante/convites",
  "/coordenacao",
  "/coordenacao/sessoes",
  "/coordenacao/coberturas",
  "/coordenacao/reorganizacao",
  "/coordenacao/historico",
  "/rota-inexistente",
];

// Executa o bin do Next diretamente com o Node (sem shell): o PID é o do servidor
// e só o processo iniciado por este teste é encerrado no final.
const nextBin = fileURLToPath(new URL("../node_modules/next/dist/bin/next", import.meta.url));
const child = spawn(process.execPath, [nextBin, mode, "-p", port], {
  stdio: ["ignore", "pipe", "pipe"],
});
let log = "";
child.stdout.on("data", (chunk) => (log += chunk));
child.stderr.on("data", (chunk) => (log += chunk));

async function waitReady() {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    try {
      const res = await fetch(`http://localhost:${port}/`);
      if (res.status < 500) return;
    } catch {
      /* ainda subindo */
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("Servidor não respondeu a tempo.");
}

let failed = false;
try {
  await waitReady();
  for (const route of routes) {
    const res = await fetch(`http://localhost:${port}${route}`);
    const html = await res.text();
    const expected = route === "/rota-inexistente" ? 404 : 200;
    const ok = res.status === expected;
    if (!ok) failed = true;
    console.log(`${ok ? "OK  " : "FALHA"} ${res.status} ${route} (${html.length} bytes)`);
  }
} catch (error) {
  failed = true;
  console.error(String(error));
} finally {
  try {
    execSync(`taskkill /pid ${child.pid} /t /f`, { stdio: "ignore" });
  } catch {
    child.kill("SIGTERM");
  }
  const lines = log.split("\n");
  const hits = lines.flatMap((line, index) => (/error|warn|⨯/i.test(line) ? lines.slice(index, index + 8) : []));
  if (hits.length) console.log("\nTrechos de erro/aviso do servidor:\n" + hits.slice(0, 60).join("\n"));
}
console.log(`\nSMOKE ${mode}: ${failed ? "FALHOU" : "OK"} (código de saída ${failed ? 1 : 0})`);
process.exit(failed ? 1 : 0);

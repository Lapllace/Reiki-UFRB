// Verifica o build de PRODUÇÃO (`next start`) em navegador real: a demonstração não pode ligar,
// mesmo com NEXT_PUBLIC_DEMO_MODE=true no .env.local e um perfil gravado no sessionStorage.
// Requer `npm run build` antes e `npm install --no-save puppeteer-core`.
// Uso: node scripts/prod-check.mjs
import { spawn, execSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const PORT = "3114";
const BASE = `http://localhost:${PORT}`;
const executablePath = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].find((path) => existsSync(path));
if (!executablePath) throw new Error("Nenhum navegador encontrado.");

const nextBin = fileURLToPath(new URL("../node_modules/next/dist/bin/next", import.meta.url));
const server = spawn(process.execPath, [nextBin, "start", "-p", PORT], { stdio: ["ignore", "pipe", "pipe"] });
let log = "";
server.stdout.on("data", (c) => (log += c));
server.stderr.on("data", (c) => (log += c));

let results = [];
const record = (ok, name, detail = "") => {
  results.push(ok);
  console.log(`${ok ? "OK   " : "FALHA"} ${name}${detail ? ` — ${detail}` : ""}`);
};
const text = (page, needle, timeout = 20000) =>
  page.waitForFunction((n) => document.body.innerText.includes(n), { timeout }, needle);

let browser = null;
try {
  for (let i = 0; i < 60; i += 1) {
    try {
      if ((await fetch(`${BASE}/`)).status < 500) break;
    } catch {
      /* subindo */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  browser = await puppeteer.launch({ executablePath, headless: true, args: ["--no-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.evaluateOnNewDocument(() => sessionStorage.setItem("reiki-demo-profile", "coordinator"));

  await page.goto(`${BASE}/agenda`, { waitUntil: "domcontentloaded" });
  await text(page, "Servidor ainda não configurado");
  const body = await page.evaluate(() => document.body.innerText);
  record(!body.includes("Modo demonstração"), "agenda em produção não exibe a faixa de demonstração");
  record(!/Sala Girassol|Espaço Ipê|Helena Duarte/.test(body), "agenda em produção não exibe dados fictícios");
  record(body.includes("Servidor ainda não configurado"), "sem API configurada, a agenda mostra erro explícito (não finge dados)");

  await page.goto(`${BASE}/coordenacao`, { waitUntil: "domcontentloaded" });
  await text(page, "Servidor ainda não configurado");
  const panel = await page.evaluate(() => document.body.innerText);
  record(!panel.includes("Visão geral dos ciclos") && !panel.includes("Paulo Henrique"), "perfil gravado no navegador não concede acesso ao painel em produção");

  await page.goto(`${BASE}/entrar`, { waitUntil: "domcontentloaded" });
  await text(page, "Entrar");
  const login = await page.evaluate(() => ({
    form: !!document.querySelector('form input[type="password"]'),
    demo: document.body.innerText.includes("Escolha um perfil"),
  }));
  record(login.form && !login.demo, "login em produção é o formulário real (sem escolha de perfis fictícios)");
} catch (error) {
  record(false, "execução", String(error.message).slice(0, 200));
} finally {
  try {
    if (browser) {
      await browser.close();
    }
  } catch {
    // browser already closed
  }
  try {
    execSync(`taskkill /pid ${server.pid} /t /f`, { stdio: "ignore" });
  } catch {
    server.kill("SIGTERM");
  }
  const ok = results.length > 0 && results.every(Boolean);
  console.log(`\nPROD-CHECK: ${ok ? "OK" : "FALHOU"} (${results.filter(Boolean).length}/${results.length})`);
  process.exit(ok ? 0 : 1);
}

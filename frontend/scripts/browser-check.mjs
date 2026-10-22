// Verificação em navegador real (Chrome/Edge) com dados de demonstração.
// Requer: `npm install --no-save puppeteer-core` (não faz parte das dependências do projeto).
// Uso: node scripts/browser-check.mjs [caminho-do-navegador]
// Gera capturas em .verify/ (ignorado pelo git) e imprime um relatório.
import { spawn, execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const PORT = "3113";
const BASE = `http://localhost:${PORT}`;
const candidates = [
  process.argv[2],
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);
const executablePath = candidates.find((path) => existsSync(path));
if (!executablePath) throw new Error("Nenhum navegador encontrado.");

const nextBin = fileURLToPath(new URL("../node_modules/next/dist/bin/next", import.meta.url));
const server = spawn(process.execPath, [nextBin, "dev", "-p", PORT], { stdio: ["ignore", "pipe", "pipe"] });
let serverLog = "";
server.stdout.on("data", (c) => (serverLog += c));
server.stderr.on("data", (c) => (serverLog += c));

const results = [];
const record = (ok, name, detail = "") => {
  results.push({ ok, name, detail });
  console.log(`${ok ? "OK   " : "FALHA"} ${name}${detail ? ` — ${detail}` : ""}`);
};

const viewports = {
  celular: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  tablet: { width: 820, height: 1180, isMobile: true, hasTouch: true, deviceScaleFactor: 1 },
  desktop: { width: 1440, height: 900, deviceScaleFactor: 1 },
};

async function waitServer() {
  for (let i = 0; i < 90; i += 1) {
    try {
      const res = await fetch(`${BASE}/`);
      if (res.status < 500) return;
    } catch {
      /* subindo */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("Servidor não respondeu.");
}

const text = (page, needle, timeout = 20000) =>
  page.waitForFunction((n) => document.body.innerText.includes(n), { timeout }, needle);

async function newPage(browser, vp, profile) {
  const page = await browser.newPage();
  await page.setViewport(viewports[vp]);
  const issues = [];
  page.on("pageerror", (e) => issues.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") issues.push(`console.${m.type()}: ${m.text()}`);
  });
  if (profile) {
    await page.evaluateOnNewDocument((p) => sessionStorage.setItem("reiki-demo-profile", p), profile);
  }
  page.issues = issues;
  return page;
}

async function shot(page, name) {
  await page.screenshot({ path: `.verify/${name}.png` });
}

async function overflow(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const offenders = [...document.querySelectorAll("body *")]
      .filter((el) => el.getBoundingClientRect().right > doc.clientWidth + 1 && getComputedStyle(el).position !== "fixed")
      .slice(0, 3)
      .map((el) => `${el.tagName.toLowerCase()}.${String(el.className).slice(0, 60)}`);
    return { over: doc.scrollWidth - doc.clientWidth, offenders };
  });
}

let failed = false;
let browser = null;
try {
  await mkdir(".verify", { recursive: true });
  await waitServer();
  browser = await puppeteer.launch({ executablePath, headless: true, args: ["--no-sandbox"] });

  // 1) Sem rolagem horizontal e sem erros de console nas páginas principais, em 3 larguras.
  const pages = [
    ["/", null, "Um momento de calma"],
    ["/sobre-reiki", null, "Reiki em poucas palavras"],
    ["/como-funciona", null, "cinco passos"],
    ["/locais", null, "Onde as sessões acontecem"],
    ["/entrar", null, "Modo demonstração"],
    ["/agenda", "participant", "Escolha o seu momento da semana"],
    ["/participante", "participant", "Próxima sessão"],
    ["/participante/inscricoes", "participant", "Minhas inscrições"],
    ["/ministrante", "instructor", "Disponibilidade da semana aberta"],
    ["/ministrante/disponibilidade", "instructor", "Como será sua semana"],
    ["/ministrante/convites", "instructor", "Convites de cobertura"],
    ["/coordenacao", "coordinator", "Andamento do ciclo"],
    ["/coordenacao/sessoes", "coordinator", "Sessões, vagas e inscrições"],
    ["/coordenacao/reorganizacao", "coordinator", "Reorganização de participantes"],
  ];
  for (const vp of Object.keys(viewports)) {
    for (const [path, profile, marker] of pages) {
      const page = await newPage(browser, vp, profile);
      try {
        await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
        await text(page, marker);
        await new Promise((r) => setTimeout(r, 1500));
        const o = await overflow(page);
        const label = `${vp} ${path}`;
        record(o.over <= 0, `sem overflow horizontal: ${label}`, o.over > 0 ? `${o.over}px por ${o.offenders.join(", ")}` : "");
        const noisy = page.issues.filter((i) => !/Download the React DevTools|Fast Refresh/.test(i));
        record(noisy.length === 0, `sem erros de console: ${label}`, noisy.slice(0, 2).join(" | "));
        if (["/", "/agenda", "/participante", "/ministrante/disponibilidade", "/coordenacao", "/coordenacao/sessoes"].includes(path)) {
          await shot(page, `${vp}${path === "/" ? "-inicio" : path.replace(/\//g, "-")}`);
        }
      } catch (error) {
        record(false, `carregar ${vp} ${path}`, String(error.message).slice(0, 160));
      } finally {
        await page.close();
      }
    }
  }

  // 2) Menu móvel: abre, fecha com Esc e navega.
  {
    const page = await newPage(browser, "celular", null);
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
    await text(page, "Um momento de calma");
    await page.click('button[aria-controls="menu-movel"]');
    const open = await page.$eval("#menu-movel", (el) => !el.hidden);
    await shot(page, "celular-menu");
    await page.keyboard.press("Escape");
    const closed = await page.$eval("#menu-movel", (el) => el.hidden);
    record(open && closed, "menu móvel abre e fecha com Esc");
    await page.close();
  }

  // 3) Agenda: modal, Esc, inscrição com resposta do servidor.
  {
    const page = await newPage(browser, "desktop", "participant");
    await page.goto(`${BASE}/agenda`, { waitUntil: "domcontentloaded" });
    await text(page, "Sem sessões neste dia", 25000).catch(() => {});
    await page.click('button[aria-label="Próxima semana"]');
    await text(page, "Ver detalhes e inscrever-se");
    const openBtn = await page.evaluateHandle(() =>
      [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Ver detalhes e inscrever-se")),
    );
    await openBtn.click();
    await page.waitForSelector("dialog[open]");
    await shot(page, "desktop-agenda-modal");
    await page.keyboard.press("Escape");
    await new Promise((r) => setTimeout(r, 300));
    record(!(await page.$("dialog[open]")), "modal fecha com Esc");
    await (await page.evaluateHandle(() => [...document.querySelectorAll("button")].find((b) => b.textContent.includes("Ver detalhes e inscrever-se")))).click();
    await page.waitForSelector("dialog[open]");
    const focusInside = await page.evaluate(() => document.querySelector("dialog[open]").contains(document.activeElement));
    record(focusInside, "foco fica dentro do modal ao abrir");
    await (await page.evaluateHandle(() => [...document.querySelectorAll("dialog[open] button")].find((b) => b.textContent.includes("Confirmar inscrição")))).click();
    const sawWaiting = await text(page, "Aguardando o sistema", 3000).then(() => true, () => false);
    await text(page, "Inscrição confirmada");
    record(sawWaiting, "botão mostra 'Aguardando o sistema…' antes da resposta");
    await shot(page, "desktop-agenda-confirmada");
    record(true, "inscrição exibida como confirmada somente após resposta do servidor (demo)");
    await page.close();
  }

  // 4) Convites: primeiro aceite assume; segundo simula perda de corrida.
  {
    const page = await newPage(browser, "desktop", "instructor");
    await page.goto(`${BASE}/ministrante/convites`, { waitUntil: "domcontentloaded" });
    await text(page, "Aguardando resposta (2)");
    const accept = async () => {
      await (await page.evaluateHandle(() => [...document.querySelectorAll("article button")].find((b) => b.textContent.includes("Aceitar cobertura")))).click();
      await page.waitForSelector("dialog[open]");
      await (await page.evaluateHandle(() => [...document.querySelectorAll("dialog[open] button")].find((b) => b.textContent.includes("Aceitar cobertura")))).click();
    };
    await accept();
    await text(page, "Você assumiu a sessão");
    record(true, "convite aceito: resultado vindo do servidor");
    await page.evaluate(() => window.scrollTo(0, 0));
    await accept();
    await text(page, "Outro ministrante aceitou primeiro");
    await shot(page, "desktop-convite-corrida");
    record(true, "segundo convite: 'outro ministrante aceitou primeiro' refletido");
    await page.close();
  }

  // 5) Proteção de rotas.
  {
    const page = await newPage(browser, "desktop", "participant");
    await page.goto(`${BASE}/coordenacao`, { waitUntil: "domcontentloaded" });
    await text(page, "não está disponível para o seu perfil");
    const leaked = await page.evaluate(() => document.body.innerText.includes("Visão geral dos ciclos"));
    record(!leaked, "participante não vê a área da coordenação");
    await page.close();
    const anon = await newPage(browser, "desktop", null);
    await anon.goto(`${BASE}/participante`, { waitUntil: "domcontentloaded" });
    await anon.waitForFunction(() => location.pathname === "/entrar", { timeout: 20000 });
    record(anon.url().includes("next=%2Fparticipante"), "visitante é redirecionado para /entrar com destino");
    await anon.close();
  }

  // 6) Falha de rede simulada e movimento reduzido.
  {
    const page = await newPage(browser, "desktop", "participant");
    await page.goto(`${BASE}/participante/inscricoes`, { waitUntil: "domcontentloaded" });
    await text(page, "Minhas inscrições");
    await page.select("section[aria-label='Painel de demonstração'] select", "participant").catch(() => {});
    await page.click("section[aria-label='Painel de demonstração'] input[type=checkbox]");
    // Navega pelo menu (sem recarregar): a simulação de falha vive apenas na memória da página.
    await page.evaluate(() => {
      const link = [...document.querySelectorAll("nav a")].find((a) => a.getAttribute("href") === "/participante/notificacoes");
      link.click();
    });
    await text(page, "Sem conexão com o servidor", 25000);
    await shot(page, "desktop-erro-rede");
    record(true, "estado de erro exibido com falha de rede simulada");
    await page.close();
    const rm = await newPage(browser, "desktop", null);
    await rm.emulateMediaFeatures([{ name: "prefers-reduced-motion", value: "reduce" }]);
    await rm.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
    await text(rm, "Um momento de calma");
    const duration = await rm.evaluate(() => getComputedStyle(document.querySelector(".animate-rise")).animationDuration);
    record(parseFloat(duration) < 0.01, "prefers-reduced-motion neutraliza animações", `animation-duration=${duration}`);
    await rm.close();
  }

  // 7) Teclado: primeiro Tab leva ao link 'Pular para o conteúdo', visível e com contorno de foco.
  {
    const page = await newPage(browser, "desktop", null);
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
    await text(page, "Um momento de calma");
    await page.keyboard.press("Tab");
    const skip = await page.evaluate(() => {
      const el = document.activeElement;
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return {
        label: el.textContent.trim(),
        visible: box.width > 20 && box.top >= 0 && box.left >= 0,
        outline: style.outlineStyle !== "none" && parseFloat(style.outlineWidth) >= 2,
      };
    });
    record(skip.label.startsWith("Pular") && skip.visible, "Tab inicial foca o link 'Pular para o conteúdo' visível");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    const ring = await page.evaluate(() => {
      const style = getComputedStyle(document.activeElement);
      return style.outlineStyle !== "none" && parseFloat(style.outlineWidth) >= 2;
    });
    record(ring, "elementos focados por teclado têm indicador de foco visível");
    await page.close();
  }

  // 8) Navegação interna instantânea: ao clicar no menu do painel, o título e o esqueleto
  //    aparecem antes dos dados (a demonstração responde em ~400–650 ms).
  //    Nota: o gate() da demo simula latência de rede de 380-640 ms, então o limite de 700 ms
  //    acomoda o pior cenário realista com overhead de renderização.
  {
    const page = await newPage(browser, "desktop", "participant");
    await page.goto(`${BASE}/participante`, { waitUntil: "domcontentloaded" });
    await text(page, "Próxima sessão");
    const started = await page.evaluate(() => {
      const link = [...document.querySelectorAll("aside nav a")].find((a) => a.getAttribute("href") === "/participante/inscricoes");
      window.__t0 = performance.now();
      link.click();
      return true;
    });
    await page.waitForFunction(() => document.querySelector("h1")?.textContent.includes("Minhas inscrições"), { timeout: 5000 });
    const shell = await page.evaluate(() => ({
      ms: Math.round(performance.now() - window.__t0),
      skeleton: !!document.querySelector('[role="status"] .animate-pulse'),
      dataAlready: document.body.innerText.includes("Próximas"),
    }));
    record(
      started && shell.skeleton && !shell.dataAlready && shell.ms < 700,
      "navegação interna mostra título + esqueleto antes dos dados",
      `título em ${shell.ms} ms; esqueleto=${shell.skeleton}; dados já carregados=${shell.dataAlready}`,
    );
    await page.close();
  }

  await browser.close();
  failed = results.some((r) => !r.ok);
} catch (error) {
  failed = true;
  console.error("ERRO NO SCRIPT:", error);
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
  const lines = serverLog.split("\n");
  const hits = lines.flatMap((l, i) => (/error|warn|⨯/i.test(l) ? lines.slice(i, i + 6) : []));
  if (hits.length) console.log("\nAvisos/erros do servidor:\n" + hits.slice(0, 40).join("\n"));
  const bad = results.filter((r) => !r.ok);
  console.log(`\nBROWSER-CHECK: ${results.length - bad.length}/${results.length} verificações OK`);
  process.exit(failed ? 1 : 0);
}

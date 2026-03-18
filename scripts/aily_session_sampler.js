#!/usr/bin/env node

const fs = require("node:fs/promises");
const path = require("node:path");

function printUsage(exitCode) {
  console.error(
    [
      "Usage:",
      "  node scripts/aily_session_sampler.js --url <aily-url> [options]",
      "",
      "Options:",
      "  --profile-dir <path>         Persistent browser profile directory",
      "  --output-dir <path>          Artifact directory",
      "  --headed                     Open a visible browser window",
      "  --wait-for-auth              Wait for manual Feishu login to complete",
      "  --auth-timeout-seconds <n>   Manual login wait timeout",
      "  --settle-ms <n>              Delay before extracting page content",
      "  --help                       Show this message",
    ].join("\n")
  );
  process.exit(exitCode);
}

function parseArgs(argv) {
  const options = {
    headed: false,
    waitForAuth: false,
    authTimeoutSeconds: 900,
    settleMs: 4000,
    profileDir: path.resolve(
      "output",
      "feishu-reader",
      "state",
      "browser-profile",
      "feishu-reader"
    ),
    outputDir: path.resolve("output", "aily-session-sampler"),
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--url") {
      options.url = argv[++index];
    } else if (arg === "--profile-dir") {
      options.profileDir = path.resolve(argv[++index]);
    } else if (arg === "--output-dir") {
      options.outputDir = path.resolve(argv[++index]);
    } else if (arg === "--headed") {
      options.headed = true;
    } else if (arg === "--wait-for-auth") {
      options.waitForAuth = true;
    } else if (arg === "--auth-timeout-seconds") {
      options.authTimeoutSeconds = Number(argv[++index]);
    } else if (arg === "--settle-ms") {
      options.settleMs = Number(argv[++index]);
    } else if (arg === "--help" || arg === "-h") {
      printUsage(0);
    } else {
      console.error(`Unknown argument: ${arg}`);
      printUsage(1);
    }
  }

  if (!options.url) {
    console.error("--url is required");
    printUsage(1);
  }

  return options;
}

function looksLikeLogin(url, text) {
  const urlLogin =
    url.includes("accounts.feishu.cn") || url.includes("/accounts/page/login");
  const lowered = text.toLowerCase();
  const textLogin = [
    "扫码登录",
    "请使用飞书移动端扫描二维码",
    "登录飞书",
    "sign in",
    "log in",
  ].some((token) => lowered.includes(token));
  return urlLogin || textLogin;
}

function collectAilyLinks(links) {
  const categories = {
    base_links: [],
    dashboard_links: [],
    doc_links: [],
    other_links: [],
  };

  for (const link of links) {
    if (link.href.includes("/base/") || link.href.includes("/bitable/")) {
      categories.base_links.push(link);
    } else if (link.href.includes("/dashboard")) {
      categories.dashboard_links.push(link);
    } else if (link.href.includes("/doc") || link.href.includes("/wiki/")) {
      categories.doc_links.push(link);
    } else {
      categories.other_links.push(link);
    }
  }

  return categories;
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function writeJson(filePath, payload) {
  await fs.writeFile(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

function renderMarkdown(summary) {
  const lines = [
    "# Aily Session Sampler",
    "",
    `- sampled_at: ${summary.sampled_at}`,
    `- status: ${summary.status}`,
    `- final_url: ${summary.final_url}`,
    `- title: ${summary.title || ""}`,
    `- screenshot: ${summary.screenshot_path || ""}`,
    "",
    "## Page Text Preview",
    "",
    "```text",
    summary.text_preview || "",
    "```",
    "",
    "## Extracted Links",
    "",
    `- base_links: ${summary.link_groups.base_links.length}`,
    `- dashboard_links: ${summary.link_groups.dashboard_links.length}`,
    `- doc_links: ${summary.link_groups.doc_links.length}`,
    `- other_links: ${summary.link_groups.other_links.length}`,
    "",
  ];

  for (const [groupName, items] of Object.entries(summary.link_groups)) {
    if (!items.length) continue;
    lines.push(`### ${groupName}`, "");
    for (const item of items) {
      lines.push(`- [${item.text || item.href}](${item.href})`);
    }
    lines.push("");
  }

  return `${lines.join("\n").trim()}\n`;
}

async function waitForManualAuth(page, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await page.waitForTimeout(2000);
    const url = page.url();
    const text = ((await page.locator("body").innerText().catch(() => "")) || "").slice(0, 2000);
    if (!looksLikeLogin(url, text)) {
      return true;
    }
  }
  return false;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const { chromium } = require("playwright");
  const outputDir = path.resolve(options.outputDir);
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const runDir = path.join(outputDir, timestamp);
  const screenshotPath = path.join(runDir, "page.png");
  const jsonPath = path.join(runDir, "result.json");
  const mdPath = path.join(runDir, "result.md");

  await ensureDir(runDir);

  const context = await chromium.launchPersistentContext(options.profileDir, {
    headless: !options.headed,
    viewport: { width: 1440, height: 960 },
  });

  try {
    const page = context.pages()[0] || (await context.newPage());
    await page.goto(options.url, { waitUntil: "domcontentloaded", timeout: 45000 });

    let bodyText = ((await page.locator("body").innerText().catch(() => "")) || "").slice(0, 6000);
    if (options.waitForAuth && looksLikeLogin(page.url(), bodyText)) {
      console.log("Waiting for manual Feishu login in the visible browser window...");
      const authenticated = await waitForManualAuth(page, options.authTimeoutSeconds * 1000);
      if (!authenticated) {
        throw new Error("Manual login did not complete before the timeout.");
      }
      await page.goto(options.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    }

    await page.waitForTimeout(options.settleMs);
    bodyText = ((await page.locator("body").innerText().catch(() => "")) || "").slice(0, 6000);
    const links = await page
      .locator("a")
      .evaluateAll((anchors) =>
        anchors
          .map((anchor) => ({
            text: (anchor.textContent || "").trim(),
            href: anchor.href || "",
          }))
          .filter((item) => item.href)
      )
      .catch(() => []);

    await page.screenshot({ path: screenshotPath, fullPage: true });

    const summary = {
      sampled_at: new Date().toISOString(),
      requested_url: options.url,
      final_url: page.url(),
      title: await page.title().catch(() => ""),
      status: looksLikeLogin(page.url(), bodyText) ? "login_required" : "accessible",
      profile_dir: options.profileDir,
      screenshot_path: screenshotPath,
      text_preview: bodyText.slice(0, 2000),
      text_full: bodyText,
      link_groups: collectAilyLinks(links),
      raw_links: links,
    };

    await writeJson(jsonPath, summary);
    await fs.writeFile(mdPath, renderMarkdown(summary), "utf8");

    console.log(
      JSON.stringify(
        {
          run_dir: runDir,
          json_path: jsonPath,
          md_path: mdPath,
          screenshot_path: screenshotPath,
          status: summary.status,
        },
        null,
        2
      )
    );
  } finally {
    await context.close();
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});

(() => {
  const SOURCE_SUFFIX = ".md.txt";

  function docsRoot() {
    const script =
      document.currentScript || document.querySelector('script[src*="copy_as_markdown.js"]');
    const src = script ? new URL(script.src, window.location.href) : null;
    if (!src) {
      return new URL("./", window.location.href);
    }
    return new URL(src.pathname.replace(/_static\/.*$/, ""), src.origin);
  }

  function pageName(root) {
    const current = new URL(window.location.href);
    let path = current.pathname.slice(root.pathname.length);
    if (!path || path.endsWith("/")) {
      path += "index.html";
    }
    return path.replace(/\.html$/, "").replace(/\/$/, "/index");
  }

  async function sourceMarkdown(root) {
    const sourceUrl = new URL(`_sources/${pageName(root)}${SOURCE_SUFFIX}`, root);
    const response = await fetch(sourceUrl);
    if (!response.ok) {
      throw new Error(`No Markdown source at ${sourceUrl.pathname}`);
    }
    return response.text();
  }

  function textContent(node) {
    return node.textContent.replace(/\s+/g, " ").trim();
  }

  function fence(code) {
    const text = code.replace(/\n+$/, "");
    const fenceText = text.includes("```") ? "````" : "```";
    return `\n${fenceText}\n${text}\n${fenceText}\n`;
  }

  function tableMarkdown(table) {
    const rows = [...table.querySelectorAll("tr")].map((row) =>
      [...row.children].map((cell) => textContent(cell).replace(/\|/g, "\\|")),
    );
    if (rows.length === 0) {
      return "";
    }
    const header = rows[0];
    const divider = header.map(() => "---");
    return [header, divider, ...rows.slice(1)]
      .map((row) => `| ${row.join(" | ")} |`)
      .join("\n");
  }

  function inlineMarkdown(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    const content = [...node.childNodes].map(inlineMarkdown).join("");
    switch (node.tagName.toLowerCase()) {
      case "code":
        return `\`${node.textContent}\``;
      case "strong":
      case "b":
        return `**${content}**`;
      case "em":
      case "i":
        return `_${content}_`;
      case "a": {
        const href = node.getAttribute("href");
        return href ? `[${content}](${href})` : content;
      }
      default:
        return content;
    }
  }

  function blockMarkdown(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) {
      return "";
    }
    const tag = node.tagName.toLowerCase();
    if (/^h[1-6]$/.test(tag)) {
      const level = Number(tag[1]);
      return `${"#".repeat(level)} ${textContent(node).replace(/¶$/, "")}`;
    }
    if (tag === "p") {
      return inlineMarkdown(node).replace(/\s+/g, " ").trim();
    }
    if (tag === "pre") {
      return fence(node.textContent);
    }
    if (tag === "table") {
      return tableMarkdown(node);
    }
    if (tag === "ul" || tag === "ol") {
      return [...node.children]
        .map((li, index) => `${tag === "ol" ? `${index + 1}.` : "-"} ${inlineMarkdown(li).trim()}`)
        .join("\n");
    }
    if (tag === "section" || tag === "article" || tag === "div") {
      return [...node.children].map(blockMarkdown).filter(Boolean).join("\n\n");
    }
    return "";
  }

  function articleMarkdown() {
    const article = document.querySelector("article");
    if (!article) {
      return document.body.innerText.trim();
    }
    return blockMarkdown(article).trim();
  }

  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }

  function setStatus(button, text) {
    const label = button.querySelector(".copy-markdown-label");
    label.textContent = text;
  }

  function makeButton(root) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-markdown-button";
    button.title = "Copy page as markdown";
    button.setAttribute("aria-label", "Copy page as markdown");
    button.innerHTML = `
      <svg aria-hidden="true" class="copy-markdown-icon" viewBox="0 0 24 24">
        <path d="M6 3h9l5 5v13H6z" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/>
        <path d="M15 3v6h6" fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8"/>
        <path d="M9 17V12l2.3 2.7L13.6 12v5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/>
        <path d="M16 12v5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8"/>
      </svg>
      <span class="copy-markdown-label">Copy page as markdown</span>
    `;
    button.addEventListener("click", async () => {
      button.disabled = true;
      setStatus(button, "Copying…");
      try {
        let markdown;
        try {
          markdown = await sourceMarkdown(root);
        } catch {
          markdown = articleMarkdown();
        }
        await copyText(markdown.trimEnd() + "\n");
        setStatus(button, "Copied");
      } catch {
        setStatus(button, "Failed");
      } finally {
        window.setTimeout(() => {
          button.disabled = false;
          setStatus(button, "Copy page as markdown");
        }, 1800);
      }
    });
    return button;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const container = document.querySelector(".content-icon-container");
    if (!container) {
      return;
    }
    container.prepend(makeButton(docsRoot()));
  });
})();

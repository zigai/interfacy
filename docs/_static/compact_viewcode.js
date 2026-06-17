(() => {
  function compactViewcodeBlocks() {
    if (!window.location.pathname.includes("/_modules/")) {
      return;
    }

    document.querySelectorAll(".viewcode-block").forEach((block) => {
      const previous = block.previousSibling;
      if (
        previous instanceof Text
        && /^\n{3,}$/.test(previous.nodeValue || "")
      ) {
        previous.nodeValue = "\n\n";
      }

      const first = block.firstChild;
      if (first instanceof Text && first.nodeValue === "\n") {
        first.remove();
      }

      const backLink = block.querySelector(":scope > .viewcode-back");
      const afterBackLink = backLink?.nextSibling;
      if (afterBackLink instanceof Text && afterBackLink.nodeValue === "\n") {
        afterBackLink.remove();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", compactViewcodeBlocks);
  } else {
    compactViewcodeBlocks();
  }
})();

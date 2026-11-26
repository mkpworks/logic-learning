(function () {
  function searchInput() {
    return document.querySelector("[data-md-component='search-query']");
  }

  function openSearch(query) {
    var toggle = document.getElementById("__search");
    var input = searchInput();
    if (toggle) {
      toggle.checked = true;
    }
    if (!input) {
      return;
    }
    if (typeof query === "string") {
      input.value = query;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true }));
    }
    input.focus();
  }

  function isSearchLink(link) {
    var href = link.getAttribute("href") || "";
    try {
      var url = new URL(href, window.location.href);
      return /\/search\/?$/.test(url.pathname);
    } catch (error) {
      return false;
    }
  }

  function bind(root) {
    (root || document).querySelectorAll("[data-notebook-search]").forEach(function (field) {
      if (field.dataset.notebookBound) {
        return;
      }
      field.dataset.notebookBound = "1";
      field.addEventListener("focus", function () {
        openSearch(field.value);
      });
      field.addEventListener("input", function () {
        openSearch(field.value);
      });
    });

    (root || document).querySelectorAll("a.md-nav__link, a.md-tabs__link").forEach(function (link) {
      if (link.dataset.searchBound || !isSearchLink(link)) {
        return;
      }
      link.dataset.searchBound = "1";
      link.addEventListener("click", function (event) {
        event.preventDefault();
        openSearch("");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    bind(document);
    if (/\/search\/?$/.test(window.location.pathname)) {
      openSearch("");
    }
  });
})();

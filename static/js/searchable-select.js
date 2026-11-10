(() => {
  "use strict";

  const normalize = (text) => text.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase();

  document.querySelectorAll("select[data-searchable-select]").forEach((select) => {
    if (select.multiple || select.disabled || select.dataset.enhanced) return;

    const options = Array.from(select.options).filter((option) => !option.disabled);
    const root = document.createElement("div");
    root.className = "searchable-select";
    const input = document.createElement("input");
    input.type = "text";
    input.id = select.id;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.title = select.dataset.searchPlaceholder;
    for (const attribute of ["aria-describedby", "aria-invalid"]) {
      if (select.hasAttribute(attribute)) input.setAttribute(attribute, select.getAttribute(attribute));
    }

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "searchable-select-toggle";
    toggle.tabIndex = -1;
    toggle.setAttribute("aria-label", select.dataset.openLabel);
    toggle.setAttribute("aria-expanded", "false");
    toggle.textContent = "⌄";

    const dropdown = document.createElement("div");
    dropdown.className = "searchable-select-dropdown";
    dropdown.hidden = true;
    const list = document.createElement("div");
    list.id = `${input.id}-options`;
    list.setAttribute("role", "listbox");
    // Use the existing field label to name both the input and its list.
    const label = document.querySelector(`label[for="${select.id}"]`);
    if (label) {
      if (!label.id) label.id = `${input.id}-label`;
      list.setAttribute("aria-labelledby", label.id);
    }
    input.setAttribute("aria-controls", list.id);
    toggle.setAttribute("aria-controls", list.id);
    const empty = document.createElement("div");
    empty.className = "searchable-select-empty";
    empty.setAttribute("role", "status");
    empty.textContent = select.dataset.noResults;
    dropdown.append(list, empty);

    let matches = [];
    let active = -1;

    function restore() {
      const selected = options.find((option) => option.value === select.value);
      input.value = selected?.value ? selected.label : "";
      input.placeholder = options.find((option) => option.value === "")?.label || "";
    }

    function close() {
      dropdown.hidden = true;
      input.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      restore();
    }

    function activate(index, scroll = false) {
      active = index;
      Array.from(list.children).forEach((item, position) => item.classList.toggle("is-active", position === active));
      const item = list.children[active];
      if (item) {
        input.setAttribute("aria-activedescendant", item.id);
        if (scroll) item.scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }

    function choose(option) {
      const changed = select.value !== option.value;
      select.value = option.value;
      close();
      if (changed) select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function open(query = "") {
      const terms = normalize(query).trim().split(/\s+/).filter(Boolean);
      matches = options.filter((option) => terms.every((term) => normalize(option.label).includes(term)));
      list.replaceChildren();
      matches.forEach((option, index) => {
        const item = document.createElement("div");
        item.id = `${list.id}-${index}`;
        item.className = "searchable-select-option";
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", String(option.value === select.value));
        item.textContent = option.label;
        item.addEventListener("click", () => choose(option));
        list.append(item);
      });
      empty.hidden = matches.length > 0;
      dropdown.hidden = false;
      input.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-expanded", "true");
      const selected = matches.findIndex((option) => option.value === select.value);
      activate(selected >= 0 ? selected : matches.length ? 0 : -1);
    }

    input.addEventListener("focus", () => {
      input.select();
      open();
      input.placeholder = select.dataset.searchPlaceholder;
    });
    input.addEventListener("click", () => {
      if (dropdown.hidden) {
        input.select();
        open();
      }
    });
    input.addEventListener("input", () => {
      if (input.value === "" && options.some((option) => option.value === "")) {
        const changed = select.value !== "";
        select.value = "";
        if (changed) select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      open(input.value);
    });
    input.addEventListener("keydown", (event) => {
      if (event.isComposing) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        if (dropdown.hidden) {
          open();
        } else if (matches.length) {
          const step = event.key === "ArrowDown" ? 1 : -1;
          activate((active + step + matches.length) % matches.length, true);
        }
      } else if (event.key === "Enter" && !dropdown.hidden) {
        event.preventDefault();
        if (matches[active]) choose(matches[active]);
      } else if (event.key === "Escape" && !dropdown.hidden) {
        event.preventDefault();
        event.stopPropagation();
        close();
      } else if (event.key === "Tab") {
        close();
      }
    });
    root.addEventListener("focusout", (event) => {
      if (!root.contains(event.relatedTarget)) close();
    });
    // Keep focus in the input until a mouse selection has been committed.
    dropdown.addEventListener("mousedown", (event) => event.preventDefault());
    toggle.addEventListener("mousedown", (event) => event.preventDefault());
    toggle.addEventListener("click", () => {
      const wasOpen = !dropdown.hidden;
      input.focus();
      if (wasOpen) close();
      else open();
    });
    select.addEventListener("change", restore);
    select.form?.addEventListener("reset", () => setTimeout(close, 0));

    select.before(root);
    root.append(select, input, toggle, dropdown);
    select.id = `${input.id}-native`;
    select.hidden = true;
    select.dataset.enhanced = "true";
    restore();
  });
})();

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const script = readFileSync(resolve(__dirname, "../../../static/js/searchable-select.js"), "utf8");

// A small DOM double exercises events and submitted values without a browser dependency.
class Element extends EventTarget {
  constructor(tagName) {
    super();
    this.tagName = tagName;
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.classes = new Set();
    this.classList = { toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name) };
    this.value = "";
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  hasAttribute(name) { return this.attributes.has(name); }
  removeAttribute(name) { this.attributes.delete(name); }
  append(...elements) {
    for (const element of elements) {
      if (element.parent) element.parent.children.splice(element.parent.children.indexOf(element), 1);
      element.parent = this;
      this.children.push(element);
    }
  }
  before(element) {
    element.parent = this.parent;
    this.parent.children.splice(this.parent.children.indexOf(this), 0, element);
  }
  replaceChildren() { this.children = []; }
  contains(target) { return target === this || this.children.some((child) => child.contains(target)); }
  select() {}
  scrollIntoView() {}
  focus() {
    if (this.document.activeElement !== this) {
      this.document.activeElement = this;
      this.dispatchEvent(new Event("focus"));
    }
  }
}

function fire(element, type, properties = {}) {
  const event = new Event(type, { cancelable: true });
  Object.assign(event, properties);
  element.dispatchEvent(event);
  return event;
}

function fixture(value = "") {
  const body = new Element("body");
  const label = new Element("label");
  const select = new Element("select");
  select.id = "id_owner";
  select.name = "owner";
  select.value = value;
  select.form = new Element("form");
  select.options = [
    { value: "", label: "All owners" },
    { value: "1", label: "North \u00c9ngineering" },
    { value: "2", label: "South Rail" },
    { value: "unassigned", label: "Owner not recorded" },
  ];
  select.dataset = {
    searchableSelect: "true", noResults: "No matching options.",
    openLabel: "Show options", searchPlaceholder: "Type to filter options",
  };
  select.setAttribute("aria-describedby", "id_owner_error");
  select.setAttribute("aria-invalid", "true");
  body.append(label, select);
  const document = {
    createElement: (tagName) => Object.assign(new Element(tagName), { document }),
    querySelectorAll: () => [select], querySelector: () => label,
  };
  const initialize = () => runInNewContext(script, { document, Event, setTimeout });
  initialize();
  const root = body.children[1];
  const [, input, toggle, dropdown] = root.children;
  const [list, empty] = dropdown.children;
  const type = (text) => { input.value = text; fire(input, "input"); };
  const key = (key) => fire(input, "keydown", { key });
  return { select, root, input, toggle, dropdown, list, empty, initialize, type, key };
}

test("typing narrows options by words, case and accents; clicking submits the original ID", () => {
  const field = fixture();
  let changes = 0;
  field.select.addEventListener("change", () => changes++);
  field.input.focus();
  field.type("ENGINE north");
  assert.equal(field.list.children.length, 1);
  assert.equal(field.list.children[0].textContent, "North \u00c9ngineering");
  fire(field.list.children[0], "click");
  assert.equal(field.select.value, "1");
  assert.equal(field.input.value, "North \u00c9ngineering");
  assert.equal(field.dropdown.hidden, true);
  assert.equal(changes, 1);
});

test("arrow keys and Enter choose an option without submitting the form", () => {
  const field = fixture();
  field.input.focus();
  assert.equal(field.key("ArrowDown").defaultPrevented, true);
  assert.equal(field.input.getAttribute("aria-activedescendant"), field.list.children[1].id);
  assert.equal(field.key("Enter").defaultPrevented, true);
  assert.equal(field.select.value, "1");
  assert.equal(field.input.getAttribute("aria-expanded"), "false");
  assert.equal(field.input.getAttribute("aria-activedescendant"), null);
});

test("Escape and Tab discard an unfinished search and preserve the committed selection", () => {
  const field = fixture("2");
  field.input.focus();
  for (const key of ["Escape", "Tab"]) {
    field.type("North");
    field.key(key);
    assert.equal(field.select.value, "2");
    assert.equal(field.input.value, "South Rail");
    assert.equal(field.dropdown.hidden, true);
  }
});

test("clearing a selected field clears the submitted filter", () => {
  const field = fixture("2");
  field.input.focus();
  field.type("");
  assert.equal(field.select.value, "");
  assert.equal(field.list.children.length, 4);
  field.key("Tab");
  assert.equal(field.input.value, "");
  assert.equal(field.input.placeholder, "All owners");
});

test("no matches shows a message and cannot commit an arbitrary value", () => {
  const field = fixture("2");
  field.input.focus();
  field.type("missing");
  assert.equal(field.list.children.length, 0);
  assert.equal(field.empty.hidden, false);
  assert.equal(field.key("Enter").defaultPrevented, true);
  assert.equal(field.select.value, "2");
  fire(field.root, "focusout", { relatedTarget: null });
  assert.equal(field.input.value, "South Rail");
});

test("enhancement preserves form submission, labels and errors and runs only once", () => {
  const field = fixture("unassigned");
  assert.equal(field.select.name, "owner");
  assert.equal(field.select.hidden, true);
  assert.equal(field.select.id, "id_owner-native");
  assert.equal(field.input.id, "id_owner");
  assert.equal(field.input.getAttribute("role"), "combobox");
  assert.equal(field.input.getAttribute("aria-invalid"), "true");
  assert.equal(field.input.getAttribute("aria-describedby"), "id_owner_error");
  assert.equal(field.list.getAttribute("aria-labelledby"), "id_owner-label");
  field.initialize();
  assert.equal(field.root.children.length, 4);
});

test("the toggle opens and closes the options", () => {
  const field = fixture();
  fire(field.toggle, "click");
  assert.equal(field.dropdown.hidden, false);
  fire(field.toggle, "click");
  assert.equal(field.dropdown.hidden, true);
});

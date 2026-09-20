(() => {
  const state = {
    path: "",
    clipboard: null, // { mode: 'copy'|'cut', path, name }
    searchMode: false,
    editor: { path: "", encoding: "utf-8" },
  };

  const $ = (id) => document.getElementById(id);
  const fileBody = $("fileBody");
  const breadcrumb = $("breadcrumb");
  const rootLabel = $("rootLabel");
  const clipStatus = $("clipStatus");
  const pasteBtn = $("pasteBtn");
  const toastEl = $("toast");
  const emptyHint = $("emptyHint");

  function toast(msg, type = "ok") {
    toastEl.hidden = false;
    toastEl.textContent = msg;
    toastEl.className = "toast " + type;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { toastEl.hidden = true; }, 3200);
  }

  async function api(url, options) {
    const res = await fetch(url, options);
    let data = null;
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      data = await res.json();
    } else {
      data = await res.text();
    }
    if (!res.ok) {
      const detail = (data && data.detail) || data || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function formatSize(n) {
    if (n == null) return "—";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
    return (n / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  }

  function updateClipUI() {
    if (!state.clipboard) {
      clipStatus.textContent = "";
      pasteBtn.disabled = true;
      return;
    }
    const label = state.clipboard.mode === "cut" ? "剪切" : "复制";
    clipStatus.textContent = label + ": " + state.clipboard.name;
    pasteBtn.disabled = false;
  }

  function renderBreadcrumb(crumbs) {
    breadcrumb.innerHTML = "";
    crumbs.forEach((c, i) => {
      if (i > 0) {
        const sep = document.createElement("span");
        sep.className = "sep";
        sep.textContent = "/";
        breadcrumb.appendChild(sep);
      }
      if (i === crumbs.length - 1 && !state.searchMode) {
        const span = document.createElement("span");
        span.className = "current";
        span.textContent = c.name || "根目录";
        breadcrumb.appendChild(span);
      } else {
        const a = document.createElement("a");
        a.href = "#";
        a.textContent = c.name || "根目录";
        a.addEventListener("click", (e) => {
          e.preventDefault();
          state.searchMode = false;
          $("clearSearchBtn").hidden = true;
          loadList(c.path);
        });
        breadcrumb.appendChild(a);
      }
    });
  }

  function isProbablyText(name) {
    const ext = (name.split(".").pop() || "").toLowerCase();
    return [
      "txt", "md", "markdown", "json", "js", "ts", "jsx", "tsx", "css", "scss",
      "html", "htm", "xml", "yml", "yaml", "toml", "ini", "cfg", "conf",
      "py", "java", "c", "cpp", "h", "hpp", "cs", "go", "rs", "rb", "php",
      "sh", "bat", "ps1", "sql", "csv", "log", "env", "gitignore", "dockerignore",
      "vue", "svelte", "kt", "swift", "r", "lua", "pl",
    ].includes(ext) || !name.includes(".");
  }

  function renderEntries(entries) {
    fileBody.innerHTML = "";
    emptyHint.hidden = entries.length > 0;

    entries.forEach((ent) => {
      const tr = document.createElement("tr");

      const tdName = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "name-cell";
      const icon = document.createElement("span");
      icon.className = "icon";
      icon.textContent = ent.is_dir ? "📁" : "📄";
      const link = document.createElement("a");
      link.href = "#";
      link.textContent = ent.name;
      link.addEventListener("click", (e) => {
        e.preventDefault();
        if (ent.is_dir) {
          state.searchMode = false;
          $("clearSearchBtn").hidden = true;
          loadList(ent.path);
        } else if (isProbablyText(ent.name)) {
          openEditor(ent.path, ent.name);
        } else {
          window.location.href = "/api/download?path=" + encodeURIComponent(ent.path);
        }
      });
      wrap.append(icon, link);
      tdName.appendChild(wrap);

      const tdSize = document.createElement("td");
      tdSize.textContent = ent.is_dir ? "—" : formatSize(ent.size);

      const tdMtime = document.createElement("td");
      tdMtime.textContent = ent.mtime || "—";

      const tdAct = document.createElement("td");
      const acts = document.createElement("div");
      acts.className = "actions";

      const addBtn = (label, fn, cls) => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = label;
        if (cls) b.className = cls;
        b.addEventListener("click", fn);
        acts.appendChild(b);
      };

      if (!ent.is_dir) {
        addBtn("下载", () => {
          window.location.href = "/api/download?path=" + encodeURIComponent(ent.path);
        });
        if (isProbablyText(ent.name)) {
          addBtn("编辑", () => openEditor(ent.path, ent.name));
        }
      }
      addBtn("复制", () => {
        state.clipboard = { mode: "copy", path: ent.path, name: ent.name };
        updateClipUI();
        toast("已复制: " + ent.name);
      });
      addBtn("剪切", () => {
        state.clipboard = { mode: "cut", path: ent.path, name: ent.name };
        updateClipUI();
        toast("已剪切: " + ent.name);
      });
      addBtn("重命名", () => openRename(ent));
      addBtn("删除", async () => {
        if (!confirm("确定删除\n" + ent.name + " ?")) return;
        try {
          await api("/api/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: ent.path }),
          });
          toast("已删除");
          reload();
        } catch (err) {
          toast(err.message, "error");
        }
      }, "danger");

      tdAct.appendChild(acts);
      tr.append(tdName, tdSize, tdMtime, tdAct);
      fileBody.appendChild(tr);
    });
  }

  async function loadList(path) {
    state.path = path || "";
    try {
      const data = await api("/api/list?path=" + encodeURIComponent(state.path));
      rootLabel.textContent = "根目录: " + data.root;
      renderBreadcrumb(data.breadcrumb || []);
      renderEntries(data.entries || []);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  async function doSearch() {
    const q = $("searchInput").value.trim();
    if (!q) return;
    try {
      const data = await api(
        "/api/search?q=" + encodeURIComponent(q) + "&path=" + encodeURIComponent(state.path)
      );
      state.searchMode = true;
      $("clearSearchBtn").hidden = false;
      renderBreadcrumb([
        { name: "根目录", path: "" },
        { name: "搜索: " + q, path: state.path },
      ]);
      renderEntries(data.results || []);
      toast("找到 " + (data.results || []).length + " 项");
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function reload() {
    if (state.searchMode) doSearch();
    else loadList(state.path);
  }

  function openRename(ent) {
    const dlg = $("renameDialog");
    const input = $("renameInput");
    input.value = ent.name;
    dlg.showModal();
    input.focus();
    input.select();

    const form = $("renameForm");
    const onSubmit = async (e) => {
      e.preventDefault();
      const newName = input.value.trim();
      if (!newName || newName === ent.name) {
        dlg.close();
        return;
      }
      try {
        await api("/api/rename", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: ent.path, new_name: newName }),
        });
        dlg.close();
        toast("已重命名");
        reload();
      } catch (err) {
        toast(err.message, "error");
      }
    };
    form.onsubmit = onSubmit;
    $("renameCancel").onclick = () => dlg.close();
  }

  $("mkdirBtn").addEventListener("click", () => {
    const dlg = $("mkdirDialog");
    const input = $("mkdirInput");
    input.value = "";
    dlg.showModal();
    input.focus();
    $("mkdirForm").onsubmit = async (e) => {
      e.preventDefault();
      const name = input.value.trim();
      if (!name) return;
      try {
        await api("/api/mkdir", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ parent: state.path, name }),
        });
        dlg.close();
        toast("文件夹已创建");
        loadList(state.path);
      } catch (err) {
        toast(err.message, "error");
      }
    };
    $("mkdirCancel").onclick = () => dlg.close();
  });

  pasteBtn.addEventListener("click", async () => {
    if (!state.clipboard) return;
    const { mode, path } = state.clipboard;
    const endpoint = mode === "cut" ? "/api/move" : "/api/copy";
    try {
      await api(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: path, dest_dir: state.path }),
      });
      if (mode === "cut") {
        state.clipboard = null;
        updateClipUI();
      }
      toast(mode === "cut" ? "已移动" : "已复制");
      loadList(state.path);
    } catch (err) {
      toast(err.message, "error");
    }
  });

  $("uploadInput").addEventListener("change", async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f);
      try {
        await api("/api/upload?path=" + encodeURIComponent(state.path), {
          method: "POST",
          body: fd,
        });
        toast("已上传: " + f.name);
      } catch (err) {
        toast(f.name + ": " + err.message, "error");
      }
    }
    e.target.value = "";
    loadList(state.path);
  });

  async function openEditor(path, name) {
    try {
      const data = await api("/api/read?path=" + encodeURIComponent(path));
      state.editor = { path: data.path, encoding: data.encoding || "utf-8" };
      $("editorTitle").textContent = "编辑: " + (name || path);
      $("editorMeta").textContent = "编码: " + state.editor.encoding;
      $("editorArea").value = data.content;
      $("editorDialog").showModal();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  $("editorSave").addEventListener("click", async () => {
    try {
      await api("/api/write", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          path: state.editor.path,
          content: $("editorArea").value,
          encoding: state.editor.encoding || "utf-8",
        }),
      });
      toast("已保存");
      reload();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  $("editorClose").addEventListener("click", () => $("editorDialog").close());

  $("refreshBtn").addEventListener("click", reload);
  $("searchBtn").addEventListener("click", doSearch);
  $("searchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });
  $("clearSearchBtn").addEventListener("click", () => {
    state.searchMode = false;
    $("searchInput").value = "";
    $("clearSearchBtn").hidden = true;
    loadList(state.path);
  });

  // Init
  api("/api/info").then((info) => {
    rootLabel.textContent = "根目录: " + info.root;
  }).catch(() => {});
  loadList("");
  updateClipUI();
})();

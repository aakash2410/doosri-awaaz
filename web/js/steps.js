// The four stages a pack goes through, shown at the top of each stage's page so the teacher
// always sees where they are and what comes next. The page names its stage in <body data-step>.
// Wrapped in a block: pages declare their own top-level `id`.
{
  const STEPS = [
    ["prepare", "Prepare", () => "/prepare.html"],
    ["review", "Review and approve", id => `/review.html?id=${id}`],
    ["classroom", "Run in class", id => `/classroom.html?id=${id}`],
    ["note", "Tomorrow's note", id => `/note.html?id=${id}`],
  ];
  const id = encodeURIComponent(new URLSearchParams(location.search).get("id") || "");
  const at = STEPS.findIndex(([key]) => key === document.body.dataset.step);
  document.getElementById("steps").innerHTML = STEPS.map(([key, label, href], i) => {
    const state = i < at ? "done" : i === at ? "now" : "next";
    const inner = `<span class="n">${i < at ? "✓" : i + 1}</span>${label}`;
    const pill = i < at && (i === 0 || id) ? `<a class="pill" href="${href(id)}">${inner}</a>` : `<span class="pill">${inner}</span>`;
    return `<li class="s${i + 1} ${state}">${pill}</li>`;
  }).join("");
}

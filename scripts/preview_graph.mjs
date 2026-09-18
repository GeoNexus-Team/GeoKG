#!/usr/bin/env node
/*
 * 把图谱视图的布局渲染成静态 SVG（用于 README 配图与视觉核对）。
 *
 * 关键点：**复用页面里的 layoutRadial()**，而不是在 Python/Node 里再写一遍。
 * 布局算法抄一份出来就会漂移，预览图与实际页面就会对不上。这里直接从
 * src/geokg/ui/index.html 里抽出那个函数求值，所以画出来的就是页面会画的。
 *
 * 用法：
 *   node scripts/preview_graph.mjs                        # 用真实 API（需先起服务）
 *   node scripts/preview_graph.mjs out.svg country.BRA 2
 */
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const HTML = path.join(ROOT, "src/geokg/ui/index.html");
const API = process.env.GEOKG_API || "http://127.0.0.1:8788/api/v1/geokg";

const out = process.argv[2] || path.join(ROOT, "docs/ui-preview.svg");
const focus = process.argv[3] || "country.BRA";
const depth = process.argv[4] || "2";

/* ---- 从页面里抽出布局函数（保证与页面同源） ---------------------------- */
const html = fs.readFileSync(HTML, "utf8");
const grab = (re, what) => {
  const m = html.match(re);
  if (!m) throw new Error(`没能从页面里抽出 ${what}——页面结构变了？`);
  return m[0];
};
const spacingSrc = grab(/const RING_SPACING = \d+;/, "RING_SPACING");
const layoutSrc = grab(/function layoutRadial\(nodes\) \{[\s\S]*?\n\}/, "layoutRadial");
const layoutRadial = new Function(`${spacingSrc}\n${layoutSrc}\nreturn layoutRadial;`)();

/* ---- 取真实数据 -------------------------------------------------------- */
const res = await fetch(`${API}/graph?focus=${encodeURIComponent(focus)}` +
                        `&depth=${depth}&direction=both&limit=400`);
if (!res.ok) throw new Error(`GET /graph 失败: ${res.status} ${await res.text()}`);
const g = await res.json();

/* ---- 用页面的算法算坐标 ------------------------------------------------ */
const {pos, maxR, cx, cy, maxDepth} = layoutRadial(g.nodes);
const pad = 130;
const box = {x: cx - maxR - pad, y: cy - maxR - pad,
             w: 2 * (maxR + pad), h: 2 * (maxR + pad)};

const TYPES = [...new Set(g.nodes.map((n) => n.type))].sort();
const PALETTE = ["#4a9eff", "#3fb950", "#e3b341", "#f778ba", "#a371f7", "#ff9e64",
                 "#39c5cf", "#d29922", "#db6d28", "#7ee787", "#79c0ff", "#ffa657",
                 "#bc8cff", "#56d364", "#e3b341", "#8b949e"];
const colorOf = (t) => PALETTE[TYPES.indexOf(t) % PALETTE.length];
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const degree = new Map();
g.edges.forEach((e) => {
  degree.set(e.source, (degree.get(e.source) || 0) + 1);
  degree.set(e.target, (degree.get(e.target) || 0) + 1);
});

const parts = [];
parts.push(`<rect x="${box.x}" y="${box.y}" width="${box.w}" height="${box.h}" fill="#0f1419"/>`);
for (let d = 1; d <= maxDepth; d++) {
  const members = g.nodes.filter((n) => n.depth === d);
  if (members.length) {
    const r = Math.max(90 * d, (members.length * 34) / (2 * Math.PI));
    parts.push(`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#243040" ` +
               `stroke-dasharray="6 12" stroke-width="2"/>`);
  }
}
const showEdgeLabel = g.edges.length <= 45;
g.edges.forEach((e) => {
  const a = pos.get(e.source), b = pos.get(e.target);
  if (!a || !b) return;
  parts.push(`<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" ` +
             `stroke="#3a4a5e" stroke-width="1.4"/>`);
  if (showEdgeLabel) {
    parts.push(`<text x="${(a.x + b.x) / 2}" y="${(a.y + b.y) / 2}" fill="#8b98a5" ` +
               `font-size="11" text-anchor="middle">${esc(e.relation)}</text>`);
  }
});
const showLabels = g.nodes.length <= 60;
g.nodes.slice()
  .sort((a, b) => (a.id === g.focus) - (b.id === g.focus))
  .forEach((n) => {
    const p = pos.get(n.id);
    if (!p) return;
    const deg = degree.get(n.id) || 0;
    const r = n.id === g.focus ? 16 : Math.max(6, Math.min(13, 5 + deg * 0.5));
    const label = showLabels || n.id === g.focus;
    if (n.id === g.focus) {
      parts.push(`<circle cx="${p.x}" cy="${p.y}" r="${r + 7}" fill="none" ` +
                 `stroke="#4a9eff" stroke-width="2" opacity="0.55"/>`);
    }
    parts.push(`<circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${colorOf(n.type)}" ` +
               `stroke="#0f1419" stroke-width="2"/>`);
    if (label) {
      parts.push(`<text x="${p.x}" y="${p.y - r - 6}" fill="#e6edf3" font-size="13" ` +
                 `text-anchor="middle" paint-order="stroke" stroke="#0f1419" ` +
                 `stroke-width="3.5">${esc(n.name)}</text>`);
    }
  });

/* 图例（右下） */
const legend = TYPES.map((t, i) =>
  `<g transform="translate(0,${i * 26})">` +
  `<rect width="14" height="14" rx="3" fill="${colorOf(t)}"/>` +
  `<text x="22" y="12" fill="#8b98a5" font-size="14">${esc(t)} ` +
  `(${g.nodes.filter((n) => n.type === t).length})</text></g>`).join("");
const lx = box.x + box.w - 250, ly = box.y + box.h - TYPES.length * 26 - 30;
parts.push(`<g transform="translate(${lx},${ly})">${legend}</g>`);

const svg =
`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box.x} ${box.y} ${box.w} ${box.h}" ` +
`width="1200" height="1200" font-family="-apple-system,PingFang SC,Helvetica,Arial,sans-serif">
<title>GeoKG 子图预览：${esc(g.focus)} 深度 ${depth}</title>
${parts.join("\n")}
</svg>
`;

fs.mkdirSync(path.dirname(out), {recursive: true});
fs.writeFileSync(out, svg, "utf8");
console.log(`${out}: ${g.nodes.length} 节点 / ${g.edges.length} 边 · ` +
            `视野 ${Math.round(box.w)}×${Math.round(box.h)} · 最大半径 ${Math.round(maxR)}`);

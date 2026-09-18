// Minimal ELK layout bridge: read an ELK JSON graph on stdin, run
// org.eclipse.elk.layered with orthogonal edge routing, write the
// laid-out graph (with x/y assigned) to stdout as JSON.
//
// Usage: node elk_bridge.cjs < graph.json > result.json
//
// This is a throwaway spike script (research/layout/elk-bridge/), not
// production code. No error-recovery beyond surfacing the raw error.

const ELK = require("elkjs");

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const raw = await readStdin();
  const graph = JSON.parse(raw);

  const elk = new ELK();
  const laidOut = await elk.layout(graph);

  process.stdout.write(JSON.stringify(laidOut, null, 2));
}

main().catch((err) => {
  process.stderr.write(String(err && err.stack ? err.stack : err) + "\n");
  process.exit(1);
});

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

function checkDir(dir) {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      checkDir(fullPath);
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      execSync(`node --check "${fullPath}"`, { stdio: "inherit" });
    }
  }
}

checkDir("src");
checkDir("data");
console.log("Sintaxe JavaScript de src/ e data/ validada com sucesso.");

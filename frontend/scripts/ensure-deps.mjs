// Runs before `npm run dev` / `npm run build`: installs packages if package-lock.json changed since the last install
// (e.g. after pulling a new version that adds a dependency), so the app never starts with a missing module.
import { execSync } from "node:child_process";
import { existsSync, statSync } from "node:fs";

const installed = "node_modules/.package-lock.json";
const stale = !existsSync(installed) || statSync("package-lock.json").mtimeMs > statSync(installed).mtimeMs;
if (stale) {
  console.log("Package list changed: running npm install…");
  execSync("npm install", { stdio: "inherit" });
}

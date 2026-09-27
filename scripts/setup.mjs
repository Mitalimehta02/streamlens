// One-time setup: create the API virtualenv, install both dependency trees.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

import { repoRoot, systemPython, systemPythonArgs, venvPython } from "./venv.mjs";

function run(command, args, label, { shell = false } = {}) {
  console.log(`\n> ${label}`);
  const result = spawnSync(command, args, {
    stdio: "inherit",
    shell,
    cwd: repoRoot,
  });
  if (result.status !== 0) {
    console.error(`\nFailed: ${label}`);
    process.exit(result.status ?? 1);
  }
}

if (!existsSync(venvPython())) {
  run(
    systemPython(),
    [...systemPythonArgs(), "-m", "venv", "api/.venv"],
    "creating the API virtualenv (Python 3.11)"
  );
} else {
  console.log("\n> virtualenv already exists, reusing it");
}

run(venvPython(), ["-m", "pip", "install", "--upgrade", "pip"], "upgrading pip");
// requirements-dev.txt includes requirements.txt, so this installs both the
// runtime tree and the test framework. A host installs requirements.txt alone.
run(
  venvPython(),
  ["-m", "pip", "install", "-r", "api/requirements-dev.txt"],
  "installing API dependencies (runtime + tests)"
);
// A single string through a shell, on purpose. npm is npm.cmd on Windows, and
// since Node 18.20 and 20.12 spawning a .cmd without a shell fails with ENOENT
// (the fix for CVE-2024-27980) - which left every Windows clone with no web
// dependencies, no tsc and a failing build. Passing the command as one string
// rather than shell:true plus an args array also avoids Node's DEP0190 warning
// about unescaped arguments; there is no user input in this line to escape.
run("npm --prefix web install", [], "installing web dependencies", {
  shell: true,
});

console.log("\nSetup complete. Start both apps with:  npm run dev\n");

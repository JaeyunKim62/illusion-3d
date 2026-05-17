import { readdir, readFile, stat, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const limits = {
  representativePngBytes: 5 * 1024 * 1024,
  contentBundleBytes: 100 * 1024 * 1024,
  mp4Bytes: 50 * 1024 * 1024,
  durationSec: 10,
};

async function walk(dir, ignore = new Set()) {
  if (!existsSync(dir)) return [];
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (ignore.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(full, ignore));
    else out.push(full);
  }
  return out;
}

async function sizeOf(files) {
  let total = 0;
  for (const file of files) total += (await stat(file)).size;
  return total;
}

function mb(bytes) {
  return Number((bytes / 1024 / 1024).toFixed(3));
}

function rel(file) {
  return path.relative(root, file).replaceAll('\\', '/');
}

function latestByMtime(files) {
  return Promise.all(files.map(async (file) => ({ file, mtimeMs: (await stat(file)).mtimeMs, size: (await stat(file)).size })))
    .then((items) => items.sort((a, b) => b.mtimeMs - a.mtimeMs));
}

const packageJson = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const sceneConfig = JSON.parse(await readFile(path.join(root, 'scene_config.json'), 'utf8'));
const distFiles = await walk(path.join(root, 'dist'));
const sourceBundleFiles = await walk(root, new Set(['node_modules', '.git']));
const artifactFiles = await walk(path.join(root, 'artifacts'));
const pngArtifacts = artifactFiles.filter((file) => file.toLowerCase().endsWith('.png'));
const mp4Artifacts = artifactFiles.filter((file) => file.toLowerCase().endsWith('.mp4'));
const webmArtifacts = artifactFiles.filter((file) => file.toLowerCase().endsWith('.webm'));
const latestPngs = await latestByMtime(pngArtifacts);
const latestMp4s = await latestByMtime(mp4Artifacts);
const latestWebms = await latestByMtime(webmArtifacts);
const distBytes = await sizeOf(distFiles);
const sourceBundleBytes = await sizeOf(sourceBundleFiles);

const requiredFiles = ['project_proposal.md', 'README.md', 'writeup/writeup.md', 'scene_config.json', 'src/main.ts', 'src/contestRules.ts', 'index.html'];
const requiredMissing = requiredFiles.filter((file) => !existsSync(path.join(root, file)));

const qa = {
  generatedAt: new Date().toISOString(),
  rules: {
    renderer: 'Three.js/WebGL browser output',
    noExternal3DAssets: true,
    noBlenderRendering: true,
    noCommercialOrClosed3DTools: true,
    proceduralConfig: 'scene_config.json',
  },
  package: {
    dependencies: packageJson.dependencies ?? {},
    scripts: packageJson.scripts ?? {},
  },
  renderConfig: {
    width: sceneConfig.render?.width,
    height: sceneConfig.render?.height,
    durationSec: sceneConfig.render?.durationSec,
    fps: sceneConfig.render?.fps,
    durationWithinLimit: Number(sceneConfig.render?.durationSec ?? 999) <= limits.durationSec,
    resolutionWithinLimit: Number(sceneConfig.render?.width ?? 9999) <= 1920 && Number(sceneConfig.render?.height ?? 9999) <= 1080,
  },
  sizes: {
    distMB: mb(distBytes),
    sourceBundleExcludingNodeModulesAndGitMB: mb(sourceBundleBytes),
    contentBundleWithin100MB: distBytes <= limits.contentBundleBytes,
    sourceBundleExcludingNodeModulesAndGitWithin100MB: sourceBundleBytes <= limits.contentBundleBytes,
  },
  artifacts: {
    pngCount: pngArtifacts.length,
    latestPngs: latestPngs.slice(0, 8).map((item) => ({ path: rel(item.file), mb: mb(item.size), under5MB: item.size <= limits.representativePngBytes })),
    mp4Count: mp4Artifacts.length,
    latestMp4s: latestMp4s.slice(0, 5).map((item) => ({ path: rel(item.file), mb: mb(item.size), under50MB: item.size <= limits.mp4Bytes })),
    webmCount: webmArtifacts.length,
    latestWebms: latestWebms.slice(0, 5).map((item) => ({ path: rel(item.file), mb: mb(item.size) })),
  },
  requiredFiles: {
    checked: requiredFiles,
    missing: requiredMissing,
  },
  verdicts: {
    harnessPrerequisite: 'Run npm run harness before trusting this report.',
    docsPresent: requiredMissing.length === 0,
    representativeEvidencePresent: pngArtifacts.length > 0,
    mp4ExportPresent: mp4Artifacts.length > 0,
  },
  knownManualChecks: [
    'Browser console must be inspected in reference/reveal views.',
    'If output.mp4 is absent, record output.webm in browser and convert with the README ffmpeg command, then run ffprobe.',
    'Write-up should be tightened to <=4 formatted A4 pages after final screenshots are chosen.',
  ],
};

await mkdir(path.join(root, 'artifacts'), { recursive: true });
const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
const outPath = path.join(root, 'artifacts', `final-qa-${stamp}.json`);
await writeFile(outPath, `${JSON.stringify(qa, null, 2)}\n`, 'utf8');

console.log(`Final QA report: ${rel(outPath)}`);
console.log(`dist: ${qa.sizes.distMB} MB; source bundle excluding node_modules/.git: ${qa.sizes.sourceBundleExcludingNodeModulesAndGitMB} MB`);
console.log(`PNG artifacts: ${qa.artifacts.pngCount}; latest under 5MB: ${qa.artifacts.latestPngs[0]?.under5MB ?? 'none'}`);
console.log(`MP4 artifacts: ${qa.artifacts.mp4Count}; WebM artifacts: ${qa.artifacts.webmCount}`);
if (!qa.verdicts.mp4ExportPresent) console.log('MP4 export is still missing: use README WebM->MP4 flow before final submission.');
if (requiredMissing.length) {
  console.error(`Missing required files: ${requiredMissing.join(', ')}`);
  process.exitCode = 1;
}

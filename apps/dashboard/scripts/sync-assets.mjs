// Copies the files the dashboard serves as static assets from the rest of the repository.
// Generated files land in public/ and are not committed. No sample photos are copied: the
// Read page reads the viewer's own photos (ADR 0011).
// - public/runtime/models: the ONNX detector and CRNN with the CRNN's metadata, for the
//   in-browser mode, and versions.json (content hashes, as the Python side computes them);
// - public/runtime/parity: results/parity_fixtures.json and its PNGs, for the parity check.
// The runtime/ prefix keeps these folders from shadowing the console's /models and /parity
// pages.
import { createHash } from 'node:crypto'
import {
    copyFileSync,
    existsSync,
    mkdirSync,
    readdirSync,
    readFileSync,
    writeFileSync,
} from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const app = join(here, '..')
const repo = join(app, '..', '..')
const pub = join(app, 'public')

function copyMatching(sourceDir, pattern, targetDir) {
    if (!existsSync(sourceDir)) return 0
    mkdirSync(targetDir, { recursive: true })
    let copied = 0
    for (const name of readdirSync(sourceDir)) {
        if (pattern.test(name)) {
            copyFileSync(join(sourceDir, name), join(targetDir, name))
            copied += 1
        }
    }
    return copied
}

function fileVersion(path) {
    return createHash('sha256').update(readFileSync(path)).digest('hex').slice(0, 12)
}

const fixtures = join(repo, 'tests', 'fixtures', 'parity')

const modelDir = join(repo, 'models')
const models = copyMatching(
    modelDir,
    /^(crnn\.onnx|crnn\.json|detector\.onnx)$/,
    join(pub, 'runtime', 'models'),
)
if (existsSync(join(modelDir, 'detector.onnx')) && existsSync(join(modelDir, 'crnn.onnx'))) {
    writeFileSync(
        join(pub, 'runtime', 'models', 'versions.json'),
        JSON.stringify({
            crnn: fileVersion(join(modelDir, 'crnn.onnx')),
            detector: fileVersion(join(modelDir, 'detector.onnx')),
        }) + '\n',
    )
}

const parity = copyMatching(fixtures, /\.png$/, join(pub, 'runtime', 'parity'))
const results = join(repo, 'results', 'parity_fixtures.json')
if (existsSync(results))
    copyFileSync(results, join(pub, 'runtime', 'parity', 'parity_fixtures.json'))

console.log(`sync-assets: ${models} model files, ${parity} parity images`)

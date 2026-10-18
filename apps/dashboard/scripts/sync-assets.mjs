// Copies the assets the dashboard serves as static files from the rest of the repository:
// the synthetic sample scenes (tests/fixtures/parity/scene_*.png), so the Read page can be
// tried without photos. Generated files land in public/ and are not committed.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const app = join(here, '..')
const repo = join(app, '..', '..')

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

const samples = copyMatching(
    join(repo, 'tests', 'fixtures', 'parity'),
    /^scene_\d+\.png$/,
    join(app, 'public', 'samples'),
)
console.log(`sync-assets: ${samples} synthetic sample scenes`)

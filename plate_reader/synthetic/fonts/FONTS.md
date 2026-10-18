# Bundled fonts

Only fonts under the SIL Open Font License 1.1 are bundled (AGENT_RULES §1, ADR 0002).
Each family's licence text sits next to its files as `OFL.txt`. The fonts render synthetic
plates, and the console (`apps/dashboard`) shows plate text in Barlow Condensed Bold and Noto
Kufi Arabic; they are not redistributed as a font product.

| Folder | Family | Files | Licence | Source |
|---|---|---|---|---|
| `barlow-condensed/` | Barlow Condensed (The Barlow Project Authors) | `BarlowCondensed-SemiBold.ttf`, `BarlowCondensed-Bold.ttf` | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/barlowcondensed |
| `noto-kufi-arabic/` | Noto Kufi Arabic (The Noto Project Authors), variable weight axis | `NotoKufiArabic-VF.ttf` (upstream `NotoKufiArabic[wght].ttf`) | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/notokufiarabic |
| `noto-naskh-arabic/` | Noto Naskh Arabic (The Noto Project Authors), variable weight axis | `NotoNaskhArabic-VF.ttf` (upstream `NotoNaskhArabic[wght].ttf`) | SIL OFL 1.1 | https://github.com/google/fonts/tree/main/ofl/notonaskharabic |

Why these: Barlow takes its proportions from Californian plates and highway signage,
which is close to the condensed grotesque used on Moroccan plates; Kufi and Naskh give two
different shapes for the Arabic letter, so the recogniser does not learn one typeface.

The variable fonts were renamed (brackets removed) without modification; the OFL permits
bundling and renaming of the files as long as the reserved font names are not used for a
modified version, and these files are unmodified.

# Scouting: national park channels (Czech and nearby)

_2026-10-29._ First run of the topic scouting routine, for nature beyond animals.
Each channel was confirmed by a link on the park's own website before it was added
(decision 0004: handles can hit look-alikes).

## Added as candidates

| Slug | Official site | What the site links |
| --- | --- | --- |
| `krnap` | [krnap.cz](https://www.krnap.cz) | `youtube.com/user/spravakrnap` (legacy URL; handle `@spravakrnap`) |
| `np-sumava` | [npsumava.cz](https://www.npsumava.cz) | `youtube.com/channel/UCGxRWwduHVNlOiG9SQif-Jw` |
| `np-ceske-svycarsko` | [npcs.cz](https://www.npcs.cz) | `youtube.com/@NPceskesvycarsko` |
| `aopk-cr` | [aopk.gov.cz](https://aopk.gov.cz) | `youtube.com/channel/UCrbD7JldOnTH4yDg0-ksDJg` |

Next: `channels evidence` and `channels vet` (need `YTKEY` and
`ANTHROPIC_API_KEY`), then review in `happytube serve`. For `krnap` and
`np-ceske-svycarsko`, check the "resolved to" title after evidence.

## Confirmed but not added: German-language parks

The registry's `languages` allows only `cs` and `en`, so these wait for `de`:

| Park | Official site | Channel |
| --- | --- | --- |
| Nationalpark Bayerischer Wald | [nationalpark-bayerischer-wald.bayern.de](https://www.nationalpark-bayerischer-wald.bayern.de/) | `@NationalparkBayerischerWald` |
| Nationalpark Berchtesgaden | [nationalpark-berchtesgaden.bayern.de](https://www.nationalpark-berchtesgaden.bayern.de/) | `UCBRYBLtsB_7KD4-YJ86d9jA` |
| Nationalpark Thayatal (Podyjí's Austrian twin) | [np-thayatal.at](https://www.np-thayatal.at/) | `UChF1wSG2qLWID0uvUbyaJyA` |
| Hohe Tauern | [nationalpark-hohetauern.at](https://nationalpark-hohetauern.at/) | `youtube.com/user/nationalparkregion`, a Carinthia tourism channel ("Hohe Tauern – die Nationalpark-Region in Kärnten"), not the park administration |

Nature films often need no words, so a German channel may suit as well as a Czech
one.

## Not found

- **NP Podyjí** ([nppodyji.cz](https://www.nppodyji.cz)): no YouTube link on the
  home page; the rest of the site blocks automated reading. Ask the park, or check
  the site footer by hand.
- **TANAP** ([tanap.sk](https://www.tanap.sk)): links Facebook and Instagram only.

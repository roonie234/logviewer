# Suno tag reference

Tags go in the **Lyrics** box. All entries are **lore** until our own songs confirm them
(see `techniques.yaml` for status). Suno treats tags as hints, not commands.

## Sections (square brackets, own line)
| Tag | Use |
|---|---|
| `[Intro]`, `[Intro: solo piano, 4 bars]` | Opening; describing it keeps it short and specific |
| `[Verse]`, `[Verse 1]`, `[Verse 2]` | Story sections |
| `[Pre-Chorus]` | Build into the chorus |
| `[Chorus]`, `[Final Chorus]` | Hook; `Final` + a cue lets the last one differ |
| `[Post-Chorus]`, `[Hook]` | Short repeated tag after chorus |
| `[Bridge]` | Contrast section, usually once |
| `[Instrumental Break]`, `[Guitar Solo]`, `[Sax Solo: ...]` | Instrumental moments |
| `[Break]`, `[Drop]`, `[Build]` | Arrangement events (electronic styles) |
| `[Outro]`, `[Outro: ...]` | Ending section; describe how it ends |
| `[Fade Out]`, `[End]` | Ending markers; `[End]` after the outro helps stop rambling |

## Delivery cues (square brackets, inline or own line)
`[spoken word]`, `[whispered]`, `[belted]`, `[falsetto]`, `[harmonies]`, `[choir]`,
`[ad-lib]`, `[laughing]`, `[breath]`, `[half-time]`, `[a cappella]`, `[band drops out]`

## Backing vocals
Words in `( )` are usually sung as backing or echo vocals: `I waited (I waited)`.

## Formatting that shapes phrasing
- Line breaks = phrase breaks. Short lines get space around them.
- Commas and dashes suggest small pauses; `...` a longer hold.
- An empty line between sections helps Suno see the boundary.
- ALL CAPS words are often sung with more force (lore).

## Limits (check in the Suno UI, they change by model)
- Style: around 1000 characters on recent models (older: 200)
- Lyrics: around 5000 characters on recent models (older: 3000)
- Title: about 80 characters

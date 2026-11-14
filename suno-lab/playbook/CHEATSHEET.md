# Suno Prompt Cheat Sheet

Generated from `playbook/techniques.yaml`. Status changes as our rated songs pile up.

## Untested lore (try these)

**sound-not-adjectives** (style)  
Describe sounds, instruments and playing style instead of quality or mood adjectives.  
Do: `brushed snare, upright bass walking, felt piano with pedal noise`  
Not: `epic emotional beautiful song`

**recording-space** (style)  
Name the recording conditions - room, era, gear, imperfections - so the mix sounds captured, not generated.  
Do: `recorded live in a small wooden room, 1970s tape, room mics, slight hiss`  
Not: `high quality professional production`

**loose-human-feel** (style)  
Ask for human timing explicitly.  
Do: `live drummer, loose swung 16ths, laid-back behind the beat`  
Not: `tight drums`

**focused-style** (style)  
Keep the style to one genre anchor plus at most one unexpected twist, 5-9 strong descriptors. Overloaded style lists blur into generic mush.  
Do: `Delta blues, slide guitar, stomp box, cracked baritone voice, with a dub-reggae bass undertow`  
Not: `art-pop, indie-soul, deep-house, 8-bit, trap, drum-and-bass, riddim, electro-pop, lo-fi`

**tempo-key-in-style** (style)  
State BPM and key/mode in the style field to pin tempo and mood.  
Do: `78 BPM, D minor`  
Not: `slow, sad`

**describe-dont-name-artists** (style)  
Describe an artist's sound instead of naming them (names get filtered and you lose control anyway).  
Do: `whispered close-mic female vocal, sparse nylon guitar, bossa nova restraint`  
Not: `sounds like <famous artist>`

**energy-arc-in-style** (style)  
Put the dynamic arc into the style - where it is sparse and where it opens up.  
Do: `sparse verses, chorus opens up with full band, stripped-down bridge, quiet last chorus`  
Not: `energetic throughout`

**exclude-the-defaults** (exclude)  
Use the Exclude field for Suno's default sounds you do not want.  
Do: `Exclude: auto-tune, EDM drop, generic pop, synth pads, reverb wash`  
Not: `(empty exclude)`

**explicit-sections** (structure)  
Tag every section explicitly in the lyrics in the order you want.  
Do: `[Intro] [Verse 1] [Pre-Chorus] [Chorus] [Verse 2] [Chorus] [Bridge] [Final Chorus] [Outro] [End]`  
Not: `lyrics with no tags`

**short-described-intro** (structure)  
Keep intros short and say what plays in them, so Suno does not ramble for 30 seconds.  
Do: `[Intro: solo piano, 4 bars]`  
Not: `[Intro]`

**designed-ending** (structure)  
End with an outro that says how it ends, then [End], to avoid abrupt cut-offs.  
Do: `[Outro: band drops out, voice and guitar only, ring out] ... [End]`  
Not: `lyrics just stop after the last chorus`

**vary-the-repeat** (structure)  
Never repeat a chorus word for word. Change a line, the arrangement cue, or the delivery on each return.  
Do: `[Final Chorus: half-time, just voice and claps] with one rewritten line`  
Not: `same chorus pasted three times`

**instrumental-moment** (structure)  
Give the band a named instrumental moment.  
Do: `[Instrumental Break: harmonica solo, slightly out of breath]`  
Not: `vocals wall to wall`

**concrete-specifics** (lyrics)  
Use concrete, specific details - names, places, objects, times - instead of abstract feelings.  
Do: `your mum's blue Corolla, the dent from the parking post`  
Not: `memories of you burning in my heart`

**uneven-lines** (lyrics)  
Vary line lengths and break the rhyme pattern sometimes; uniform lines with perfect end rhymes sound templated.  
Do: `a 4-syllable line after a 12-syllable one; slant rhymes (home / alone / phone booth)`  
Not: `every line 8 syllables, AABB perfect rhymes`

**conversational-voice** (lyrics)  
Write lines the way a person would actually say them - contractions, asides, unfinished thoughts.  
Do: `I didn't call. Well - I did, I hung up.`  
Not: `I shall never forget the love we shared`

**one-strange-image** (lyrics)  
Put one surprising, slightly odd image in each verse.  
Do: `the fridge hums in the key of your leaving`  
Not: `tears fall like rain`

**voice-character** (vocals)  
Describe the singer as a person - age, texture, mic distance, attitude.  
Do: `raspy 50-year-old male baritone, close-mic, tired but warm`  
Not: `male vocals`

**performance-cues** (vocals)  
Add delivery cues inside sections (whispered, spoken, laughing, breath) and backing vocals in parentheses.  
Do: `[spoken, almost laughing] ... (ooh, don't)`  
Not: `no delivery direction`

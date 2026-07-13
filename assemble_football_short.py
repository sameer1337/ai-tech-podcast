# -*- coding: utf-8 -*-
"""
Assemble a finished football Short from your Veo clips + a script.

You bring: a folder of 6 (or any number) vertical Veo .mp4 clips + the script.
This does: edge-TTS voiceover (word-timed), stitches the clips to fill the
voiceover length, burns SAFE-ZONE captions + a follow CTA, exports a 1080x1920
mp4 ready to upload.

Usage:
  python assemble_football_short.py --clips-dir "D:/claude/fifa/1" ^
      --script @script.txt  --hook "SPAIN 2-1 BELGIUM" --out final.mp4
  # or pass the script inline:
  python assemble_football_short.py --clips-dir "D:/claude/fifa/1" ^
      --script "Spain took the lead..." --hook "SPAIN 2-1 BELGIUM"

Reuses synthesize() (TTS + word timings) from generate_short.py so captions
match the rest of the channel.
"""
import os, sys, glob, subprocess
import imageio_ffmpeg
from generate_short import synthesize

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE_DEFAULT = "en-GB-RyanNeural"          # matches the World Cup short voice

# Natural visual arc — clips are ordered by the first keyword they match.
# Specific keywords only (no generic "stadium"/"lights" that appear in many
# names and would mis-sort, e.g. a trophy clip named "..._stadium_lights").
ARC = ["exterior", "dusk", "aerial", "tunnel", "walk", "attack", "battl",
       "ball", "net", "goal", "crowd", "fans", "cheer", "celebrat",
       "trophy", "cup", "hand", "final"]


def arg(name, default=None):
    return next((sys.argv[sys.argv.index(name) + 1] for a in sys.argv if a == name), default)


def order_clips(clips_dir, exclude=()):
    exclude = {e.lower() for e in exclude}
    files = [f for f in glob.glob(os.path.join(clips_dir, "*.mp4"))
             if os.path.basename(f).lower() not in exclude
             and not os.path.basename(f).lower().startswith(("final", "voice"))]

    def rank(path):
        n = os.path.basename(path).lower()
        for i, kw in enumerate(ARC):
            if kw in n:
                return (i, n)
        return (len(ARC), n)          # unknown clips last, alphabetical
    return sorted(files, key=rank)


def _ass_time(t):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_captions(words, duration, ass_path, hook="", cta="Follow for daily World Cup recaps"):
    """Word-chunk captions centered in the middle safe zone (top 20% / bottom
    25% are covered by YouTube UI). Pinned hook first 2.5s, CTA last 3s."""
    chunks, cur = [], []
    for (start, end, text) in words:
        if cur and (len(cur) >= 3 or start - cur[-1][1] > 0.6):
            chunks.append(cur); cur = []
        cur.append((start, end, text))
    if cur:
        chunks.append(cur)

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H88000000,-1,0,0,0,100,100,1,0,1,7,2,5,60,60,0,1
Style: CTA,Arial,54,&H0000E5FF,&H00FFFFFF,&H00000000,&H88000000,-1,0,0,0,100,100,1,0,1,4,1,5,60,60,0,1
Style: Hook,Arial,80,&H0000E5FF,&H00FFFFFF,&H00000000,&HAA000000,-1,0,0,0,100,100,1,0,1,6,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for i, chunk in enumerate(chunks):
        start = chunk[0][0]
        end = chunks[i + 1][0][0] if i + 1 < len(chunks) else min(chunk[-1][1] + 0.4, duration)
        text = " ".join(w[2] for w in chunk).upper().replace("\\", "").replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Cap,,0,0,0,,"
                     f"{{\\an5\\pos(540,960)\\fad(60,0)}}{text}")
    if hook:
        h = hook.upper().replace("\\", "").replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(min(2.5, duration))},Hook,,0,0,0,,"
                     f"{{\\an5\\pos(540,700)\\fad(0,150)}}{h}")
    cta_start = max(0.0, duration - 3.0)
    lines.append(f"Dialogue: 1,{_ass_time(cta_start)},{_ass_time(duration)},CTA,,0,0,0,,"
                 f"{{\\an5\\pos(540,1330)\\fad(200,0)}}▶ {cta}")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    print(f"[assemble] captions: {len(chunks)} chunks + hook + CTA")


def main():
    clips_dir = arg("--clips-dir")
    if not clips_dir or not os.path.isdir(clips_dir):
        sys.exit("Pass --clips-dir <folder with your .mp4 clips>")
    script = arg("--script", "")
    if script.startswith("@"):
        with open(script[1:], encoding="utf-8") as f:
            script = f.read().strip()
    if not script:
        sys.exit("Pass --script \"...\" or --script @file.txt")
    voice = arg("--voice", VOICE_DEFAULT)
    hook  = arg("--hook", "")
    out   = arg("--out", "final.mp4")

    clips = order_clips(clips_dir, exclude={os.path.basename(out)})
    if not clips:
        sys.exit(f"No .mp4 clips found in {clips_dir}")
    print(f"[assemble] {len(clips)} clips in order:")
    for c in clips:
        print("   -", os.path.basename(c))

    # 1) Voiceover + word timings (written into the clips dir)
    voice_mp3 = os.path.join(clips_dir, "voice.mp3")
    words = synthesize(script, voice, voice_mp3)
    audio_dur = (words[-1][1] if words else 0) + 0.4
    total = audio_dur + 2.0                       # ~2s tail for the CTA/loop
    per = total / len(clips)
    print(f"[assemble] voiceover {audio_dur:.1f}s -> short {total:.1f}s, {per:.1f}s/clip")

    # 2) Captions
    ass_path = os.path.join(clips_dir, "captions.ass")
    build_captions(words, total, ass_path, hook=hook)

    # 3) ffmpeg: trim+scale+crop each clip, concat, burn captions, add audio.
    #    Run with cwd=clips_dir so the subtitles filter takes a bare filename
    #    (avoids Windows path-escaping pain inside the filtergraph).
    inputs = []
    for c in clips:
        inputs += ["-i", os.path.basename(c)]
    inputs += ["-i", "voice.mp3"]

    fc = []
    for i in range(len(clips)):
        fc.append(f"[{i}:v]trim=0:{per:.3f},setpts=PTS-STARTPTS,"
                  f"scale=1080:1920:force_original_aspect_ratio=increase,"
                  f"crop=1080:1920,setsar=1,fps=30[v{i}]")
    concat_in = "".join(f"[v{i}]" for i in range(len(clips)))
    fc.append(f"{concat_in}concat=n={len(clips)}:v=1:a=0[cat]")
    # Veo stamps its logo in the bottom-right corner. delogo interpolates it
    # away from surrounding pixels (the CTA caption sits lower-center, clear of
    # this box, so it is never touched). --no-delogo skips it.
    if "--no-delogo" in sys.argv:
        fc.append("[cat]subtitles=captions.ass[vout]")
    else:
        fc.append("[cat]delogo=x=828:y=1674:w=116:h=116,subtitles=captions.ass[vout]")
    filtergraph = ";".join(fc)

    cmd = [FFMPEG, "-y", *inputs,
           "-filter_complex", filtergraph,
           "-map", "[vout]", "-map", f"{len(clips)}:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
           "-t", f"{total:.3f}", os.path.basename(out)]
    print("[assemble] rendering...")
    r = subprocess.run(cmd, cwd=clips_dir, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2500:])
        sys.exit("[assemble] ffmpeg failed")
    final = os.path.join(clips_dir, os.path.basename(out))
    size = os.path.getsize(final) // 1024
    print(f"\n[OK] Done: {final}  ({size} KB, {total:.1f}s, 1080x1920)")


if __name__ == "__main__":
    main()

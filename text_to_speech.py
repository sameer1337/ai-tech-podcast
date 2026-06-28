"""
Step 3 — Convert script to MP3 using Edge TTS (free Microsoft Neural voices).
Optionally layers intro/outro music via pydub + ffmpeg.
"""

import asyncio
import os
import edge_tts
from pathlib import Path
from config import TTS_VOICE, TTS_RATE, TTS_PITCH, INTRO_MUSIC, OUTRO_MUSIC, MUSIC_FADE


async def _synthesize(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH)
    await communicate.save(output_path)


def text_to_speech(script: str, output_path: str) -> str:
    """Convert script to MP3. Returns the final output path."""
    raw_path = output_path.replace(".mp3", "_raw.mp3")

    print(f"[tts] Synthesizing voice → {raw_path}")
    asyncio.run(_synthesize(script, raw_path))

    # If music assets exist, layer them; otherwise just rename raw to final
    has_intro = INTRO_MUSIC and os.path.exists(INTRO_MUSIC)
    has_outro = OUTRO_MUSIC and os.path.exists(OUTRO_MUSIC)

    if has_intro or has_outro:
        _mix_music(raw_path, output_path, has_intro, has_outro)
        os.remove(raw_path)
    else:
        os.rename(raw_path, output_path)
        print("[tts] No music assets found — using voice-only audio")

    print(f"[tts] Final audio → {output_path}")
    return output_path


def _mix_music(voice_path: str, output_path: str, has_intro: bool, has_outro: bool) -> None:
    try:
        from pydub import AudioSegment

        voice = AudioSegment.from_mp3(voice_path)
        result = AudioSegment.empty()

        if has_intro:
            intro = AudioSegment.from_mp3(INTRO_MUSIC)
            intro = intro[:8000]  # first 8 seconds
            intro = intro.fade_in(500).fade_out(MUSIC_FADE * 1000)
            result += intro

        result += voice

        if has_outro:
            outro = AudioSegment.from_mp3(OUTRO_MUSIC)
            outro = outro[:8000]
            outro = outro.fade_in(MUSIC_FADE * 1000).fade_out(500)
            result += outro

        result.export(output_path, format="mp3", bitrate="128k")
        print(f"[tts] Music mixed successfully")

    except ImportError:
        print("[tts] pydub not installed — skipping music mix, using raw voice")
        import shutil
        shutil.copy(voice_path, output_path)


if __name__ == "__main__":
    test_script = "This is a test of the AI Tech Daily podcast text to speech system. The voice sounds great!"
    text_to_speech(test_script, "test_output.mp3")

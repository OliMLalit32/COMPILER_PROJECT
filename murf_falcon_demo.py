import argparse
import os
import wave
from pathlib import Path


SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stream audio from Murf Falcon and optionally play/save it."
    )
    parser.add_argument(
        "--text",
        default="Hello from Murf Falcon.",
        help="Text to convert to speech.",
    )
    parser.add_argument(
        "--voice",
        default="Matthew",
        help="Falcon voice ID, for example Matthew.",
    )
    parser.add_argument(
        "--locale",
        default="en-US",
        help="Locale code, for example en-US.",
    )
    parser.add_argument(
        "--region",
        default="in",
        choices=["global", "in"],
        help="Murf API region. Use 'in' for India or 'global' for auto-routing.",
    )
    parser.add_argument(
        "--output",
        default="falcon_output.wav",
        help="Where to save the streamed audio.",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="Save audio without live playback.",
    )
    return parser.parse_args()


def require_api_key():
    api_key = os.getenv("MURF_API_KEY")
    if api_key:
        return api_key

    raise SystemExit(
        "MURF_API_KEY is not set.\n"
        "PowerShell example:\n"
        '$env:MURF_API_KEY="paste-your-api-key-here"'
    )


def import_murf_sdk():
    try:
        from murf import Murf, MurfRegion
    except ImportError as exc:
        raise SystemExit(
            "Murf SDK is not installed.\n"
            "Install it with:\n"
            "pip install murf"
        ) from exc

    return Murf, MurfRegion


def get_region(region_name, murf_region_cls):
    region_map = {
        "global": murf_region_cls.GLOBAL,
        "in": murf_region_cls.IN,
    }
    return region_map[region_name]


def open_audio_player(disabled):
    if disabled:
        return None, None

    try:
        import pyaudio
    except ImportError:
        print("PyAudio not found. Audio will be saved only.")
        return None, None

    player = pyaudio.PyAudio()
    stream = player.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        output=True,
    )
    return player, stream


def close_audio_player(player, stream):
    if stream is not None:
        stream.stop_stream()
        stream.close()
    if player is not None:
        player.terminate()


def main():
    args = parse_args()
    api_key = require_api_key()
    Murf, MurfRegion = import_murf_sdk()

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = Murf(
        api_key=api_key,
        region=get_region(args.region, MurfRegion),
    )

    player, audio_out = open_audio_player(args.no_play)

    print(f"Starting Falcon stream with voice '{args.voice}'...")
    audio_stream = client.text_to_speech.stream(
        text=args.text,
        voice_id=args.voice,
        model="FALCON",
        locale=args.locale,
        sample_rate=SAMPLE_RATE,
        format="PCM",
    )

    total_bytes = 0
    wav_file = wave.open(str(output_path), "wb")
    wav_file.setnchannels(CHANNELS)
    wav_file.setsampwidth(SAMPLE_WIDTH)
    wav_file.setframerate(SAMPLE_RATE)

    try:
        for chunk in audio_stream:
            if not chunk:
                continue
            total_bytes += len(chunk)
            wav_file.writeframes(chunk)
            if audio_out is not None:
                audio_out.write(chunk)
    except Exception as exc:
        raise SystemExit(f"Streaming failed: {exc}") from exc
    finally:
        wav_file.close()
        close_audio_player(player, audio_out)

    print(f"Saved audio to: {output_path}")
    print(f"Received {total_bytes} bytes from Murf Falcon.")


if __name__ == "__main__":
    main()

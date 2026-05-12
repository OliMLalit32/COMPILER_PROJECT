import io
import os
import wave


SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM


class MurfFalconError(RuntimeError):
    pass


def normalize_text(text):
    normalized = " ".join((text or "").split())
    if normalized:
        return normalized

    raise MurfFalconError("Cannot generate voice for empty text.")


def resolve_api_key(explicit_api_key=None):
    api_key = explicit_api_key or os.getenv("MURF_API_KEY")
    if api_key:
        return api_key

    raise MurfFalconError(
        "Murf API key not found. Paste it in the frontend or set MURF_API_KEY."
    )


def import_murf_sdk():
    try:
        from murf import Murf, MurfRegion
    except ImportError as exc:
        raise MurfFalconError(
            "Murf SDK is not installed. Run: pip install murf"
        ) from exc

    return Murf, MurfRegion


def get_region(region_name, murf_region_cls):
    region_map = {
        "global": murf_region_cls.GLOBAL,
        "in": murf_region_cls.IN,
    }

    if region_name not in region_map:
        raise MurfFalconError(f"Unsupported Murf region: {region_name}")

    return region_map[region_name]


def coerce_audio_chunk(chunk):
    if not chunk:
        return b""

    if isinstance(chunk, (bytes, bytearray)):
        return bytes(chunk)

    if isinstance(chunk, dict):
        payload = chunk.get("audio") or chunk.get("chunk") or chunk.get("data")
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)
        return b""

    for attr in ("audio", "chunk", "data"):
        payload = getattr(chunk, attr, None)
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)

    return b""


def generate_falcon_wav_bytes(
    text,
    *,
    voice_id="Matthew",
    locale="en-US",
    region="in",
    api_key=None,
):
    text = normalize_text(text)
    api_key = resolve_api_key(api_key)
    Murf, MurfRegion = import_murf_sdk()

    client = Murf(
        api_key=api_key,
        region=get_region(region, MurfRegion),
    )

    audio_stream = client.text_to_speech.stream(
        text=text,
        voice_id=voice_id,
        model="FALCON",
        locale=locale,
        sample_rate=SAMPLE_RATE,
        format="PCM",
    )

    pcm_bytes = bytearray()
    for chunk in audio_stream:
        pcm_chunk = coerce_audio_chunk(chunk)
        if pcm_chunk:
            pcm_bytes.extend(pcm_chunk)

    if not pcm_bytes:
        raise MurfFalconError("Murf returned no audio data.")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(bytes(pcm_bytes))

    return buffer.getvalue()

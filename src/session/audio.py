import struct
from pathlib import Path

from src.config import settings

AUDIO_STORAGE = Path(settings.audio_storage_path)
SAMPLE_RATE_OUT = 24000  # Gemini Live output: 24kHz
SAMPLE_RATE_IN = 16000   # Browser input: 16kHz
CHANNELS = 1
BITS_PER_SAMPLE = 16


def pcm_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE_OUT) -> bytes:
    """Добавляет RIFF WAV-заголовок к raw PCM (16-bit LE mono)."""
    byte_rate = sample_rate * CHANNELS * BITS_PER_SAMPLE // 8
    block_align = CHANNELS * BITS_PER_SAMPLE // 8
    data_size = len(pcm_data)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,  # PCM
        CHANNELS,
        sample_rate,
        byte_rate,
        block_align,
        BITS_PER_SAMPLE,
        b"data",
        data_size,
    )
    return header + pcm_data


def calc_duration_ms(pcm_data: bytes, sample_rate: int = SAMPLE_RATE_OUT) -> int:
    bytes_per_sample = CHANNELS * BITS_PER_SAMPLE // 8
    return int(len(pcm_data) / bytes_per_sample / sample_rate * 1000)


def save_turn_audio(session_id: str, sequence: int, role: str, pcm_chunks: list[bytes]) -> tuple[str, int]:
    """Финализирует WAV-файл из PCM-чанков. Возвращает (путь, длительность_мс)."""
    pcm_data = b"".join(pcm_chunks)
    if not pcm_data:
        return "", 0

    wav_data = pcm_to_wav(pcm_data)
    duration_ms = calc_duration_ms(pcm_data)

    path = AUDIO_STORAGE / session_id / f"{sequence:03d}_{role}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(wav_data)

    return str(path), duration_ms

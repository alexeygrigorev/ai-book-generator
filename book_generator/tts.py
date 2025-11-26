import os
import wave
import json
import time
import threading
import io
from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
from tqdm.auto import tqdm
from google.genai import types
import boto3
from book_generator.utils import get_client, calculate_tts_cost


class TTSGenerator:
    def __init__(
        self,
        model: str = "models/gemini-2.5-flash-preview-tts",
        voice_name: str = "Charon",
        num_threads: int = 1,
        s3_bucket: Optional[str] = None,
    ):
        self.model = model
        self.voice_name = voice_name
        self.client = get_client()
        self.total_cost = 0.0
        self.cost_lock = threading.Lock()
        self.num_threads = num_threads
        self.s3_bucket = s3_bucket
        self.s3_client = boto3.client("s3") if s3_bucket else None

    def _save_wave_file(
        self,
        filename: Path,
        pcm_data: bytes,
        channels: int = 1,
        rate: int = 24000,
        sample_width: int = 2,
    ):
        """Saves PCM data to a WAV file."""
        with wave.open(str(filename), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)

    def _create_wave_bytes(
        self,
        pcm_data: bytes,
        channels: int = 1,
        rate: int = 24000,
        sample_width: int = 2,
    ) -> bytes:
        """Creates WAV file bytes from PCM data."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)
        return buffer.getvalue()

    def _upload_to_s3(self, wav_bytes: bytes, s3_key: str):
        """Uploads WAV bytes to S3."""
        try:
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=wav_bytes,
                ContentType="audio/wav",
            )
        except Exception as e:
            raise Exception(f"Failed to upload to S3: {e}")

    def generate_audio_bytes(self, text: str) -> Optional[bytes]:
        """Generates audio from text and returns WAV bytes."""
        if not text.strip():
            return None

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=text,
                config={
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": self.voice_name}
                        }
                    },
                },
            )

            if not response.candidates:
                tqdm.write("No candidates returned")
                return None

            parts = response.candidates[0].content.parts
            if not parts:
                tqdm.write("No parts returned")
                return None

            inline_data = parts[0].inline_data
            if not inline_data or not inline_data.data:
                tqdm.write("No audio data returned")
                return None

            # Create WAV bytes from PCM data
            wav_bytes = self._create_wave_bytes(inline_data.data)

            # Calculate and track cost
            cost = calculate_tts_cost(
                response.usage_metadata, is_batch=False, print_cost=False
            )
            with self.cost_lock:
                self.total_cost += cost
            tqdm.write(f"  Cost: ${cost:.6f}")

            return wav_bytes

        except Exception as e:
            tqdm.write(f"Error generating audio: {e}")
            return None

    def generate_audio(self, text: str, output_path: Path):
        """Generates audio from text and saves it to output_path."""
        wav_bytes = self.generate_audio_bytes(text)
        if wav_bytes:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(wav_bytes)
            tqdm.write(f"  Generated {output_path.name}")

    def _s3_file_exists(self, s3_key: str) -> bool:
        """Check if a file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.s3_bucket, Key=s3_key)
            return True
        except:
            return False

    def _process_single_file(
        self, file_path: Path, base_path: Path, audio_base_path: Path, book_name: str
    ):
        """Worker function for processing a single file."""
        try:
            # Construct paths
            relative_path = file_path.relative_to(base_path)

            if self.s3_bucket:
                # Check if file exists in S3
                s3_key = f"{book_name}/{relative_path.with_suffix('.wav')}"
                s3_key = s3_key.replace("\\", "/")  # Normalize path separators

                if self._s3_file_exists(s3_key):
                    tqdm.write(f"Skipping existing audio: {relative_path}")
                    return

                tqdm.write(f"Processing: {relative_path}")
                text = file_path.read_text(encoding="utf-8")

                # Generate audio and upload to S3
                wav_bytes = self.generate_audio_bytes(text)
                if wav_bytes:
                    self._upload_to_s3(wav_bytes, s3_key)
                    tqdm.write(f"  Uploaded to S3: s3://{self.s3_bucket}/{s3_key}")
            else:
                # Original behavior: save to local filesystem
                output_path = audio_base_path / relative_path.with_suffix(".wav")
                if output_path.exists():
                    tqdm.write(f"Skipping existing audio: {output_path.name}")
                    return

                tqdm.write(f"Processing: {relative_path}")
                text = file_path.read_text(encoding="utf-8")
                self.generate_audio(text, output_path)

        except Exception as e:
            tqdm.write(f"Error processing {file_path}: {e}")

    def _process_book_standard(
        self,
        base_path: Path,
        audio_base_path: Path,
        book_name: str,
        limit: Optional[int] = None,
    ):
        """Processes files using the Standard API with parallel execution."""
        files_to_process = []
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith(".md"):
                    files_to_process.append(Path(root) / file)

        if limit:
            files_to_process = files_to_process[:limit]

        print(f"Found {len(files_to_process)} markdown files to process.")

        # Sequential execution if num_threads is 1
        if self.num_threads == 1:
            for file_path in tqdm(files_to_process, desc="Generating Audio"):
                self._process_single_file(
                    file_path, base_path, audio_base_path, book_name
                )
            return

        # Parallel execution
        pool = ThreadPoolExecutor(max_workers=self.num_threads)
        interrupted = False

        try:
            with tqdm(total=len(files_to_process), desc="Generating Audio") as progress:
                futures = []
                for file_path in files_to_process:
                    future = pool.submit(
                        self._process_single_file,
                        file_path,
                        base_path,
                        audio_base_path,
                        book_name,
                    )
                    future.add_done_callback(lambda p: progress.update())
                    futures.append(future)

                # Wait for all futures with timeout to allow keyboard interrupts
                from concurrent.futures import TimeoutError as FuturesTimeoutError

                for future in futures:
                    while True:
                        try:
                            future.result(timeout=1.0)
                            break
                        except FuturesTimeoutError:
                            continue

        except KeyboardInterrupt:
            print("\nStopping...")
            interrupted = True
            pool.shutdown(wait=False, cancel_futures=True)
            import sys

            sys.exit(0)
        finally:
            if not interrupted:
                pool.shutdown(wait=True)

    def process_book(self, book_folder: str, limit: Optional[int] = None):
        """
        Processes markdown files in the book folder.

        Args:
            book_folder: Name of the folder in 'books/'.
            limit: Optional maximum number of files to process.
        """
        base_path = Path("books") / book_folder
        audio_base_path = Path("audio") / book_folder

        if not base_path.exists():
            print(f"Book folder not found: {base_path}")
            return

        self._process_book_standard(base_path, audio_base_path, book_folder, limit)

        print(f"TTS Generation Completed. Total Estimated Cost: ${self.total_cost:.6f}")

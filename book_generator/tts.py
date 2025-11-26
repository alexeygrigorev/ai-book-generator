import os
import wave
import json
import time
import threading
from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
from tqdm.auto import tqdm
from google.genai import types
from book_generator.utils import get_client, calculate_tts_cost

class TTSGenerator:
    def __init__(self, model: str = "models/gemini-2.5-flash-preview-tts", voice_name: str = "Charon", num_threads: int = 10):
        self.model = model
        self.voice_name = voice_name
        self.client = get_client()
        self.total_cost = 0.0
        self.cost_lock = threading.Lock()
        self.num_threads = num_threads

    def _save_wave_file(self, filename: Path, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2):
        """Saves PCM data to a WAV file."""
        with wave.open(str(filename), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)

    def generate_audio(self, text: str, output_path: Path):
        """Generates audio from text and saves it to output_path."""
        if not text.strip():
            tqdm.write(f"Skipping empty text for {output_path}")
            return

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=text,
                config={
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": self.voice_name
                            }
                        }
                    }
                }
            )
            
            if not response.candidates:
                tqdm.write(f"No candidates returned for {output_path}")
                return

            parts = response.candidates[0].content.parts
            if not parts:
                tqdm.write(f"No parts returned for {output_path}")
                return
                
            inline_data = parts[0].inline_data
            if not inline_data or not inline_data.data:
                tqdm.write(f"No audio data returned for {output_path}")
                return

            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_wave_file(output_path, inline_data.data)

            # Calculate and track cost
            # Standard API usage metadata structure
            cost = calculate_tts_cost(response.usage_metadata, is_batch=False, print_cost=False)
            with self.cost_lock:
                self.total_cost += cost
            tqdm.write(f"  Generated {output_path.name} | Cost: ${cost:.6f}")

        except Exception as e:
            tqdm.write(f"Error generating audio for {output_path}: {e}")



    def _process_single_file(self, file_path: Path, base_path: Path, audio_base_path: Path):
        """Worker function for processing a single file."""
        try:
            # Construct output path
            relative_path = file_path.relative_to(base_path)
            output_path = audio_base_path / relative_path.with_suffix(".wav")

            if output_path.exists():
                tqdm.write(f"Skipping existing audio: {output_path.name}")
                return

            tqdm.write(f"Processing: {relative_path}")
            text = file_path.read_text(encoding="utf-8")
            self.generate_audio(text, output_path)
        except Exception as e:
            tqdm.write(f"Error processing {file_path}: {e}")

    def _process_book_standard(self, base_path: Path, audio_base_path: Path, limit: Optional[int] = None):
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
                self._process_single_file(file_path, base_path, audio_base_path)
            return
        
        # Parallel execution
        pool = ThreadPoolExecutor(max_workers=self.num_threads)
        interrupted = False

        try:
            with tqdm(total=len(files_to_process), desc="Generating Audio") as progress:
                futures = []
                for file_path in files_to_process:
                    future = pool.submit(self._process_single_file, file_path, base_path, audio_base_path)
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

        self._process_book_standard(base_path, audio_base_path, limit)

        print(f"TTS Generation Completed. Total Estimated Cost: ${self.total_cost:.6f}")

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict
from google.genai import types
from book_generator.utils import get_client, calculate_tts_cost
from book_generator.tts import TTSGenerator


class TTSBatchGenerator(TTSGenerator):
    """TTS Generator using the Batch API for cost savings."""
    
    def _create_batch_request(self, text: str, custom_id: str) -> Dict:
        """Creates a single request dictionary for the batch job."""
        return {
            "custom_id": custom_id,
            "request": {
                "model": self.model,
                "contents": [{"parts": [{"text": text}]}],
                "config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": self.voice_name
                            }
                        }
                    }
                }
            }
        }

    def process_book(self, book_folder: str, limit: Optional[int] = None):
        """
        Processes markdown files in the book folder using Batch API.
        
        Args:
            book_folder: Name of the folder in 'books/'.
            limit: Optional maximum number of files to process.
        """
        base_path = Path("books") / book_folder
        audio_base_path = Path("audio") / book_folder

        if not base_path.exists():
            print(f"Book folder not found: {base_path}")
            return

        audio_base_path.mkdir(parents=True, exist_ok=True)
        batch_file_path = audio_base_path / "tts_batch_requests.jsonl"

        # 1. Prepare Requests
        files_to_process = []
        requests = []
        
        print("Scanning files...")
        for root, _, files in os.walk(base_path):
            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(base_path)
                    output_path = audio_base_path / relative_path.with_suffix(".wav")
                    
                    if output_path.exists():
                        print(f"Skipping existing audio: {output_path}")
                        continue
                        
                    files_to_process.append((file_path, output_path))
                    
                    text = file_path.read_text(encoding="utf-8")
                    if not text.strip():
                        continue
                        
                    # Use relative path as custom_id
                    custom_id = str(relative_path).replace("\\", "/")
                    requests.append(self._create_batch_request(text, custom_id))
                    
                    if limit and len(requests) >= limit:
                        break
            
            if limit and len(requests) >= limit:
                break

        if not requests:
            print("No new files to process.")
            return

        print(f"Prepared {len(requests)} requests.")
        
        # Write JSONL file
        with batch_file_path.open("w", encoding="utf-8") as f:
            for req in requests:
                f.write(json.dumps(req) + "\n")

        # 2. Submit Batch Job
        print("Uploading batch file...")
        batch_file = self.client.files.upload(
            file=batch_file_path,
            config=types.UploadFileConfig(mime_type='application/json')
        )
        
        print("Submitting batch job...")
        batch_job = self.client.batches.create(
            model=self.model,
            src=batch_file.name
        )
        
        print(f"Batch job created: {batch_job.name}")
        print("Waiting for job to complete...")

        # 3. Poll for Completion
        while batch_job.state == "ACTIVE" or batch_job.state == "CREATING":
            time.sleep(30)
            batch_job = self.client.batches.get(name=batch_job.name)
            print(f"Status: {batch_job.state}")

        if batch_job.state != "SUCCEEDED":
            print(f"Batch job failed with state: {batch_job.state}")
            return

        print("Job succeeded. Downloading results...")

        # 4. Retrieve and Process Results
        try:
             output_content = self.client.files.download(file=batch_job.output_file)
             
             for line in output_content.decode("utf-8").split("\n"):
                 if not line.strip():
                     continue
                 result = json.loads(line)
                 custom_id = result["custom_id"]
                 
                 output_path = audio_base_path / Path(custom_id).with_suffix(".wav")
                 
                 if "error" in result:
                     print(f"Error for {custom_id}: {result['error']}")
                     continue
                     
                 try:
                     response_data = result["response"]
                     candidates = response_data.get("candidates", [])
                     if not candidates:
                         print(f"No candidates for {custom_id}")
                         continue
                         
                     parts = candidates[0].get("content", {}).get("parts", [])
                     if not parts:
                         print(f"No parts for {custom_id}")
                         continue
                         
                     inline_data = parts[0].get("inline_data", {})
                     data_b64 = inline_data.get("data")
                     
                     if not data_b64:
                         print(f"No data for {custom_id}")
                         continue
                         
                     import base64
                     pcm_data = base64.b64decode(data_b64)
                     
                     output_path.parent.mkdir(parents=True, exist_ok=True)
                     self._save_wave_file(output_path, pcm_data)
                     
                     usage = response_data.get("usage_metadata", {})
                     cost = calculate_tts_cost(usage, is_batch=True, print_cost=False)
                     self.total_cost += cost
                     print(f"  Generated {output_path.name} | Cost: ${cost:.6f}")
                     
                 except Exception as e:
                     print(f"Error processing result for {custom_id}: {e}")

        except Exception as e:
            print(f"Error downloading/processing results: {e}")
            print(f"Batch Job Details: {batch_job}")

        print(f"TTS Generation Completed. Total Estimated Cost: ${self.total_cost:.6f}")

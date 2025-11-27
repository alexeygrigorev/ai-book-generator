from book_generator.tts import TTSGenerator

def main():
    # You can change the book folder name here or use argparse for CLI arguments
    book_folder = "sirens"
    
    print(f"Starting TTS generation for book: {book_folder}")
    generator = TTSGenerator(
        num_threads=1,
        s3_bucket="ai-generated-audio-books-eu-west-1-wav"
    )
    generator.process_book(book_folder)

if __name__ == "__main__":
    main()

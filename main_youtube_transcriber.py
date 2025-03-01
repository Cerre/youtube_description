import asyncio
from video_selection.video_selector import VideoSelector
from downloads.downloader import Downloader
from transcription.transcriber import WhisperTranscriber, WhisperxTranscriber
from text_processing.text_processor import TextProcessor, clean_filename
import os
from numba import cuda
import time
from text_chunker.text_chunker import TextChunker
from embedding_generator.embedding_generator import EmbeddingGenerator


async def process_video(video, downloader, transcriber, text_processor, chunker, embedding_generator):
    start_time = time.time()
    audio_path = await downloader.download_audio(video)
    if audio_path:
        audio_file_name = clean_filename(video.title)
        transcript, metadata_dicts = await transcriber.transcribe_audio(audio_path)
        text_processor.save_processed_data(audio_file_name, transcript, metadata_dicts)

        # Combine text to 1 minute chunks with overlap.
        
        metadata_chunks = chunker.chunk_texts(metadata_dicts, video)
        # Create embeddings
        embedding_generator.generate_embeddings(metadata_chunks)


        # print(f"Transcript: {transcript}\n\n")
        # print()
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Processing time for video {video}: {elapsed_time:.2f} seconds.")
    else:
        print(f"Failed to download audio for video: {video.title}")


def setup_cuda():
    cuda_toolkit_path = _get_cuda_toolkit_path()
    if cuda_toolkit_path:
        os.environ["PATH"] += os.pathsep + cuda_toolkit_path
        os.environ["LD_LIBRARY_PATH"] = (
            "/usr/local/cuda/lib64:/usr/local/cuda-12.3/lib64:"
            + os.environ.get("LD_LIBRARY_PATH", "")
        )
    if cuda.is_available():
        print("CUDA is available. Using GPU for transcription.")
        device = "cuda"
        compute_type = "float16"  # Use FP16 for faster computation on GPU
    else:
        print("CUDA not available. Using CPU for transcription.")
        device = "cpu"
        compute_type = "auto"  # Use default compute type for CPU
    return device, compute_type


def _get_cuda_toolkit_path():
    # Change to your cuda path
    possible_paths = [
        "/usr/local/cuda-12.3/bin",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


async def main():
    # video_selector = VideoSelector(single_video_url="https://www.youtube.com/watch?v=PC8iEn8bdl8")
    # video_selector = VideoSelector(single_video_url="https://www.youtube.com/watch?v=CWeSzhJpJ9U") # 5 min
    
    video_selector = VideoSelector(
        url_list_path="/home/ceder/dev2/embeddings/channel_videos_medium.csv"
    )
    #video_selector = VideoSelector(
    #    single_video_url="https://www.youtube.com/watch?v=beAvFHP4wDI"
    #)  # 1 minute clip
    embedding_model = "text-embedding-3-large"
    videos = video_selector.get_videos()
    device, compute_type = setup_cuda()

    downloader = Downloader()
    # transcriber = WhisperTranscriber(model_name = "tiny.en", device=device, output_dir="transcripts", compute_type=compute_type)
    # 249 seconds for channel_videos_short.csv for WhisperTranscriber tiny.en
    # 1341 seconds for large-v3
    
    transcriber = WhisperxTranscriber(
        model_name="large-v3",
        device=device,
        output_dir="transcripts",
        compute_type=compute_type,
        batch_size=4,
    )
    # Total time for whisperX was 118 seconds for channel_videos_short.csv. tiny.en. Batch 32
    # 
    # 79 seconds with batch 2048
    # 77 seconds batch 512
    # 82 seconds with batch size 128
    # 459.seconds for large-v3 batch size 4


    transcriber.load_model()
    text_processor = TextProcessor()  # Not used right now
    chunker = TextChunker()
    embedding_generator = EmbeddingGenerator()
    start_time = time.time()
    tasks = [
        process_video(video, downloader, transcriber, text_processor, chunker, embedding_generator)
        for video in videos
    ]
    await asyncio.gather(*tasks)
    end_time = time.time()
    print(f"Total time for model {transcriber.__class__} is {end_time-start_time}")
    # breakpoint()
    # print(embedding_generator.db_client.peek())



if __name__ == "__main__":
    asyncio.run(main())

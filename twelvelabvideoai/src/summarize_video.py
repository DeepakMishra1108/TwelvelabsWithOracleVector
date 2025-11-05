import os
import os
import sys
import array
import time
import oracledb
from twelvelabs import TwelveLabs
from twelvelabs import Pegasus
from twelvelabs.types import VideoSegment
from twelvelabs.embed import TasksStatusResponse
from dotenv import load_dotenv
import oci

load_dotenv()

# Environment variables
db_username = os.getenv("ORACLE_DB_USERNAME")
db_password = os.getenv("ORACLE_DB_PASSWORD")
db_connect_string = os.getenv("ORACLE_DB_CONNECT_STRING")
db_wallet_path = os.getenv("ORACLE_DB_WALLET_PATH")
db_wallet_pw = os.getenv("ORACLE_DB_WALLET_PASSWORD")
twelvelabs_api_key = os.getenv("TWELVE_LABS_API_KEY")
PEGASUS_API_KEY = os.getenv("PEGASUS_API_KEY")

# Constants

# Initialize Twelve Labs client
twelvelabs_client = TwelveLabs(api_key=twelvelabs_api_key)

# Initialize Pegasus with your API key (replace with your actual key)
pegasus = Pegasus(api_key=PEGASUS_API_KEY)


def summarize_video(video_url):
    """
    Summarizes a video using Twelvelabs Pegasus.
    """
    response = pegasus.summarize_video(video_url=video_url)
    summary = response.get("summary")
    if not summary:
        raise Exception("Video summary failed.")
    print("Video Summary:")
    print(summary)

if __name__ == "__main__":
   
   
    # Replace with actual video URL after generation
    video_url = "https://example.com/generated_video.mp4"
    summarize_video(video_url)
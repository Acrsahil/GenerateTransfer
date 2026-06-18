import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackNotifier:
    def __init__(self):
        # 1. Load environment variables from the .env file
        load_dotenv()

        token = os.getenv("SLACK_BOT_TOKEN")
        user_id = os.getenv("MY_USER_ID")

        if not token:
            raise ValueError("SLACK_BOT_TOKEN not found in environment or .env file")

        if not user_id:
            raise ValueError("MY_USER_ID not found in environment or .env file")

        # 2. Initialize the WebClient
        self.client = WebClient(token=token)

        # 3. FIX: Convert your User ID (U...) into a proper DM Channel ID (D...)
        try:
            response = self.client.conversations_open(users=user_id)
            self.receiver_id = response["channel"]["id"]  # This converts 'U...' to 'D...'
            print(f"DM Session opened successfully. Target DM ID: {self.receiver_id}")
        except SlackApiError as e:
            raise ValueError(f"Failed to open DM with User ID {user_id}: {e.response['error']}")

    def send_message(self, message: str) -> bool:
        """Sends a plain text message to the configured receiver."""
        try:
            response = self.client.chat_postMessage(
                channel=self.receiver_id,
                text=message,
            )
            print(f"Message sent! TS: {response['ts']}")
            return True
        except SlackApiError as e:
            print(f"Slack API Error (Message): {e.response['error']}")
            return False

    def send_file(self, file_path: str, initial_comment: str = None) -> bool:
        """
        Uploads and sends a file to the configured receiver using files_upload_v2.
        """
        if not os.path.exists(file_path):
            print(f"Error: The file at '{file_path}' does not exist.")
            return False

        try:
            filename = os.path.basename(file_path)
            print(f"Uploading '{filename}' to Slack...")
            
            # Open the file in binary read mode ('rb')
            with open(file_path, "rb") as file_content:
                # FIX: We use 'channel' here because the SDK handles mapping it internally
                response = self.client.files_upload_v2(
                    channel=self.receiver_id,  # Uses the translated 'D...' ID
                    file=file_content,
                    filename=filename,
                    initial_comment=initial_comment
                )
            
            assert response["file"]
            print(f"File sent successfully! File ID: {response['file']['id']}")
            return True

        except SlackApiError as e:
            print(f"Slack API Error (File): {e.response['error']}")
            return False

if __name__ == "__main__":
    notifier = SlackNotifier()
    
    # 1. (Optional) Send a text notification first
    notifier.send_message("Hello! Sending the existing report file from the directory.")
    
    # 2. Point directly to your existing file name
    # Change "output.xlsx" to the exact name of your file if it's different
    existing_file = "./aws.xlsx" 
        
    # 3. Send it
    notifier.send_file(
        file_path=existing_file, 
        initial_comment="📊 Here is the present Excel report file."
    )

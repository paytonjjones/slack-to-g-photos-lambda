import os

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()


def create_slack_client():
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_token)
    return client


def get_channel_id(channel_name, client=None):
    conversations = client.conversations_list()
    conversation_id = None
    for channel in conversations["channels"]:
        if channel["name"] == channel_name:
            conversation_id = channel["id"]
            break
    return conversation_id


def get_photo_dictionary_from_channel(channel_name, client=None):
    channel_id = get_channel_id(channel_name, client)
    channel_messages = client.conversations_history(channel=channel_id)

    photo_dictionary = {}
    for message in channel_messages["messages"]:
        files = message.get("files")
        if files is not None:
            for file in files:
                try:
                    photo_id = file.get("id")
                    url_private = file.get("url_private")
                    photo_dictionary.update({photo_id: url_private})
                except Exception as e:
                    print(e)
                    print(file)

    return photo_dictionary

import json
import os
from dotenv import load_dotenv

from utils import create_slack_client, get_photo_dictionary_from_channel

load_dotenv()


def handler(event, context):
    client = create_slack_client()
    photo_dictionary = get_photo_dictionary_from_channel("photos", client)
    body = {
        "message": photo_dictionary,
        "input": event,
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response

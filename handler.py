import json
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from utils import (
    create_slack_client,
    get_photo_dictionary_from_channel,
    send_email,
    split_dict,
)

load_dotenv()


def handler(event, context):
    # after_timestamp = (datetime.now() - timedelta(hours=1)).timestamp()
    after_timestamp = 0
    client = create_slack_client()
    photo_dictionary = get_photo_dictionary_from_channel(
        "photos", after_timestamp, client
    )

    chunks_of = 3
    total_chunks = int(len(photo_dictionary) / chunks_of)
    for mini_photo_dict in split_dict(photo_dictionary, total_chunks):
        send_email(
            send_from=os.environ["EMAIL_ADDRESS"],
            send_to=[os.environ["PHOTO_FRAME_EMAIL_ADDRESS"]],
            subject="New Photos From Slack",
            text="Photos sent via AWS Lambda",
            password=os.environ["EMAIL_PASSWORD"],
            image_dict=mini_photo_dict,
            slack_token=os.environ["SLACK_BOT_TOKEN"],
            server="smtp.gmail.com",
        )

    body = {
        "message": photo_dictionary,
        "input": event,
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response

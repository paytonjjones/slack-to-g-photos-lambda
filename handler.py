import json
import os
from dotenv import load_dotenv
from datetime import date

from utils import create_slack_client, get_photo_dictionary_from_channel, send_email

load_dotenv()


def handler(event, context):
    client = create_slack_client()
    photo_dictionary = get_photo_dictionary_from_channel("photos", client)

    send_email(
        send_from=os.environ["EMAIL_ADDRESS"],
        send_to=[os.environ["PHOTO_FRAME_EMAIL_ADDRESS"]],
        subject="New Photos From Slack",
        text="Photos sent via AWS Lambda",
        password=os.environ["EMAIL_PASSWORD"],
        image_dict=photo_dictionary,
        slack_token=os.environ["SLACK_BOT_TOKEN"],
        server="smtp.gmail.com",
    )

    body = {
        "message": photo_dictionary,
        "input": event,
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response

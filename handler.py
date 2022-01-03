import json
import logging
import os
import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta

from utils import (
    create_slack_client,
    get_photo_dictionary_from_channel,
    send_email,
    split_dict,
    get_dictionary_from_dynamodb,
    update_dynamodb,
)

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    # previously added images
    dynamodb_resource = boto3.resource(
        "dynamodb",
        region_name=os.environ["AWS_REGION"],
        verify=True,  # for local execution set verify=False
    )
    dynamo_dict = get_dictionary_from_dynamodb(
        os.environ["DYNAMODB_TABLE_NAME"], dynamodb_resource
    )

    # date range
    latest = datetime.now().timestamp()
    oldest = (datetime.now() - timedelta(hours=24)).timestamp()

    # for specific date execution use:
    # oldest = (datetime.now() - timedelta(days=30)).timestamp()
    # latest = (datetime.now() - timedelta(days=5)).timestamp()

    # new images from slack
    client = create_slack_client()
    photo_dictionary = get_photo_dictionary_from_channel(
        "photos", oldest, latest, client
    )

    photo_dictionary.update(dynamo_dict)

    photo_dictionary = {k: v for k, v in photo_dictionary.items() if not v["attached"]}

    if not photo_dictionary:
        logger.info("No new images found")
        pass
    else:
        chunks_of = 3
        total_chunks = int(len(photo_dictionary) / chunks_of)
        total_chunks = total_chunks if total_chunks > 0 else 1
        for mini_photo_dict in split_dict(photo_dictionary, total_chunks):
            updated_dict = send_email(
                send_from=os.environ["EMAIL_ADDRESS"],
                send_to=[os.environ["PHOTO_FRAME_EMAIL_ADDRESS"]],
                subject="New Photos From Slack",
                text="Photos sent via AWS Lambda",
                password=os.environ["EMAIL_PASSWORD"],
                photo_dictionary=mini_photo_dict,
                slack_token=os.environ["SLACK_BOT_TOKEN"],
                server="smtp.gmail.com",
                max_retries=3,
            )
            photo_dictionary.update(updated_dict)

        dynamodb_client = boto3.client(
            "dynamodb", region_name=os.environ["AWS_REGION"], verify=False
        )
        update_dynamodb(
            photo_dictionary, os.environ["DYNAMODB_TABLE_NAME"], dynamodb_client
        )

    body = {
        "message": photo_dictionary,
        "input": event,
    }

    response = {"statusCode": 200, "body": json.dumps(body)}

    return response

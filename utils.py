import os
import smtplib
import requests
import itertools
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import COMMASPACE, formatdate

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


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


def get_photo_dictionary_from_channel(
    channel_name, oldest=0, latest=datetime.now().timestamp(), client=None
):
    channel_id = get_channel_id(channel_name, client)
    photo_dictionary = {}
    next_cursor = None

    while True:
        channel_messages = client.conversations_history(
            channel=channel_id,
            oldest=oldest,
            latest=latest,
            cursor=next_cursor,
            limit=200,
        )

        for message in channel_messages["messages"]:
            files = message.get("files")
            if files is not None:
                for file in files:
                    try:
                        image_id = file.get("id")
                        image_name = file.get("name")
                        url_private = file.get("url_private")
                        photo_dictionary.update(
                            {
                                image_id: {
                                    "image_name": image_name,
                                    "url_private": url_private,
                                    "attached": False,
                                }
                            }
                        )
                    except Exception as e:
                        logger.info(e)
                        logger.info(file)

        metadata = channel_messages.get("response_metadata")
        if metadata is None:
            break
        else:
            next_cursor = metadata.get("next_cursor")

    return photo_dictionary


def send_email(
    send_from,
    send_to,
    subject,
    text,
    password=None,
    photo_dictionary=None,
    slack_token=None,
    server="smtp.gmail.com",
    max_retries=3,
):
    """
    From https://stackoverflow.com/questions/3362600/how-to-send-email-attachments
    """
    assert isinstance(send_to, list)

    retries = 0
    while retries < max_retries:
        try:
            msg = MIMEMultipart()
            msg["From"] = send_from
            msg["To"] = COMMASPACE.join(send_to)
            msg["Date"] = formatdate(localtime=True)
            msg["Subject"] = subject

            msg.attach(MIMEText(text))

            for image_id, image_info in photo_dictionary.items():
                image_name = image_info.get("image_name")
                url_private = image_info.get("url_private")
                if url_private is not None and "HDR." not in image_name:
                    try:
                        response = requests.get(
                            url_private,
                            headers={"Authorization": "Bearer %s" % slack_token},
                        )
                        image = MIMEImage(response.content)
                        image_name_as_valid_file = "".join(
                            [x if x.isalnum() else "_" for x in image_name]
                        )
                        image.add_header(
                            "Content-Disposition",
                            "attachment",
                            filename=image_name_as_valid_file,
                        )
                        msg.attach(image)
                        photo_dictionary[image_id].update(
                            {
                                "image_name": image_name,
                                "url_private": url_private,
                                "attached": True,
                            }
                        )
                    except Exception as e:
                        logger.info(e)
                        logger.info(image_name)
                        logger.info(url_private)

            smtp = smtplib.SMTP(server)
            smtp.starttls()
            smtp.login(send_from, password)
            smtp.sendmail(send_from, send_to, msg.as_string())
            smtp.close()
            retries = max_retries
        except Exception as e:
            retries += 1
            logger.info(e)
            logger.info("Error in sending email. Retrying...")
            continue
    return photo_dictionary


def split_dict(x, chunks):
    i = itertools.cycle(range(chunks))
    split = [dict() for _ in range(chunks)]
    for k, v in x.items():
        split[next(i)][k] = v
    return split


def get_dictionary_from_dynamodb(table_name, dynamodb_resource=None):
    table = dynamodb_resource.Table(table_name)
    response = table.scan()
    list_of_dicts = response["Items"]
    restructured_dict = {}
    for d in list_of_dicts:
        restructured_dict.update(
            {
                d["image_id"]: {
                    "image_name": d["image_name"],
                    "url_private": d["url_private"],
                    "attached": d["attached"],
                }
            }
        )
    return restructured_dict


def update_dynamodb(photo_dictionary, table_name, dynamodb_client=None):
    for image_id, image_info in photo_dictionary.items():
        image_name = image_info.get("image_name")
        url_private = image_info.get("url_private")
        attached = image_info.get("attached")
        if url_private is not None:
            try:
                dynamodb_client.update_item(
                    TableName=table_name,
                    Key={"image_id": {"S": image_id}},
                    UpdateExpression="set image_name=:n, url_private=:u, attached=:a",
                    ExpressionAttributeValues={
                        ":n": {"S": image_name},
                        ":u": {"S": url_private},
                        ":a": {"BOOL": attached},
                    },
                    ReturnValues="UPDATED_NEW",
                )
            except Exception as e:
                logger.info(e)
                logger.info(image_name)
                logger.info(url_private)


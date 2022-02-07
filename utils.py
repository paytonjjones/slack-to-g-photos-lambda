import os
import smtplib
import ssl
import requests
import itertools
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import COMMASPACE, formatdate

from pytz import timezone
from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def logTime(tz="US/Pacific"):
    time = datetime.now(tz=timezone(tz)).strftime("%I:%M %p")
    logger.info(f"The current time in {tz} is {time}")


def create_slack_client(verify=True):
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    if verify:
        client = WebClient(token=slack_token)
    else:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        client = WebClient(token=slack_token, ssl=ssl_context)
    return client


def get_channel_id(channel_name, client=None):
    conversations = client.conversations_list()
    conversation_id = None
    for channel in conversations["channels"]:
        if channel["name"] == channel_name:
            conversation_id = channel["id"]
            break
    return conversation_id


def get_formatted_image_name(file):
    image_name = file.get("name")
    image_name_formatted = "".join(
        [x if (x.isalnum() or x in ".-") else "_" for x in image_name]
    )
    return image_name_formatted


def check_file_validity(file):
    image_deleted = file.get("mode") == "tombstone"
    if image_deleted:
        return False
    image_name_formatted = get_formatted_image_name(file)
    is_hdr = "HDR." in image_name_formatted
    if is_hdr:
        return False
    ext = image_name_formatted.split(".")[-1]
    valid_extension = ext in [
        "jpg",
        "JPG",
        "jpeg",
        "JPEG",
        "png",
        "PNG",
    ]
    if not valid_extension:
        return False
    url_private = file.get("url_private")
    if url_private is None:
        return False
    return True


def deduplicate_image_name(image_name, is_duplicate, iterator):
    if is_duplicate:
        name_without_ext = image_name.split(".")[-2]
        ext = image_name.split(".")[-1]
        iterated_suffix = "__" + str(iterator)
        return name_without_ext + iterated_suffix + "." + ext, iterator + 1
    else:
        return image_name, iterator


def get_photo_dictionary_from_channel(
    channel_name, oldest=0, latest=datetime.now().timestamp(), client=None
):
    channel_id = get_channel_id(channel_name, client)
    photo_dictionary = {}
    next_cursor = None

    while True:
        batch_of_channel_messages = client.conversations_history(
            channel=channel_id,
            oldest=oldest,
            latest=latest,
            cursor=next_cursor,
            limit=200,
        )

        image_names = []
        for message in batch_of_channel_messages["messages"]:
            files = message.get("files")
            if files is not None:
                iterator = 1
                for file in files:
                    try:
                        if check_file_validity(file):
                            image_name_formatted = get_formatted_image_name(file)
                            image_name_deduplicated, iterator = deduplicate_image_name(
                                image_name_formatted,
                                is_duplicate=image_name_formatted in image_names,
                                iterator=iterator,
                            )
                            image_names.append(image_name_deduplicated)
                            image_id = file.get("id")
                            photo_dictionary.update(
                                {
                                    image_id: {
                                        "image_name": image_name_deduplicated,
                                        "url_private": file.get("url_private"),
                                        "attached": False,
                                    }
                                }
                            )
                        else:
                            logger.info("File not in acceptable format:")
                            logger.info(file.get("name"))
                            logger.info(file.get("url_private"))
                    except Exception as e:
                        logger.info(e)
                        logger.info(file)

        metadata = batch_of_channel_messages.get("response_metadata")
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
    has_attachment = False
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
                if url_private is not None:
                    try:
                        response = requests.get(
                            url_private,
                            headers={"Authorization": "Bearer %s" % slack_token},
                        )
                        image = MIMEImage(response.content)
                        image.add_header(
                            "Content-Disposition", "attachment", filename=image_name,
                        )
                        msg.attach(image)
                        photo_dictionary[image_id].update(
                            {
                                "image_name": image_name,
                                "url_private": url_private,
                                "attached": True,
                            }
                        )
                        has_attachment = True
                    except Exception as e:
                        logger.info(e)
                        logger.info(image_name)
                        logger.info(url_private)

            if has_attachment:
                logger.info("Sending email...")
                smtp = smtplib.SMTP(server, 587)
                smtp.starttls()
                smtp.login(send_from, password)
                logger.info("Email login successful...")
                smtp.sendmail(send_from, send_to, msg.as_string())
                smtp.close()
                logger.info("Email sent!")
                return photo_dictionary
            else:
                logger.info("No attachments found, nothing to send")
                return {}
        except Exception as e:
            retries += 1
            logger.info(e)
            logger.info("Error in sending email. Retrying...")
            continue
    return {}


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
                    UpdateExpression="set image_name=:n, url_private=:u, attached=:a, updated_at=:t",
                    ExpressionAttributeValues={
                        ":n": {"S": image_name},
                        ":u": {"S": url_private},
                        ":a": {"BOOL": attached},
                        ":t": {"S": str(datetime.now())},
                    },
                    ReturnValues="UPDATED_NEW",
                )
            except Exception as e:
                logger.info(e)
                logger.info(image_name)
                logger.info(url_private)


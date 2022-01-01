import os
import smtplib
import requests
import itertools
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

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


def get_photo_dictionary_from_channel(channel_name, after_timestamp=0, client=None):
    channel_id = get_channel_id(channel_name, client)
    photo_dictionary = {}
    next_cursor = None

    while True:
        channel_messages = client.conversations_history(
            channel=channel_id, oldest=after_timestamp, cursor=next_cursor, limit=200
        )

        for message in channel_messages["messages"]:
            files = message.get("files")
            if files is not None:
                for file in files:
                    try:
                        photo_id = file.get("name")
                        url_private = file.get("url_private")
                        photo_dictionary.update({photo_id: url_private})
                    except Exception as e:
                        print(e)
                        print(file)

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
    image_dict=None,
    slack_token=None,
    server="smtp.gmail.com",
):
    """
    From https://stackoverflow.com/questions/3362600/how-to-send-email-attachments
    """
    assert isinstance(send_to, list)

    msg = MIMEMultipart()
    msg["From"] = send_from
    msg["To"] = COMMASPACE.join(send_to)
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject

    msg.attach(MIMEText(text))

    for image_name, image_url in image_dict.items():
        if image_url is not None:
            response = requests.get(
                image_url, headers={"Authorization": "Bearer %s" % slack_token}
            )
            ext = image_name.split(".")[-1:]
            part = MIMEApplication(response.content, Name=image_name, _subtype=ext)
            part["Content-Disposition"] = 'attachment; filename="%s"' % image_name
            msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.starttls()
    smtp.login(send_from, password)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()


def split_dict(x, chunks):
    i = itertools.cycle(range(chunks))
    split = [dict() for _ in range(chunks)]
    for k, v in x.items():
        split[next(i)][k] = v
    return split


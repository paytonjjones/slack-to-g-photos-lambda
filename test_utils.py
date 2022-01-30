import logging
from unittest.mock import Mock, patch
from data.mocks import mock_message, mock_conversation_history
from utils import (
    check_file_validity,
    create_slack_client,
    get_channel_id,
    get_formatted_image_name,
    get_photo_dictionary_from_channel,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def test_create_slack_client__integration():
    client = create_slack_client()
    try:
        client.auth_test()
    except Exception as e:
        logger.info(e)
        assert False


def test_get_channel_id__integration():
    client = create_slack_client()
    channel_id = get_channel_id("photos", client)
    assert channel_id == "C01AJKY3CKC"


def test_get_formatted_image_name():
    file = mock_message["files"][0]
    image_name = get_formatted_image_name(file)
    assert image_name == "Image_from_iOS.jpg"


def test_check_file_validity():
    mock_file_1 = {"mode": "tombstone", "url_private": "A Test URL"}
    assert not check_file_validity(mock_file_1)
    mock_file_2 = {
        "mode": "file",
        "name": "Image_from_iOS.HDR.jpg",
        "url_private": "A Test URL",
    }
    assert not check_file_validity(mock_file_2)
    mock_file_3 = {
        "mode": "file",
        "name": "Image_from_iOS.HDR.mp4",
        "url_private": "A Test URL",
    }
    assert not check_file_validity(mock_file_3)
    mock_file_4 = {
        "mode": "file",
        "name": "Image_from_iOS.jpg",
    }
    assert not check_file_validity(mock_file_4)

    file = mock_message["files"][0]
    assert check_file_validity(file)


@patch("utils.get_channel_id")
def test_get_photo_dictionary_from_channel(get_channel_id):
    client = Mock()
    client.conversations_history = Mock(return_value=mock_conversation_history)
    photo_dictionary = get_photo_dictionary_from_channel(
        "photos", oldest=None, latest=None, client=client,
    )

    expectedPhotoDictionary = {
        "ID1": {
            "attached": False,
            "image_name": "Image_from_iOS.jpg",
            "url_private": "A Test URL",
        },
        "ID2": {
            "attached": False,
            "image_name": "Image_from_iOS__1.jpg",
            "url_private": "A Test URL",
        },
    }
    assert photo_dictionary == expectedPhotoDictionary
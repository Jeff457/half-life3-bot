from TwitterAPI import TwitterAPI
from base64 import b64decode

import xmltodict
import requests
import logging
import boto3
import json
import os


NEW_RELEASES = "https://store.steampowered.com/feeds/newreleases.xml"


log = logging.getLogger()
log.setLevel(logging.INFO)

kms = boto3.client("kms")

api = TwitterAPI(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token_key=ACCESS_TOKEN_KEY,
    access_token_secret=ACCESS_TOKEN_SECRET
)


def decrypt(encrypted: str) -> str:
    """Decrypt and return the encrypted environment variables.

    Args:
        encrypted: A base64 encoded string representing the
            key to be decrypted.

    Returns:
        A string representing the decrypted key.
    """
    return kms.decrypt(CiphertextBlob=b64decode(encrypted))["Plaintext"]


CONSUMER_KEY = decrypt(os.getenv("CONSUMER_KEY"))
CONSUMER_SECRET = decrypt(os.getenv("CONSUMER_SECRET"))
ACCESS_TOKEN_KEY = decrypt(os.getenv("ACCESS_TOKEN_KEY"))
ACCESS_TOKEN_SECRET = decrypt(os.getenv("ACCESS_TOKEN_SECRET"))


def handler(event, context):
    res = requests.get(NEW_RELEASES)
    try:
        titles = list()
        releases = xmltodict.parse(res.text)["rss"]["channel"]["item"]
        for game in releases:
            try:
                title = game.get("title").split("-")[1].strip().split(",")[0]
                link = game.get("link")
                description = game.get("description")
                titles.append({title: link})
                check = title.lower()
                # don't guess on formatting if HL3 is ever released
                if "half" in check and "life" in check and "3" in check:
                    # sweet jesus it's out
                    pass
            except IndexError as index_error:
                log.error(str(index_error))

        print(titles)
    except KeyError as key_error:
        log.error(str(key_error))


if __name__ == "__main__":
    handler({}, {})

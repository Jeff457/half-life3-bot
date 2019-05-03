from TwitterAPI import TwitterAPI
from bs4 import BeautifulSoup
from base64 import b64decode

import requests
import logging
import arrow
import boto3
import json
import os


# Apr 13, 2019
DATETIME_FORMAT = "MMM DD, YYYY"
NEW_RELEASES = "https://store.steampowered.com/search/?sort_by=Released_DESC&os=win"


log = logging.getLogger()
log.setLevel(logging.INFO)

kms = boto3.client("kms", region_name="us-west-2")


def decrypt(encrypted: str) -> str:
    """Decrypt and return the encrypted environment variables.

    Args:
        encrypted: A base64 encoded string representing the
            key to be decrypted.

    Returns:
        A string representing the decrypted key.
    """
    if os.getenv("DEV"):
        return encrypted
    return kms.decrypt(CiphertextBlob=b64decode(encrypted))["Plaintext"]


CONSUMER_KEY = decrypt(os.getenv("CONSUMER_KEY"))
CONSUMER_SECRET = decrypt(os.getenv("CONSUMER_SECRET"))
ACCESS_TOKEN_KEY = decrypt(os.getenv("ACCESS_TOKEN_KEY"))
ACCESS_TOKEN_SECRET = decrypt(os.getenv("ACCESS_TOKEN_SECRET"))

api = TwitterAPI(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token_key=ACCESS_TOKEN_KEY,
    access_token_secret=ACCESS_TOKEN_SECRET
)


class TweetException(Exception):
    pass


def tweet(*, title: str, link: str, **kwargs):
    """Tweet game info.

    Args:
        title: a str representing the game title to be tweeted.
        link: a str representing the Steam article about the game.

    Raises:
        TweetException: for 4xx responses
    """
    message = ["No Half-Life 3 yet.\n"]

    check = title.lower()
    # don't guess on formatting if HL3 is ever released
    if "half" in check and "life" in check and "3" in check:
        message[0] = "Sweet Jesus Half-Life 3 is out!\n"

    message.append(f"{title} {link}")
    status = {
        "status": "\n".join(m for m in message)
    }

    res = api.request("statuses/update", status)
    res_json = res.json()

    # 187 = status is a duplicate, ignore
    if res.status_code >= 400 and res_json["errors"][0]["code"] != 187:
        raise TweetException(json.dumps(res_json))


def handler(event, context):
    now = arrow.utcnow()
    res = requests.get(NEW_RELEASES)
    try:
        page = BeautifulSoup(res.text, features="html.parser")

        all_games = page.find_all(
            "div", {"class": "responsive_search_name_combined"}
        )
        for game in all_games:
            try:
                # steampowered link to game page
                link = game.parent["href"]

                # contains title and release date
                # '\n\nLevers & Buttons\n\n \n\nApr 13, 2019\n\n\n\n-25%\n\n'
                info = game.text.strip().split("\n\n")
                title = info[0]

                try:
                    # games are sorted by release date
                    released = arrow.get(info[2], DATETIME_FORMAT)
                except arrow.parser.ParserError as e:
                    # arrow is dumb
                    released = arrow.get(info[2], "MMM D, YYYY")

                # return if no new games have been released
                if released.day < now.day:
                    return

                tweet(title=title, link=link)
                log.info(f"Finished tweeting about {title}")
            except (
                IndexError, arrow.parser.ParserError, TweetException
            ) as error:
                log.error(str(error))
    except KeyError as key_error:
        log.error(str(key_error))

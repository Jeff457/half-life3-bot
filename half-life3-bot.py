from TwitterAPI import TwitterAPI
from base64 import b64decode

import xmltodict
import requests
import logging
import arrow
import boto3
import json
import os


# Fri, 12 Apr 2019 18:10:21 -0700
DATETIME_FORMAT = "ddd, D MMM YYYY HH:mm:ss Z"
NEW_RELEASES = "https://store.steampowered.com/feeds/newreleases.xml"


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
        releases = xmltodict.parse(res.text)["rss"]["channel"]

        # check if new releases page has been updated
        last_build_date = releases["lastBuildDate"]
        last = arrow.get(last_build_date, DATETIME_FORMAT).to("UTC")

        if last.day < now.day:
            log.info(f"No new releases yet. Last updated: {last.humanize()}")
            return

        yesterday = now.replace(days=-1)
        items = releases["item"]
        for game in items:
            try:
                # items are sorted from newest - oldest release date
                published_date = arrow.get(
                    game.get("pubDate"), DATETIME_FORMAT).to("UTC")

                # return if pubDate is before 10AM PST the previous day
                # since function runs 10AM PST daily
                if published_date < yesterday:
                    return

                # Now Available on Steam - GAME TITLE, % off!
                title = game.get("title").split("-")[1].strip().split(",")[0]
                # steampowered news link about game
                link = game.get("link")

                tweet(title=title, link=link)
                log.info(f"Finished tweeting about {title}")
            except (IndexError, TweetException) as error:
                log.error(str(error))
    except KeyError as key_error:
        log.error(str(key_error))

#!/usr/bin/env bash

# get the full path to the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ZIP=$DIR/half-life3-bot.zip

# remove existing archive
rm $ZIP

# add dependencies to archive
zip -r9 $ZIP package/

# add lambda function to archive
zip -g $ZIP half-life3-bot.py

# update lambda function
aws lambda update-function-code --function-name half-life3-bot --zip-file fileb://$ZIP
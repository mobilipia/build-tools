#!/bin/bash
# Mimics "forge package ios" without requiring the Forge build tools to be installed
# Arguments:
#    * path to the .app
#    * path to the desired provisioning profile (strongly recommend only using development wildcard profiles to start with)
#    * developer certificate name
#    * output path for IPA
# 
# Gotchas:
#    * I don't appear to handle spaces in paths properly: I'd recommend you put the app, profile and script somewhere without a space in the path
#    * the certificate name must be unique

get_abs_path() {
	local PARENT_DIR=$(dirname "$1")
	cd "$PARENT_DIR"
	local ABS_PATH="$(pwd)"/"$(basename $1)"
	cd - >/dev/null
	echo $ABS_PATH
} 

set -e
# set -x

if [ -z "$4" ]; then
	cat << EOM

Usage: $0 app provisioning_profile certificate output

    app: relative or absolute path to the output from 'forge build'
        should be called something like device-testplatform7d72364f474811e1861658b035f29a76.app

    provisioning_profile: relative or absolute path to your .mobileprovision file,
        downloaded from the Apple developer centre

    certificate: developer certificate identity to build with, e.g. 'iPhone Developer'

    output: where to write the IPA to

EOM
	exit 1
else
	APP=$(get_abs_path $1)
	PROV_P=$(get_abs_path $2)
	CERT=$3
	OUTPUT=$(get_abs_path $4)
fi

echo "Checking input"
if [ ! -d "$APP" ]; then
	echo "app must be a directory"
	exit 1
else
	APP=$(echo $APP | sed -e 's#/$##')
	APP_DIR=$(basename $APP)
fi

if [ ! -f "$PROV_P" ]; then
	echo "provisioning_profile must be a file"
	exit 1
fi

SEED_ID=$(grep --binary-files=text -A2 ApplicationIdentifierPrefix $PROV_P | perl -n -e'/<string>(\w+)<\/string>/ && print $1')

if [ -z "$SEED_ID" ]; then
	echo "Couldn't extract app seed ID from your provisioning profile: are you're sure you pointed at the right file?"
	exit 2
fi

echo "Removing previous output"
rm -f "$OUTPUT"

ORIG_DIR=$(pwd)

echo "Creating IPA"
WORKING=$(mktemp -d -t forge)
cd $WORKING

echo "Creating Payload"
PAYLOAD="Payload"
PAYLOAD_APP="$PAYLOAD/$APP_DIR"

mkdir $PAYLOAD
cp -Rp $APP $PAYLOAD
# codesign --verify -vvvv $ORIG_DIR/../../.template/ios/device*
rm $PAYLOAD_APP/embedded.mobileprovision
cp -p $PROV_P "$PAYLOAD_APP/embedded.mobileprovision"

echo "Doing horrific things to the binary"
# sed -e "s/YGP57GM255/$SEED_ID/g" -i .bak $PAYLOAD_APP/Forge
sed -e "s/5ARZY8MX8B/$SEED_ID/g" -i .bak $PAYLOAD_APP/Forge

echo "Signing"
codesign --force --preserve-metadata --sign "$CERT" --resource-rules=$PAYLOAD_APP/ResourceRules.plist $PAYLOAD_APP

echo "Zipping"
zip --quiet --symlinks --recurse-paths $OUTPUT .

echo "Cleaning up"
cd $ORIG_DIR
rm -rf $WORKING

#!/bin/bash

set -e

#
# Push built image to ecr staging
#

if [ x"$BRANCH_NAME" != x"master" -a x"$BRANCH_NAME" != x"next_release" -a x"$BRANCH_NAME" != x"staging" ]; then
    echo "Branch $BRANCH_NAME is not deployable. Skipping prod build and tests"
    exit 0
fi

pip install --user awscli # install aws cli w/o sudo
export PATH=$PATH:$HOME/.local/bin # put aws in the path

eval $(aws ecr get-login --region ap-southeast-2) #needs AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY envvars
env

tag="?????"

ecrtag="$AWSACCOUNTID.dkr.ecr.us-east-1.amazonaws.com/$tag"  # needs account id in env

docker push $ecrtag



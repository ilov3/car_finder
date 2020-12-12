#!/bin/bash
set -m
scrapyd --pidfile= &
until $(curl --output /dev/null --silent --head --fail http://localhost:6800); do
    echo 'Waiting for scrapyd...'
    sleep 3
done
scrapyd-deploy
fg

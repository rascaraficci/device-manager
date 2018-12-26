#!/bin/bash -ex
if [ $TRAVIS_PULL_REQUEST == false ] ; then
  version="latest"
  if [ $TRAVIS_BRANCH != "master" ] ; then
    version=$TRAVIS_BRANCH
  fi

  tag=${TRAVIS_REPO_SLUG}:$version

  echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
  docker tag ${TRAVIS_REPO_SLUG} ${tag}
  docker push $tag
fi

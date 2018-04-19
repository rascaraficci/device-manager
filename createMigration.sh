#!/bin/sh

# This helps devs create easier to maintain migrations for device-manager
# When migrations are run, pg schemas (namespaces) are set up in runtime, but it is quite
# cumbersome to generate said "shema-less" migrations in the first place.
#
# This creates a clean slate alembic migrations environment to generate new migrations
# for the project.

get_dir() {
    newdir=$(tr -cd '[:alnum:]' < /dev/urandom | fold -w10 | head -n1)
    while [ -d ${newdir} ] ; do
        newdir=$(tr -cd '[:alnum:]' < /dev/urandom | fold -w10 | head -n1)
    done
    echo ${newdir}
}

script_home=$( dirname $(readlink -f "$0") )
target=$(get_dir)
home="${script_home}/migrations/versions"
flask db init --directory ${target}
for i in ${home}/*.py ; do
    ln -s ${i} ${target}/versions/$(basename ${i}) ;
done

flask db migrate --directory ${target}
result=$?

if [ ${result} != 0 ] ; then
    flask db upgrade --directory ${target}
    flask db migrate --directory ${target}
fi


for i in ${target}/versions/*.py ; do
    [ ! -h ${i} ] && cp ${i} ${home}
done

# remove unneeded file
rm -rf ${target}
